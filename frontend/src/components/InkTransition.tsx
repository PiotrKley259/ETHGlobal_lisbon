import { useEffect, useRef } from "react";

interface InkTransitionProps {
  onCovered: () => void; // fire when screen is fully inked → swap view under it
  onDone: () => void; // fire when the drain ends → unmount overlay
}

export const REDUCED_MOTION = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const COLS = 12;
const ROWS = 7;
const COVERED_MS = 450; // all tiles opaque by here → swap the view beneath
const DONE_MS = 1000; // last tile drained

// 8-bit ink transition: the screen fills with chunky pixel tiles in a
// scattered order (steps() timing, no easing curves — this is pixel art),
// holds a beat with bioluminescent flecks, then drains top-down row by row.
// Plays on every "Try demo" click; the desk mounts at cover so it is
// interactive the moment the drain starts. Reduced-motion skips it entirely
// (handled by the caller).
export function InkTransition({ onCovered, onDone }: InkTransitionProps) {
  const covered = useRef(false);
  const timers = useRef<number[]>([]);

  const skip = () => {
    timers.current.forEach(clearTimeout);
    if (!covered.current) {
      covered.current = true;
      onCovered();
    }
    onDone();
  };

  useEffect(() => {
    timers.current = [
      window.setTimeout(() => {
        covered.current = true;
        onCovered();
      }, COVERED_MS),
      window.setTimeout(onDone, DONE_MS),
    ];
    return () => timers.current.forEach(clearTimeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const tiles = Array.from({ length: COLS * ROWS }, (_, i) => {
    const row = Math.floor(i / COLS);
    // deterministic pseudo-random scatter for fill; top-down jittered drain
    const delayIn = (((i * 7919) % 13) / 13) * 0.3;
    const delayOut = 0.5 + row * 0.05 + (((i * 104729) % 7) / 7) * 0.06;
    return (
      <span
        key={i}
        className="ink-tile"
        style={{ animationDelay: `${delayIn.toFixed(3)}s, ${delayOut.toFixed(3)}s` }}
      />
    );
  });

  return (
    <div className="ink" role="presentation">
      <div className="ink-grid">{tiles}</div>
      <div className="ink-flecks">
        <span className="fleck f1" />
        <span className="fleck f2" />
        <span className="fleck f3" />
        <span className="fleck f4" />
        <span className="fleck f5" />
        <span className="fleck f6" />
      </div>
      <button className="ink-skip" onClick={skip}>
        Skip animation
      </button>
    </div>
  );
}
