import type { PanelState, SseEvent } from "./types";

// One env swap points the app at the real backend instead of the mock server
// (I1.3) — the protocol is identical by contract.
export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";

// POST /chat streams text/event-stream (CONTRACTS §3). EventSource can't POST,
// so parse the stream by hand: blocks separated by blank lines, each with
// `event:` and `data:` lines.
export async function streamChat(
  message: string,
  conversationId: string | null,
  onEvent: (evt: SseEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`chat request failed: HTTP ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const evt = parseSseBlock(block);
      if (evt) onEvent(evt);
    }
  }
}

function parseSseBlock(block: string): SseEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const rawLine of block.split("\n")) {
    const line = rawLine.replace(/\r$/, "");
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (dataLines.length === 0) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) } as SseEvent;
  } catch {
    return null; // malformed frame — skip rather than kill the stream
  }
}

// GET /panel — page-load hydration of the pricing panel.
export async function getPanel(): Promise<PanelState> {
  const res = await fetch(`${API_BASE}/panel`);
  if (!res.ok) throw new Error(`GET /panel failed: HTTP ${res.status}`);
  return res.json();
}
