import { useEffect, useRef } from "react";
import type { ChainEvent } from "../types";

const KIND_GLYPH: Record<ChainEvent["kind"], string> = {
  mint: "◆",
  hcs: "≡",
  schedule: "⏱",
  settle: "$",
};

// B2.4 — chain activity strip: append-only terminal log of `chain` SSE events.
// Status pills go armed → paid in place (App flips earlier rows on a paid
// event for the same label); every row links out to Hashscan.
export function ChainStrip({ events }: { events: ChainEvent[] }) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [events]);

  return (
    <div className="chain-scroll" ref={scrollRef}>
      {events.length === 0 && (
        <p className="placeholder">no on-chain activity yet; mint an option to see it here</p>
      )}
      {events.map((evt, i) => (
        <div key={i} className="chain-row">
          <span className="chain-kind">
            {KIND_GLYPH[evt.kind]} {evt.kind}
          </span>
          <span className="chain-label">{evt.label}</span>
          <a className="chain-link" href={evt.hashscan_url} target="_blank" rel="noreferrer">
            {evt.id}
          </a>
          <span className={`pill pill-${evt.status}`}>{evt.status}</span>
        </div>
      ))}
    </div>
  );
}
