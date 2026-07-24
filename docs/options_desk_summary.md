# OptoPuts — Product Spec (original)

**Slogan:** An insurance for your wallet.

## Main idea
A mini options desk for ETH: a Python engine prices European cash-settled calls and
puts using realized volatility estimated from Uniswap v3 price history (via The
Graph), an AI agent quotes and explains them in plain language, and each option
series is minted, audited, and automatically settled on Hedera testnet.

## Architecture
Chat interface → AI agent (Claude, tool use) → two MCP servers: the vol engine
(Python) and the subgraph MCP (ad-hoc live queries). The vol engine reads price
history and live spot from the Uniswap v3 ETH/USDC Subgraph (spot = latest pool
price). The agent mints and settles through three Hedera services: Token Service
(option series as HTS tokens with strike/expiry metadata), Consensus Service
(tamper-proof quote and trade log), Scheduled Transactions (expiry settlement).

## Vol engine specification (quant core)
1. `get_price_history(pool, hours)` — `poolHourDatas` from the ETH/USDC 0.05%
   Subgraph (hourly OHLC + volume).
2. `estimate_vol(window, estimator)` — log returns; close-to-close std as baseline,
   Parkinson (high/low range) as the upgrade; annualized via `sqrt(8760)`; windows
   24h / 7d / 30d giving a realized-vol term structure.
3. `get_regime()` — current 7d vol percentile within its trailing distribution →
   calm / elevated / stressed.
4. `price_option(S, K, T, type)` — Black–Scholes. **Vol term structure (stretch,
   not mandatory):** `estimate_vol` returns realized vol at three tenors which
   define a term-structure curve. Add `get_vol_curve()` returning the three
   (tenor_days, sigma) points plus a fitted interpolator, and
   `sigma_for_horizon(T_days)` as the single source of σ for all pricing —
   `price_option` must call it rather than selecting a bar. Interpolation is linear
   in **variance-time (σ²·T)**, not in σ (variance is additive across time);
   convert back to σ at the end. Clamp flat outside the observed range (T < 1d →
   24h estimate; T > 30d → 30d estimate) — extrapolating a realized curve is not
   defensible. Expose the curve's shape (contango vs backwardation) as a
   first-class output; the agent should mention it when it materially affects a
   quote. The pricing panel should render the three bars with the fitted curve
   overlaid and the quoted (T, σ) marked. Unit tests: exact reproduction at tenor
   points; monotone interpolation; flat clamping; variance-time interpolation ≠
   naive σ-interpolation on a non-flat curve.
5. Greeks from the same closed-form pass.
6. `price_strategy(view or named structure)` — compose legs from `price_option`;
   net cost, net Greeks, payoff curve (net P/L across terminal ETH prices). Spot
   comes from the Subgraph (latest pool price).

## Division of labor: agent vs engine
The agent computes nothing. All numbers come from deterministic, tested Python
exposed as MCP tools. The agent: parses intent ("a call just out of the money
expiring Friday" → strike, T), orchestrates tool calls, explains results in plain
language (price, Greeks, regime, why), investigates ad-hoc questions via the
Subgraph MCP, and triggers mint/settle actions.

## Settlement model
Cash-settled: at expiry the desk pays the holder `max(0, S−K)` for calls (reverse
for puts) in a demo stablecoin. Only stablecoins move, between customer and desk
treasury. Credibility collateral: treasury pre-funded with demo stablecoin, max
payout capped per series, agent refuses to sell beyond treasury coverage.

## Strategy library and view-to-strategy reasoning
Multi-leg strategies as baskets of already-priced calls/puts — pricing is cheap
composition. Library (~8–10, declarative legs relative to spot): long call, long
put, bull call spread, bear put spread, long straddle, long strangle, long
butterfly, short straddle / short butterfly. Recognizable payoff shapes:
butterfly = tent, spread = capped ramp, long straddle = V, short straddle =
inverted V.

**The reasoning showcase — view-to-strategy mapping** (watch direction carefully):
- "ETH stays flat, I want to PROFIT from calm" → **short** straddle / short
  butterfly (collect premium, lose if it breaks).
- "ETH stays flat BUT protect me against big moves either way" → **LONG**
  straddle / strangle (pay premium, profit if it breaks).
These are opposites; the agent should surface the tension and clarify ("profit
from calm, or protect against a break?") rather than keyword-match.

**Strategy profitability:** the user can also seek yield, not just hedging — e.g.
"I have 1 ETH, maximize my current position" → low vol, short call on the view
the asset won't move.

## Risk-free rate
Source r from the Aave v3 Ethereum mainnet subgraph: Reserve entity for USDC
(settlement currency), `variableBorrowRate` annualized and scaled 1e27 (ray) —
divide by 1e27 for decimal APR; convert to continuous via `r_cc = ln(1 + r)`.
Implement as `get_risk_free_rate()` in the data layer reusing the GraphQL client;
returns `{rate_cc, source, observed_at}`. Cache in memory, refresh ≤ hourly —
never call from inside `price_option`. Fallbacks: Aave subgraph → cached FRED
DGS1MO → hardcoded constant, surfacing the fallback level. Rationale for README:
payoff is stablecoin-settled, so the desk's true financing rate is the stablecoin
borrow rate, not a Treasury rate — internally consistent with settlement and same
live data source. Tests: ray conversion, percent→continuous vs known value, each
fallback branch.

## UI
When a strategy is proposed, the pricing panel renders its payoff diagram (P/L at
expiry vs ETH price, breakevens and max profit/loss marked).

Single-page chat app — no landing page, no login. Three regions:
- **Left (primary):** chat column; tool-call chips show when the agent works.
- **Right top:** live pricing panel — spot, vol term structure bars 24h/7d/30d,
  regime badge, and on a quote, price + Greeks. When the agent says "$142," the
  panel shows the vol and regime that produced it at the same moment.
- **Right bottom:** chain activity strip (dark, terminal look) — token ID +
  Hashscan link, HCS topic, settlement-armed status in real time.

Aesthetic: quant-terminal, muted, monospace-ish. Build order: chat + pricing panel
first (complete Graph-track demo alone), chain strip when minting works, styling
dead last.

## Minting a multi-leg strategy
Mint each leg as its own HTS token, grouped under a strategy ID logged to HCS. No
new settlement logic — each leg settles by the existing rule. Do NOT build a
composite "structured product token"; basket-of-legs reuses everything.

## Principles
The vol_engine package is self-contained and testable in isolation (it is the
differentiator and the MCP server); graph/ and hedera adapters are thin; the agent
wires them together; the frontend calls one FastAPI endpoint. Secrets only from
env via config; commit only `.env.example`.
