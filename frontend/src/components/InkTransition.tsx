import { useEffect, useRef } from "react";
import { Octopus } from "./Octopus";

interface InkTransitionProps {
  onCovered: () => void; // fire when screen is fully inked → swap view under it
  onDone: () => void; // fire when the drain ends → unmount overlay
}

export const REDUCED_MOTION = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const COLS = 16;
const ROWS = 9;
const COVERED_MS = 460; // splatter fully opaque → swap the view beneath
const DONE_MS = 1350; // last drip retracted

// deterministic pseudo-random in [0,1) from an integer — same pattern every
// run, so the demo machine behaves exactly like rehearsal
const jitter = (i: number, salt: number) => ((i * salt) % 997) / 997;

// Octopus ink attack, in pixel language:
//   1. splatter — chunky tiles snap in RADIALLY from the octopus (center-low),
//      with flying pixel droplets ahead of the wave
//   2. blackout — bioluminescent flecks drift; the octopus itself flashes
//      in the dark like a culprit caught in torchlight
//   3. drain — ink slides off the glass top-down in uneven, streaky columns,
//      then a few hanging drips retract off the top edge
// steps() timing everywhere — no easing curves, this is pixel art. The desk
// mounts at cover (460ms) so it is interactive the moment the drain starts.
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
    // radial fill: distance from the splat origin (center, slightly low —
    // where the octopus sits) drives the delay, plus per-tile jitter
    const dx = (col + 0.5) / COLS - 0.5;
    const dy = (row + 0.5) / ROWS - 0.62;
    const dist = Math.sqrt(dx * dx + dy * dy) / 0.78; // ~0..1
    const delayIn = dist * 0.26 + jitter(i, 7919) * 0.07;
    // streaky drain: columns clear at uneven speeds (ink sliding off glass)
    const delayOut =
      0.56 + jitter(col, 104729) * 0.14 + row * 0.034 + jitter(i, 31) * 0.05;
    return (
      <span
        key={i}
        className="ink-tile"
        style={{ animationDelay: `${delayIn.toFixed(3)}s, ${delayOut.toFixed(3)}s` }}
      />
    );
  });

  const droplets = Array.from({ length: 9 }, (_, i) => {
    const angle = (i / 9) * Math.PI * 2 + jitter(i, 13) * 0.9;
    const reach = 34 + jitter(i, 41) * 28; // vh-ish reach
    return (
      <span
        key={i}
        className="ink-drop"
        style={
          {
            "--dx": `${(Math.cos(angle) * reach).toFixed(1)}vmin`,
            "--dy": `${(Math.sin(angle) * reach * 0.8 - 6).toFixed(1)}vmin`,
            animationDelay: `${(jitter(i, 61) * 0.08).toFixed(3)}s`,
          } as React.CSSProperties
        }
      />
    );
  });

  const drips = Array.from({ length: 7 }, (_, i) => (
    <span
      key={i}
      className="ink-driphang"
      style={{
        left: `${(6 + i * 13 + jitter(i, 89) * 8).toFixed(1)}%`,
        height: `${(6 + jitter(i, 53) * 11).toFixed(1)}vh`,
        animationDelay: `${(0.98 + jitter(i, 23) * 0.16).toFixed(3)}s`,
      }}
    />
  ));

  return (
    <div className="ink" role="presentation">
      <div className="ink-grid">{tiles}</div>
      <div className="ink-droplets">{droplets}</div>
      <div className="ink-flecks">
        <span className="fleck f1" />
        <span className="fleck f2" />
        <span className="fleck f3" />
        <span className="fleck f4" />
        <span className="fleck f5" />
        <span className="fleck f6" />
        <span className="ink-octo">
          <Octopus />
        </span>
      </div>
      <div className="ink-drips">{drips}</div>
      <button className="ink-skip" onClick={skip}>
        Skip animation
      </button>
    </div>
  );
}
