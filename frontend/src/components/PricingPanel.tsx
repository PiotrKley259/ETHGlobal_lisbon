import { useState } from "react";
import type { Greeks, PanelState } from "../types";
import { PayoffDiagram } from "./PayoffDiagram";
import { SettingsMenu } from "./SettingsMenu";

interface PricingPanelProps {
  panel: PanelState | null;
  onSettingsSaved: () => void;
}

const fmtUsd = (x: number) =>
  x.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtPct = (x: number) => `${(x * 100).toFixed(1)}%`;

const WINDOW_HOURS: Record<string, number> = { "24h": 24, "7d": 168, "30d": 720 };
// 1-sigma move over the window itself — served by the backend; derived here
// only for older payloads (mock fixtures) that predate sigma_period.
const periodMove = (v: { sigma_annual: number; sigma_period?: number; window: string }) =>
  v.sigma_period ?? v.sigma_annual * Math.sqrt((WINDOW_HOURS[v.window] ?? 24) / 8760);

// B2.2 — live pricing panel: spot, vol term-structure bars, regime badge with
// active bands in the tooltip, rate source line, and on a quote the price +
// Greeks grid. Renders whatever the panel event carries — nulls collapse.
export function PricingPanel({ panel, onSettingsSaved }: PricingPanelProps) {
  const [settingsOpen, setSettingsOpen] = useState(false);

  const regime = panel?.regime ?? null;
  const bandsTip = regime
    ? `bands: calm < ${fmtPct(regime.bands.calm)} ≤ elevated < ${fmtPct(regime.bands.elevated)} ≤ stressed` +
      ` (stressed = top ${fmtPct(1 - regime.bands.elevated)})`
    : undefined;
  const maxSigma = Math.max(0.0001, ...(panel?.vols ?? []).map((v) => v.sigma_annual));

  return (
    <div className="panel-body">
      <button
        className="gear"
        title="regime band settings"
        onClick={() => setSettingsOpen((o) => !o)}
      >
        ⚙
      </button>
      {settingsOpen && (
        <SettingsMenu onSaved={onSettingsSaved} onClose={() => setSettingsOpen(false)} />
      )}

      {!panel && <p className="placeholder">no data yet; ask the desk for a quote</p>}

      {panel?.spot && (
        <div className="panel-row spot-row">
          <span className="big">{panel.asset ?? "ETH"} ${fmtUsd(panel.spot.price)}</span>
          <span className="dim">{panel.spot.source}</span>
        </div>
      )}

      {panel?.vols && panel.vols.length > 0 && (
        <div className="vol-bars">
          {panel.vols.map((v) => (
            <div
              key={v.window}
              className="vol-bar-row"
              title={`typical ±move over ${v.window} · ${fmtPct(v.sigma_annual)} annualized · ${v.estimator}, n=${v.n_obs}`}
            >
              <span className="vol-label">{v.window}</span>
              <div className="vol-track">
                {/* bar heights stay ANNUALIZED so the term-structure shape
                    (contango/backwardation) remains readable */}
                <div
                  className="vol-fill"
                  style={{ width: `${(v.sigma_annual / maxSigma) * 100}%` }}
                />
              </div>
              <span className="vol-value">±{fmtPct(periodMove(v))}</span>
              <span className="dim vol-annualized">{fmtPct(v.sigma_annual)} ann.</span>
            </div>
          ))}
        </div>
      )}

      {regime && (
        <div className="panel-row">
          <span className={`regime-badge regime-${regime.regime}`} title={bandsTip}>
            {regime.regime} · p{Math.round(regime.percentile * 100)}
          </span>
          <span className="dim">7d vol vs trailing 30d</span>
        </div>
      )}

      {panel?.rate && (
        <div className="quote-specs">
          <SpecCell
            label="rate · r"
            value={`${fmtPct(panel.rate.rate_cc)}${panel.rate.fallback_level > 0 ? ` · L${panel.rate.fallback_level}` : ""}`}
            def={`Risk-free rate (r), continuously compounded: the financing leg of the price. Source: ${panel.rate.source}${panel.rate.fallback_level > 0 ? ` (fallback level ${panel.rate.fallback_level})` : ""}.`}
          />
        </div>
      )}

      {panel?.quote && (
        <div className="quote-block">
          <div className="panel-row">
            <span className="big">${fmtUsd(panel.quote.price)}</span>
            <span className="dim" title="Premium: what this option costs now.">
              premium
            </span>
          </div>
          <div className="quote-specs">
            <SpecCell
              label="strike · K"
              value={`$${fmtUsd(panel.quote.inputs.K)}`}
              def="Strike (K): the price level the option pays out around at expiry."
            />
            <SpecCell
              label="expiry · T"
              value={`${panel.quote.inputs.T_days}d`}
              def="Time to expiry (T): how long the protection or bet runs, in days."
            />
            <SpecCell
              label="vol · σ"
              value={fmtPct(panel.quote.inputs.sigma)}
              def={`Volatility (σ): annualized realized volatility fed into Black-Scholes. Source: ${panel.quote.inputs.sigma_source}.`}
            />
          </div>
          <GreeksGrid greeks={panel.quote.greeks} />
          {panel.quote.payoff && panel.quote.breakevens && (
            <PayoffDiagram
              strategy={{
                payoff: panel.quote.payoff,
                breakevens: panel.quote.breakevens,
                max_profit: panel.quote.max_profit ?? null,
                max_loss: panel.quote.max_loss ?? null,
              }}
            />
          )}
        </div>
      )}

      {panel?.strategy && (
        <div className="quote-block">
          <div className="panel-row">
            <span className="big">${fmtUsd(panel.strategy.net_cost)}</span>
            <span className="dim" title="Net cost of the whole strategy: debit if positive, credit if negative.">
              net cost
            </span>
          </div>
          <div className="quote-specs">
            <SpecCell
              label="max profit"
              value={panel.strategy.max_profit === null ? "+∞" : `$${fmtUsd(panel.strategy.max_profit)}`}
              def="Best case at expiry. +∞ means the upside is unbounded."
            />
            <SpecCell
              label="max loss"
              value={panel.strategy.max_loss === null ? "−∞" : `$${fmtUsd(panel.strategy.max_loss)}`}
              def="Worst case at expiry. −∞ means the downside is unbounded."
            />
          </div>
          <GreeksGrid greeks={panel.strategy.net_greeks} />
          <PayoffDiagram strategy={panel.strategy} />
        </div>
      )}
    </div>
  );
}

