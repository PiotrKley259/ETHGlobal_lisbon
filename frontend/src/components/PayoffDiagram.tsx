import type { StrategyQuote } from "../types";

const W = 320;
const H = 170;
const PAD = { top: 14, right: 12, bottom: 22, left: 44 };

const fmt = (x: number) =>
  Math.abs(x) >= 1000 ? x.toLocaleString("en-US", { maximumFractionDigits: 0 }) : x.toFixed(0);

// B2.3 — the "options for non-experts" money shot: P/L at expiry vs terminal
// ETH price from payoff.prices/pnl, profit green / loss red, breakevens and
// max P/L marked. Hand-rolled SVG so it renders instantly.
export function PayoffDiagram({ strategy }: { strategy: StrategyQuote }) {
  const { prices, pnl } = strategy.payoff;
  if (prices.length < 2 || pnl.length !== prices.length) return null;

  const x0 = prices[0];
  const x1 = prices[prices.length - 1];
  const yMin = Math.min(...pnl, 0);
  const yMax = Math.max(...pnl, 0);
  const ySpan = yMax - yMin || 1;
  const yPad = ySpan * 0.08;

  const sx = (p: number) => PAD.left + ((p - x0) / (x1 - x0)) * (W - PAD.left - PAD.right);
  const sy = (v: number) =>
    H - PAD.bottom - ((v - (yMin - yPad)) / (ySpan + 2 * yPad)) * (H - PAD.top - PAD.bottom);

  const line = prices.map((p, i) => `${i === 0 ? "M" : "L"}${sx(p).toFixed(1)},${sy(pnl[i]).toFixed(1)}`).join(" ");
  const zeroY = sy(0);
  const area = `${line} L${sx(x1).toFixed(1)},${zeroY.toFixed(1)} L${sx(x0).toFixed(1)},${zeroY.toFixed(1)} Z`;

  return (
    <svg
      className="payoff"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="strategy payoff at expiry"
    >
      <defs>
        <clipPath id="clip-profit">
          <rect x="0" y="0" width={W} height={zeroY} />
        </clipPath>
        <clipPath id="clip-loss">
          <rect x="0" y={zeroY} width={W} height={H - zeroY} />
        </clipPath>
      </defs>

      <path d={area} className="payoff-area-profit" clipPath="url(#clip-profit)" />
      <path d={area} className="payoff-area-loss" clipPath="url(#clip-loss)" />

      {/* zero P/L axis */}
      <line x1={PAD.left} y1={zeroY} x2={W - PAD.right} y2={zeroY} className="payoff-zero" />
      <path d={line} className="payoff-line" />

      {/* breakevens: dashed verticals + price labels */}
      {strategy.breakevens.map((be) => (
        <g key={be}>
          <line x1={sx(be)} y1={PAD.top} x2={sx(be)} y2={H - PAD.bottom} className="payoff-be" />
          <text x={sx(be)} y={H - PAD.bottom + 12} className="payoff-tick" textAnchor="middle">
            {fmt(be)}
          </text>
        </g>
      ))}

      {/* y extremes: max profit / max loss */}
      <text x={PAD.left - 4} y={sy(yMax) + 4} className="payoff-tick" textAnchor="end">
        {strategy.max_profit === null ? "+∞" : `+${fmt(yMax)}`}
      </text>
      <text x={PAD.left - 4} y={sy(yMin) + 4} className="payoff-tick" textAnchor="end">
        {fmt(yMin)}
      </text>
      <text x={PAD.left - 4} y={zeroY + 4} className="payoff-tick" textAnchor="end">
        0
      </text>

      {/* x range labels */}
      <text x={sx(x0)} y={H - PAD.bottom + 12} className="payoff-tick" textAnchor="start">
        {fmt(x0)}
      </text>
      <text x={sx(x1)} y={H - PAD.bottom + 12} className="payoff-tick" textAnchor="end">
        {fmt(x1)}
      </text>
    </svg>
  );
}
