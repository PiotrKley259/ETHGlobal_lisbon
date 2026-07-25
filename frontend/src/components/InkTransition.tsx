import { useEffect, useRef } from "react";

interface InkTransitionProps {
  onCovered: () => void; // fire when screen is fully inked → swap view under it
  onDone: () => void; // fire when recede ends → unmount overlay
}

export const REDUCED_MOTION = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export const INK_SEEN_KEY = "optoputs_ink_seen";

// Octopus defense sequence (brief v3): burst 180ms → flood 340ms → recede
// 520ms, 1040ms total. The desk is mounted at "covered" (520ms), so the CTA
// is interactive the instant recede begins — the overlay stops catching
// pointer events at that point. Skippable; instant on repeat visits and under
// prefers-reduced-motion (handled by the caller via shouldInk()).
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
      }, 520), // burst 180 + flood 340
      window.setTimeout(onDone, 1040), // + recede 520
    ];
    localStorage.setItem(INK_SEEN_KEY, "1");
    return () => timers.current.forEach(clearTimeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="ink" role="presentation">
      {/* irregular pixel-noise blobs erupting from center-ish */}
      <div className="ink-burst">
        <span className="blob b1" />
        <span className="blob b2" />
        <span className="blob b3" />
        <span className="blob b4" />
        <span className="blob b5" />
      </div>
      {/* full flood with bioluminescent flecks */}
      <div className="ink-flood">
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
