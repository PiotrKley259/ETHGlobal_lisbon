import type { PayoffCurve } from "../types";

const W = 320;
const H = 200;
const PAD = { top: 18, right: 14, bottom: 40, left: 50 };

const fmt = (x: number) =>
  Math.abs(x) >= 1000 ? x.toLocaleString("en-US", { maximumFractionDigits: 0 }) : x.toFixed(0);

/** ~`count` round tick values (1/2/5 × 10^n steps) spanning [min, max] */
function niceTicks(min: number, max: number, count: number): number[] {
  const span = max - min;
  if (span <= 0) return [min];
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const step = (norm < 1.5 ? 1 : norm < 3.5 ? 2 : norm < 7.5 ? 5 : 10) * mag;
  const out: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step / 1e6; v += step) {
    out.push(Math.abs(v) < step / 1e6 ? 0 : v);
  }
  return out;
}

// B2.3 — the "options for non-experts" money shot: P/L at expiry vs terminal
// price from payoff.prices/pnl, profit green / loss red, real axes with round
// ticks + gridlines, breakevens and unbounded sides marked. Hand-rolled SVG.
export function PayoffDiagram({ strategy }: { strategy: PayoffCurve }) {
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

  const xTicks = niceTicks(x0, x1, 4);
  const yTicks = niceTicks(yMin, yMax, 3);
  const axisY = H - PAD.bottom;

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

      {/* gridlines behind everything */}
      {yTicks.map((t) => (
        <line key={`gy${t}`} x1={PAD.left} y1={sy(t)} x2={W - PAD.right} y2={sy(t)} className="payoff-grid" />
      ))}
      {xTicks.map((t) => (
        <line key={`gx${t}`} x1={sx(t)} y1={PAD.top} x2={sx(t)} y2={axisY} className="payoff-grid" />
      ))}

      <path d={area} className="payoff-area-profit" clipPath="url(#clip-profit)" />
      <path d={area} className="payoff-area-loss" clipPath="url(#clip-loss)" />

      {/* zero P/L reference */}
      <line x1={PAD.left} y1={zeroY} x2={W - PAD.right} y2={zeroY} className="payoff-zero" />
      <path d={line} className="payoff-line" />

      {/* axes */}
      <line x1={PAD.left} y1={PAD.top} x2={PAD.left} y2={axisY} className="payoff-axis" />
      <line x1={PAD.left} y1={axisY} x2={W - PAD.right} y2={axisY} className="payoff-axis" />

      {/* y ticks: P&L in $ */}
      {yTicks.map((t) => (
        <g key={`y${t}`}>
          <line x1={PAD.left - 3} y1={sy(t)} x2={PAD.left} y2={sy(t)} className="payoff-axis" />
          <text x={PAD.left - 6} y={sy(t) + 3} className="payoff-tick" textAnchor="end">
            {t > 0 ? `+${fmt(t)}` : fmt(t)}
          </text>
        </g>
      ))}

      {/* x ticks: terminal price */}
      {xTicks.map((t) => (
        <g key={`x${t}`}>
          <line x1={sx(t)} y1={axisY} x2={sx(t)} y2={axisY + 3} className="payoff-axis" />
          <text x={sx(t)} y={axisY + 13} className="payoff-tick" textAnchor="middle">
            {fmt(t)}
          </text>
        </g>
      ))}

      {/* axis titles */}
      <text
        x={12}
        y={(PAD.top + axisY) / 2}
        className="payoff-axis-title"
        textAnchor="middle"
        transform={`rotate(-90 12 ${(PAD.top + axisY) / 2})`}
      >
        P&amp;L at expiry ($)
      </text>
      <text x={(PAD.left + W - PAD.right) / 2} y={H - 6} className="payoff-axis-title" textAnchor="middle">
        price at expiry ($)
      </text>

      {/* breakevens: dashed verticals, labels at the top edge (off the tick row) */}
      {strategy.breakevens.map((be) => (
        <g key={be}>
          <line x1={sx(be)} y1={PAD.top} x2={sx(be)} y2={axisY} className="payoff-be" />
          <text x={sx(be)} y={PAD.top - 4} className="payoff-be-label" textAnchor="middle">
            {fmt(be)}
          </text>
        </g>
      ))}

      {/* unbounded-side badges */}
      {strategy.max_profit === null && (
        <text x={W - PAD.right - 2} y={PAD.top + 10} className="payoff-tick" textAnchor="end">
          +∞
        </text>
      )}
      {strategy.max_loss === null && (
        <text x={W - PAD.right - 2} y={axisY - 4} className="payoff-tick" textAnchor="end">
          −∞
        </text>
      )}
    </svg>
  );
}
