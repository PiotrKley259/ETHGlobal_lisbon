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

// Pixel-art Ethereum diamond on a 12x19 grid: per-row column spans
// [first, last], split at the centre into a dark and a light facet.
const CRYSTAL_TOP: [number, number][] = [
  [5, 6], [5, 6], [4, 7], [4, 7], [3, 8], [3, 8], [2, 9], [2, 9],
  [1, 10], [0, 11], [2, 9], [4, 7], [5, 6],
];
const CRYSTAL_BOTTOM: [number, number][] = [[0, 11], [2, 9], [3, 8], [4, 7], [5, 6]];

function EthCrystal() {
  const rows = [
    ...CRYSTAL_TOP.map(([a, b], r) => ({ a, b, y: r, left: 0.55, right: 0.85 })),
    ...CRYSTAL_BOTTOM.map(([a, b], r) => ({ a, b, y: r + 14, left: 0.45, right: 0.7 })),
  ];
  return (
    <svg viewBox="0 0 12 19" className="eth-crystal-svg" shapeRendering="crispEdges" aria-hidden="true">
      {rows.map(({ a, b, y, left, right }) => (
        <g key={y}>
          <rect x={a} y={y} width={6 - a} height={1} fill="currentColor" opacity={left} />
          <rect x={6} y={y} width={b - 5} height={1} fill="currentColor" opacity={right} />
        </g>
      ))}
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
