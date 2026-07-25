// Shapes from docs/CONTRACTS.md §1 (engine objects) and §3 (wire protocol).
// These are FROZEN — do not edit without a joint contracts commit.

export interface Spot {
  price: number;
  ts: number;
  source: string;
}

export type Asset = "ETH" | "WBTC";

export interface Vol {
  sigma_annual: number;
  /** 1-sigma expected move over the window itself — the intuitive headline.
   *  Optional: absent in older fixtures (mock scripts); derive as fallback. */
  sigma_period?: number;
  window: "24h" | "7d" | "30d";
  estimator: "close" | "parkinson";
  n_obs: number;
}

export interface RegimeBands {
  calm: number;
  elevated: number;
}

export interface Regime {
  regime: "calm" | "elevated" | "stressed";
  percentile: number;
  window: string;
  bands: RegimeBands;
}

export interface Rate {
  rate_cc: number;
  source: "aave-v3-subgraph" | "fred-dgs1mo-cached" | "constant";
  observed_at: number;
  fallback_level: 0 | 1 | 2;
}

export interface Greeks {
  delta: number;
  gamma: number;
  vega: number;
  theta: number;
  rho: number;
}

export interface Quote {
  price: number;
  qty: number;
  inputs: {
    S: number;
    K: number;
    T_days: number;
    r_cc: number;
    sigma: number;
    sigma_source: string;
  };
  greeks: Greeks;
}

export interface StrategyQuote {
  net_cost: number;
  net_greeks: Greeks;
  legs: Quote[];
  payoff: { prices: number[]; pnl: number[] };
  breakevens: number[];
  max_profit: number | null;
  max_loss: number;
}

export interface VolCurvePoint {
  tenor_days: number;
  sigma: number;
}

export interface VolCurve {
  points: VolCurvePoint[];
  shape: "contango" | "backwardation" | "flat";
}

export interface PanelState {
  /** which underlying the panel currently reflects (absent on old payloads) */
  asset?: Asset;
  spot: Spot | null;
  vols: Vol[] | null;
  regime: Regime | null;
  rate: Rate | null;
  quote: Quote | null;
  strategy: StrategyQuote | null;
  curve: VolCurve | null;
}

export interface Settings {
  regime_bands: RegimeBands;
}

export type ChainStatus = "ok" | "armed" | "paid";

export interface ChainEvent {
  kind: "mint" | "hcs" | "schedule" | "settle";
  label: string;
  id: string;
  tx_id: string;
  hashscan_url: string;
  status: ChainStatus;
}

// SSE events on POST /chat (CONTRACTS §3)
export type SseEvent =
  | { event: "token"; data: { delta: string } }
  | { event: "tool_call"; data: { name: string; args: Record<string, unknown> } }
  | { event: "tool_result"; data: { name: string; summary: string } }
  | { event: "panel"; data: PanelState }
  | { event: "chain"; data: ChainEvent }
  | { event: "error"; data: { message: string } }
  | { event: "done"; data: { conversation_id: string } };
