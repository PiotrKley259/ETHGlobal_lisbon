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

      {!panel && <p className="placeholder">no data yet — ask the desk for a quote</p>}

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
        <div className="panel-row dim">
          r = {fmtPct(panel.rate.rate_cc)} cc · {panel.rate.source}
          {panel.rate.fallback_level > 0 && ` (fallback L${panel.rate.fallback_level})`}
        </div>
      )}

      {panel?.quote && (
        <div className="quote-block">
          <div className="panel-row">
            <span className="big">${fmtUsd(panel.quote.price)}</span>
            <span className="dim">
              {panel.quote.inputs.K} K · {panel.quote.inputs.T_days}d · σ{" "}
              {fmtPct(panel.quote.inputs.sigma)} ({panel.quote.inputs.sigma_source})
            </span>
          </div>
          <GreeksGrid greeks={panel.quote.greeks} />
        </div>
      )}

      {panel?.strategy && (
        <div className="quote-block">
          <div className="panel-row">
            <span className="big">net {fmtUsd(panel.strategy.net_cost)}</span>
            <span className="dim">
              max +{panel.strategy.max_profit === null ? "∞" : fmtUsd(panel.strategy.max_profit)} /{" "}
              {fmtUsd(panel.strategy.max_loss)}
            </span>
          </div>
          <GreeksGrid greeks={panel.strategy.net_greeks} />
          <PayoffDiagram strategy={panel.strategy} />
        </div>
      )}
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
        <div key={label} className="greek-cell">
          <span className="dim">{label}</span>
          <span>{value.toFixed(dp)}</span>
        </div>
      ))}
    </div>
  );
}
