import { useEffect, useRef } from "react";
import type { CSSProperties } from "react";

interface InkTransitionProps {
  onCovered: () => void; // fire when screen is fully inked → swap view under it
  onDone: () => void; // fire when the wash-off ends → unmount overlay
}

export const REDUCED_MOTION = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const COLS = 16;
const ROWS = 9;
const COVERED_MS = 380; // spray + sheet fully cover → swap the view beneath
const DONE_MS = 1550; // last rivulet gone

// deterministic pseudo-random in [0,1) — identical animation every run
const jitter = (i: number, salt: number) => ((i * salt) % 997) / 997;

// Ink sprayed onto the page, then washing off:
//   1. spray (0–350ms) — irregular pixel splats stamp across the screen in
//      rapid fire; a full ink sheet snaps in beneath them to seal coverage
//   2. wash (600ms+) — the sheet drains top-down in uneven streaky columns,
//      every chunk smearing one frame downward as it lets go
//   3. rivulets — thin runners race down the glass behind the receding ink
// steps() timing only — realistic motion, pixel grammar. The desk mounts at
// cover (380ms) and is interactive throughout the wash.
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

  const splats = Array.from({ length: 14 }, (_, i) => {
    const style: CSSProperties & Record<string, string> = {
      left: `${(jitter(i, 383) * 92 + 4).toFixed(1)}%`,
      top: `${(jitter(i, 653) * 86 + 5).toFixed(1)}%`,
      "--s": (2.6 + jitter(i, 101) * 3.4).toFixed(2),
      "--r": `${Math.floor(jitter(i, 29) * 360)}deg`,
      "--d": `${(jitter(i, 811) * 0.26).toFixed(3)}s`,
    };
    return <span key={i} className="ink-splat" style={style} />;
  });

  const tiles = Array.from({ length: COLS * ROWS }, (_, i) => {
    const col = i % COLS;
    const row = Math.floor(i / COLS);
    // wash-off: top rows first, each column at its own uneven pace
    const delay =
      0.6 + jitter(col, 104729) * 0.17 + row * 0.038 + jitter(i, 31) * 0.05;
    return (
      <span key={i} className="ink-tile" style={{ animationDelay: `${delay.toFixed(3)}s` }} />
    );
  });

  const runners = Array.from({ length: 10 }, (_, i) => (
    <span
      key={i}
      className="ink-runner"
      style={{
        left: `${(jitter(i, 271) * 94 + 3).toFixed(1)}%`,
        height: `${(18 + jitter(i, 47) * 22).toFixed(1)}vh`,
        width: `${2 + Math.floor(jitter(i, 7) * 3)}px`,
        animationDelay: `${(0.72 + jitter(i, 149) * 0.4).toFixed(3)}s`,
      }}
    />
  ));

  return (
    <div className="ink" role="presentation">
      <div className="ink-splats">{splats}</div>
      <div className="ink-grid">{tiles}</div>
      <div className="ink-runners">{runners}</div>
      <button className="ink-skip" onClick={skip}>
        Skip animation
      </button>
    </div>
  );
}
