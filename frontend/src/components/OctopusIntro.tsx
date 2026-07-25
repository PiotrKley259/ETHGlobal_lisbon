import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

// One-shot intro overlay: the octopus mascot pops in mid-screen, bobs,
// then vanishes — leaving a scatter of ETH crystals that twinkle out.
// Pure CSS keyframes drive the timeline; we only unmount at the end.

const TOTAL_MS = 6200;

// Crystal scatter: fixed layout so the burst looks composed, not random-jittery.
// x/y are offsets (px) from the octopus centre, revealed as it disappears.
const CRYSTALS = [
  { x: -90, y: -20, scale: 1.0, delay: 0.0 },
  { x: -45, y: 55, scale: 0.7, delay: 0.12 },
  { x: 0, y: -70, scale: 0.85, delay: 0.05 },
  { x: 48, y: 40, scale: 1.1, delay: 0.18 },
  { x: 95, y: -35, scale: 0.75, delay: 0.1 },
  { x: -10, y: 15, scale: 1.3, delay: 0.0 },
  { x: 55, y: -5, scale: 0.6, delay: 0.25 },
];

function EthCrystal() {
  // Stylised Ethereum diamond: two facet pairs with different opacities.
  return (
    <svg viewBox="0 0 24 38" className="eth-crystal-svg" aria-hidden="true">
      <polygon points="12,0 22,19 12,25" fill="currentColor" opacity="0.85" />
      <polygon points="12,0 2,19 12,25" fill="currentColor" opacity="0.55" />
      <polygon points="12,28 22,22 12,38" fill="currentColor" opacity="0.7" />
      <polygon points="12,28 2,22 12,38" fill="currentColor" opacity="0.45" />
    </svg>
  );
}

export function OctopusIntro() {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const t = setTimeout(() => setVisible(false), TOTAL_MS);
    return () => clearTimeout(t);
  }, []);

  if (!visible) return null;

  return (
    <div className="octo-overlay" aria-hidden="true">
      <div className="octo-stage">
        {CRYSTALS.map((c, i) => (
          <span
            key={i}
            className="eth-crystal"
            style={
              {
                transform: `translate(${c.x}px, ${c.y}px) scale(${c.scale})`,
                "--crystal-delay": `${c.delay}s`,
              } as CSSProperties
            }
          >
            <EthCrystal />
          </span>
        ))}
        <img src="/octopus.png" alt="" className="octo-sprite" />
      </div>
    </div>
  );
}
