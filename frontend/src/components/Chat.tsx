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
  onSend: (message: string) => void;
}

// B2.1 — chat column: streamed tokens plus tool-call chips (name flashes while
// the tool runs, collapses to a badge with the result summary).
export function Chat({ messages, busy, onSend }: ChatProps) {
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
          <p className="chat-empty">
            Ask the desk something — e.g. “Protect my ETH below $2,800 through
            next Friday.”
          </p>
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
