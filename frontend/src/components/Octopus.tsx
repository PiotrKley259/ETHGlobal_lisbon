// 8-bit octopus, hand-placed on a 16×14 grid rendered as SVG rects
// (crisp at any scale — the SVG equivalent of image-rendering: pixelated).
// Palette only: B=b91372 body, G=fa198b glow, D=6b0f1a shade, K=0e0004 pupil.
// Two eye/arm frames: idle and "alert" (hover on the CTA widens the eyes and
// curls the arm tips inward, per the brief).

const COLORS: Record<string, string> = {
  B: "#b91372",
  G: "#fa198b",
  D: "#6b0f1a",
  K: "#0e0004",
};

const IDLE = [
  "....BBBBBBBB....",
  "...BBBBBBBBBB...",
  "..BBBBBBBBBBBB..",
  "..BBGGBBBBGGBB..",
  "..BGKGGBBGKGGB..",
  "..BBGGBBBBGGBB..",
  "..BBBBBDDBBBBB..",
  "..BBBBBBBBBBBB..",
  "...BBBBBBBBBB...",
  "..B.BB.BB.BB.B..",
  "..B.BB.BB.BB.B..",
  ".BB.BB.BB.BB.BB.",
  ".B..B...B...B.B.",
  "DB..B...B...B.BD",
];

const ALERT = [
  "....BBBBBBBB....",
  "...BBBBBBBBBB...",
  "..BBGGGBBGGGBB..",
  "..BGGGGBBGGGGB..",
  "..BGKKGBBGKKGB..",
  "..BGGGGBBGGGGB..",
  "..BBBBBDDBBBBB..",
  "..BBBBBBBBBBBB..",
  "...BBBBBBBBBB...",
  "...BBB.BB.BBB...",
  "..B.BB.BB.BB.B..",
  "..BB.B.BB.B.BB..",
  "...B.BB..BB.B...",
  "...DB......BD...",
];

function Frame({ rows }: { rows: string[] }) {
  const rects = [];
  for (let y = 0; y < rows.length; y++) {
    for (let x = 0; x < rows[y].length; x++) {
      const c = rows[y][x];
      if (c !== ".") {
        rects.push(<rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} fill={COLORS[c]} />);
      }
    }
  }
  return <>{rects}</>;
}

// Rendered size comes from CSS (.octopus width/height); mobile 64px, ≥768px 128px.
export function Octopus() {
  return (
    <span className="octopus" aria-hidden="true">
      <svg viewBox="0 0 16 14" shapeRendering="crispEdges" className="octo-frame octo-idle">
        <Frame rows={IDLE} />
      </svg>
      <svg viewBox="0 0 16 14" shapeRendering="crispEdges" className="octo-frame octo-alert">
        <Frame rows={ALERT} />
      </svg>
    </span>
  );
}
