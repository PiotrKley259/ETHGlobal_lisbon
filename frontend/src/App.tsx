import { useCallback, useEffect, useRef, useState } from "react";
import { getPanel, streamChat } from "./api";
import { Chat } from "./components/Chat";
import type { ChatMessage } from "./components/Chat";
import { ChainStrip } from "./components/ChainStrip";
import { Landing } from "./components/Landing";
import { PricingPanel } from "./components/PricingPanel";
import type { ChainEvent, PanelState, SseEvent } from "./types";
import "./App.css";

// Three regions per the spec: chat (left, primary), pricing panel (right top),
// chain activity strip (right bottom). All SSE events funnel through here:
// chat events feed the message list, `panel` and `chain` feed the right side.
// Router-free routing: "/" = landing, "/desk" = the desk app. pushState keeps
// the query string intact so the ?key=... invite flow survives navigation.
const onDesk = () => window.location.pathname === "/desk";

function App() {
  const [view, setView] = useState<"landing" | "desk">(onDesk() ? "desk" : "landing");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [panel, setPanel] = useState<PanelState | null>(null);
  const [chainEvents, setChainEvents] = useState<ChainEvent[]>([]);
  const conversationId = useRef<string | null>(null);

  // Hydrate the panel on load and after settings changes (the backend
  // recomputes the regime when bands change — CONTRACTS §3).
  const hydratePanel = useCallback(() => {
    getPanel()
      .then(setPanel)
      .catch(() => {}); // backend not up yet — panel stays empty
  }, []);
  useEffect(hydratePanel, [hydratePanel]);

  useEffect(() => {
    const onPop = () => setView(onDesk() ? "desk" : "landing");
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const enterDesk = () => {
    window.history.pushState(null, "", `/desk${window.location.search}`);
    setView("desk");
  };

  const applyEvent = (evt: SseEvent) => {
    switch (evt.event) {
      case "token":
        setMessages((ms) => patchLast(ms, (m) => ({ ...m, text: m.text + evt.data.delta })));
        break;
      case "tool_call":
        setMessages((ms) =>
          patchLast(ms, (m) => ({
            ...m,
            chips: [...m.chips, { name: evt.data.name, args: evt.data.args, done: false }],
          }))
        );
        break;
      case "tool_result":
        setMessages((ms) =>
          patchLast(ms, (m) => {
            const chips = [...m.chips];
            const idx = chips.findLastIndex((c) => c.name === evt.data.name && !c.done);
            if (idx >= 0) chips[idx] = { ...chips[idx], done: true, summary: evt.data.summary };
            return { ...m, chips };
          })
        );
        break;
      case "panel":
        setPanel(evt.data);
        break;
      case "chain":
        setChainEvents((evts) => {
          // Append-only log; a `paid` event also flips this label's earlier
          // `armed` rows so the status pill transitions in place (B2.4).
          const next =
            evt.data.status === "paid"
              ? evts.map((e) =>
                  e.label === evt.data.label && e.status === "armed" ? { ...e, status: "paid" as const } : e
                )
              : evts;
          return [...next, evt.data];
        });
        break;
      case "error":
        setMessages((ms) => patchLast(ms, (m) => ({ ...m, error: evt.data.message })));
        break;
      case "done":
        conversationId.current = evt.data.conversation_id;
        break;
    }
  };

  const handleSend = async (message: string) => {
    setBusy(true);
    setMessages((ms) => [
      ...ms,
      { role: "user", text: message, chips: [] },
      { role: "assistant", text: "", chips: [] },
    ]);
    try {
      await streamChat(message, conversationId.current, applyEvent);
    } catch (err) {
      setMessages((ms) =>
        patchLast(ms, (m) => ({ ...m, error: err instanceof Error ? err.message : String(err) }))
      );
    } finally {
      setBusy(false);
    }
  };

  if (view === "landing") {
    return <Landing onEnter={enterDesk} />;
  }

  return (
    <div className="app">
      <section className="region chat-region">
        <header className="region-title">OptoPuts · desk chat</header>
        <Chat messages={messages} busy={busy} onSend={handleSend} />
      </section>
      <section className="region panel-region">
        <header className="region-title">pricing panel</header>
        <PricingPanel panel={panel} onSettingsSaved={hydratePanel} />
      </section>
      <section className="region chain-region">
        <header className="region-title">chain activity</header>
        <ChainStrip events={chainEvents} />
      </section>
    </div>
  );
}

function patchLast(ms: ChatMessage[], patch: (m: ChatMessage) => ChatMessage): ChatMessage[] {
  if (ms.length === 0) return ms;
  const last = ms[ms.length - 1];
  if (last.role !== "assistant") return ms;
  return [...ms.slice(0, -1), patch(last)];
}

export default App;