// plain-language definitions, hover tooltips; units match CONTRACTS §1
// (vega per 1.00 of vol, theta per calendar day, rho per 1.00 of rate)
const GREEK_DEFS: Record<string, string> = {
  "Δ": "Delta: how much the option price changes when the underlying moves $1. Also reads as directional exposure: Δ −0.25 behaves like being short a quarter unit.",
  "Γ": "Gamma: how fast delta itself changes per $1 move in the underlying (the curvature of the position). High gamma = exposure flips quickly near the strike.",
  "ν": "Vega: how much the price changes if annualized volatility moves by 1.00 (i.e. 100 percentage points). Divide by 100 for the effect of a 1-point vol move.",
  "Θ": "Theta: time decay; how much value the position gains or loses per calendar day, everything else unchanged. Negative when you own options, positive when you sold them.",
  "ρ": "Rho: sensitivity to the financing rate (per 1.00 of rate). Small for short-dated options; the desk sources the rate from Aave's USDC borrow market.",
};

// Labeled pricing input/output cell with an instant hover definition,
// visually consistent with the greeks grid.
function SpecCell({ label, value, def }: { label: string; value: string; def: string }) {
  return (
    <div className="greek-cell spec-cell" data-def={def} aria-label={def}>
      <span className="dim greek-label">{label}</span>
      <span>{value}</span>
    </div>
  );
}

function GreeksGrid({ greeks }: { greeks: Greeks }) {
  const cells: [string, number, number][] = [
    ["Δ", greeks.delta, 3],
    ["Γ", greeks.gamma, 5],
    ["ν", greeks.vega, 2],
    ["Θ", greeks.theta, 2],
    ["ρ", greeks.rho, 2],
  ];
  return (
    <div className="greeks-grid">
      {cells.map(([label, value, dp]) => (
        <div
          key={label}
          className="greek-cell"
          data-def={GREEK_DEFS[label]}
          aria-label={GREEK_DEFS[label]}
        >
          <span className="dim greek-label">{label}</span>
          <span>{value.toFixed(dp)}</span>
        </div>
      ))}
    </div>
  );
}
