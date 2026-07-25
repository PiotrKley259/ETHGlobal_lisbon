import { useEffect, useRef } from "react";

interface InkTransitionProps {
  onCovered: () => void; // fire when screen is fully inked → swap view under it
  onDone: () => void; // fire when the wash-off ends → unmount overlay
}

export const REDUCED_MOTION = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const COLS = 16;
const ROWS = 9;
const COVERED_MS = 220; // black snaps in fast → swap the view beneath
const DONE_MS = 1150; // last streak washed off

// deterministic pseudo-random in [0,1) — identical animation every run
const jitter = (i: number, salt: number) => ((i * salt) % 997) / 997;

// One effect only: the screen snaps to black ink, then the ink washes off
// downward in uneven streaky columns, like it's draining off glass. steps()
// timing throughout — pixel art, no smooth curves. The desk mounts at cover
// (220ms) so it's interactive for the whole wash-off.
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
    const col = i % COLS;
    const row = Math.floor(i / COLS);
    // wash-off: top rows clear first, but each column at its own uneven pace
    const delay =
      0.42 + jitter(col, 104729) * 0.16 + row * 0.038 + jitter(i, 31) * 0.05;
    return (
      <span key={i} className="ink-tile" style={{ animationDelay: `${delay.toFixed(3)}s` }} />
    );
  });

  return (
    <div className="ink" role="presentation">
      <div className="ink-grid">{tiles}</div>
      <button className="ink-skip" onClick={skip}>
        Skip animation
      </button>
    </div>
  );
}
