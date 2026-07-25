import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

// One-shot intro overlay: the octopus mascot pops in mid-screen, bobs,
// then vanishes — leaving a scatter of pixel-art coins (one per asset the
// desk quotes) that twinkle out. Pure CSS keyframes drive the timeline;
// we only unmount at the end.

const TOTAL_MS = 6200;

// Pixel-art coin icons on a 12-wide grid, one char per pixel ('.' = empty).
// Same grids drive the README GIF renderer — keep them in sync.
type CoinKind = "eth" | "wbtc" | "link" | "uni" | "aave";

const COIN_ART: Record<CoinKind, { glow: string; colors: Record<string, string>; grid: string[] }> = {
  // ETH diamond: dark/light facet split at the centre
  eth: {
    glow: "#58a6ff",
    colors: {
      d: "rgba(88,166,255,0.55)",
      l: "rgba(88,166,255,0.85)",
      D: "rgba(88,166,255,0.45)",
      L: "rgba(88,166,255,0.7)",
    },
    grid: [
      ".....dl.....",
      ".....dl.....",
      "....ddll....",
      "....ddll....",
      "...dddlll...",
      "...dddlll...",
      "..ddddllll..",
      "..ddddllll..",
      ".dddddlllll.",
      "ddddddllllll",
      "..ddddllll..",
      "....ddll....",
      ".....dl.....",
      "............",
      "DDDDDDLLLLLL",
      "..DDDDLLLL..",
      "...DDDLLL...",
      "....DDLL....",
      ".....DL.....",
    ],
  },
  // WBTC: orange coin, white ₿
  wbtc: {
    glow: "#f7931a",
    colors: { c: "#f7931a", b: "rgba(240,246,252,0.95)" },
    grid: [
      "...cccccc...",
      "..cccccccc..",
      ".cccccccccc.",
      ".cccbbbcccc.",
      ".cccbccbccc.",
      ".cccbccbccc.",
      ".cccbbbcccc.",
      ".cccbccbccc.",
      ".cccbccbccc.",
      ".cccbbbcccc.",
      ".cccccccccc.",
      "..cccccccc..",
      "...cccccc...",
    ],
  },
  // LINK: Chainlink hexagon ring
  link: {
    glow: "#4e7fff",
    colors: { x: "#4e7fff" },
    grid: [
      ".....xx.....",
      "...xxxxxx...",
      "..xxx..xxx..",
      ".xx......xx.",
      "xx........xx",
      "xx........xx",
      "xx........xx",
      "xx........xx",
      "xx........xx",
      ".xx......xx.",
      "..xxx..xxx..",
      "...xxxxxx...",
      ".....xx.....",
    ],
  },
  // UNI: pink coin with a golden unicorn horn
  uni: {
    glow: "#ff2d92",
    colors: { p: "#ff2d92", q: "#ff7ab8", h: "#ffd966" },
    grid: [
      "......hh....",
      ".....hh.....",
      "....hh......",
      "...pppppp...",
      "..ppqqpppp..",
      ".ppqqpppppp.",
      ".pppppppppp.",
      ".pppppppppp.",
      ".pppppppppp.",
      ".pppppppppp.",
      "..pppppppp..",
      "...pppppp...",
    ],
  },
  // AAVE: the ghost, eyes punched through to the background
  aave: {
    glow: "#2ebac6",
    colors: { g: "#2ebac6" },
    grid: [
      "...gggggg...",
      "..gggggggg..",
      ".gggggggggg.",
      ".gggggggggg.",
      ".ggeeggeegg.",
      ".ggeeggeegg.",
      ".gggggggggg.",
      ".gggggggggg.",
      ".gggggggggg.",
      ".gggggggggg.",
      ".gggggggggg.",
      ".gg..gg..gg.",
    ],
  },
};

// Coin scatter: fixed layout so the burst looks composed, not random-jittery.
// x/y are offsets (px) from the octopus centre, revealed as it disappears.
// ETH gets the big centre slot; every quoted asset appears at least once.
const COINS: { kind: CoinKind; x: number; y: number; scale: number; delay: number }[] = [
  { kind: "wbtc", x: -90, y: -20, scale: 1.0, delay: 0.0 },
  { kind: "uni", x: -45, y: 55, scale: 0.7, delay: 0.12 },
  { kind: "link", x: 0, y: -70, scale: 0.85, delay: 0.05 },
  { kind: "aave", x: 48, y: 40, scale: 1.1, delay: 0.18 },
  { kind: "eth", x: 95, y: -35, scale: 0.75, delay: 0.1 },
  { kind: "eth", x: -10, y: 15, scale: 1.3, delay: 0.0 },
  { kind: "uni", x: 55, y: -5, scale: 0.6, delay: 0.25 },
];

function PixelCoin({ kind }: { kind: CoinKind }) {
  const { glow, colors, grid } = COIN_ART[kind];
  const rects: React.ReactElement[] = [];
  grid.forEach((row, y) => {
    let x = 0;
    while (x < row.length) {
      const ch = row[x];
      if (!(ch in colors)) {
        x += 1;
        continue;
      }
      let end = x;
      while (end < row.length && row[end] === ch) end += 1;
      rects.push(<rect key={`${x},${y}`} x={x} y={y} width={end - x} height={1} fill={colors[ch]} />);
      x = end;
    }
  });
  return (
    <svg
      viewBox={`0 0 12 ${grid.length}`}
      width={24}
      height={grid.length * 2}
      className="pixel-coin-svg"
      style={{ color: glow }}
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      {rects}
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
        {COINS.map((c, i) => (
          <span
            key={i}
            className="pixel-coin"
            style={
              {
                transform: `translate(${c.x}px, ${c.y}px) scale(${c.scale}) translate(-50%, -50%)`,
                "--crystal-delay": `${c.delay}s`,
              } as CSSProperties
            }
          >
            <PixelCoin kind={c.kind} />
          </span>
        ))}
        <img src="/octopus.png" alt="" className="octo-sprite" />
      </div>
    </div>
  );
}
