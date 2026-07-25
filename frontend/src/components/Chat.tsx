import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

export interface ToolChip {
  name: string;
  args?: Record<string, unknown>;
  summary?: string;
  done: boolean;
}

export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  chips: ToolChip[];
  error?: string;
}

interface ChatProps {
  messages: ChatMessage[];
  busy: boolean;
  connected: boolean; // market feed hydrated — drives the boot-log status line
  onSend: (message: string) => void;
}

const STARTER_PROMPTS = [
  "Protect my ETH below $2,800 through next Friday",
  "Price a WBTC straddle expiring in 7 days",
  "What's the vol regime right now?",
];

// B2.1 — chat column: streamed tokens plus tool-call chips (name flashes while
// the tool runs, collapses to a badge with the result summary).
export function Chat({ messages, busy, connected, onSend }: ChatProps) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const message = draft.trim();
    if (!message || busy) return;
    setDraft("");
    onSend(message);
  };

  return (
    <>
      <div className="chat-scroll" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="chat-empty">
            <div className="boot-log" aria-hidden="true">
              <span className="boot-title">OPTOPUTS DESK v1.0</span>
              <span>&gt; vol engine ....... deterministic Black–Scholes</span>
              <span>&gt; market data ...... {connected ? "live · The Graph" : "connecting…"}</span>
              <span>&gt; settlement ....... Hedera testnet</span>
              <span>
                &gt; awaiting instruction <span className="boot-cursor">█</span>
              </span>
            </div>
            <div className="starter-prompts">
              {STARTER_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="starter-prompt"
                  disabled={busy}
                  onClick={() => onSend(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
            <p className="starter-hint">…or type your own request below</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`msg msg-${msg.role}`}>
            {msg.chips.length > 0 && (
              <div className="chips">
                {msg.chips.map((chip, j) => (
                  <span key={j} className={`chip ${chip.done ? "chip-done" : "chip-running"}`}>
                    {chip.name}
                    {chip.done && chip.summary ? ` · ${chip.summary}` : "…"}
                  </span>
                ))}
              </div>
            )}
            {msg.text && <div className="msg-text">{msg.text}</div>}
            {msg.error && <div className="msg-error">⚠ {msg.error}</div>}
          </div>
        ))}
      </div>
      <form className="chat-input" onSubmit={submit}>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={busy ? "desk is working…" : "type a request"}
          disabled={busy}
        />
        <button type="submit" disabled={busy || !draft.trim()}>
          send
        </button>
      </form>
    </>
  );
}
