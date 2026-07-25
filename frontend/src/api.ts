import type { PanelState, Settings, SseEvent } from "./types";

// One env swap points the app at the real backend instead of the mock server
// (I1.3) — the protocol is identical by contract.
export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";

// Public-deploy gate (CONTRACTS §3): a demo key arrives once via ?key=... in
// the judges' link. Stash it in sessionStorage and scrub it from the address
// bar so it doesn't linger in the visible URL or browser history. Never bake
// a key into the bundle — anything in the build is public.
const DEMO_KEY_STORAGE = "optoputs_demo_key";

function demoKey(): string | null {
  const params = new URLSearchParams(window.location.search);
  const fromUrl = params.get("key");
  if (fromUrl) {
    sessionStorage.setItem(DEMO_KEY_STORAGE, fromUrl);
    params.delete("key");
    const query = params.size > 0 ? `?${params}` : "";
    window.history.replaceState(null, "", `${window.location.pathname}${query}`);
  }
  return sessionStorage.getItem(DEMO_KEY_STORAGE);
}

// POST /chat streams text/event-stream (CONTRACTS §3). EventSource can't POST,
// so parse the stream by hand: blocks separated by blank lines, each with
// `event:` and `data:` lines.
export async function streamChat(
  message: string,
  conversationId: string | null,
  onEvent: (evt: SseEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const key = demoKey();
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(key ? { "X-Demo-Key": key } : {}),
    },
    body: JSON.stringify({ message, conversation_id: conversationId }),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(
      res.status === 401
        ? "this demo is key-gated — open it via the invite link (with ?key=...)"
        : `chat request failed: HTTP ${res.status}`
    );
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

// GET/POST /settings — user regime bands (CONTRACTS §3). POST returns 422 on
// invalid bands; surface the message to the settings menu.
export async function getSettings(): Promise<Settings> {
  const res = await fetch(`${API_BASE}/settings`);
  if (!res.ok) throw new Error(`GET /settings failed: HTTP ${res.status}`);
  return res.json();
}

export async function postSettings(settings: Settings): Promise<Settings> {
  const res = await fetch(`${API_BASE}/settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail?.[0]?.msg ?? body?.error ?? `HTTP ${res.status}`);
  }
  return res.json();
}
