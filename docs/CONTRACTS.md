# OptoPuts — Interface Contracts (FROZEN)

> Everything is JSON. All timestamps are unix seconds UTC. All prices are USD floats.
> All vols are annualized decimals (0.62 = 62%). All tenors `T_days` are float days.

---

## 1. Engine tool schemas (Python `vol_engine` + `graph`, exposed as MCP + agent tools)

The same functions are exposed twice from one implementation:
- as MCP tools in `backend/vol_engine/server.py` (FastMCP) — the demo narrative,
- as plain Python callables consumed by `backend/agent/tools.py`.

> **Multi-asset addendum:** every
> engine data/pricing tool gains an optional `asset` parameter whose enum is
> **registry-driven** from `backend/config.py` (currently ETH, WBTC, LINK,
> UNI, AAVE; default `"ETH"` — all pre-existing shapes unchanged). `get_price_history`/
> `get_spot` responses and the §3 `panel` object gain an additive `asset`
> field. Assets come from the registry in `backend/config.py` (Uniswap v3
> USDC pools; per-pool inversion handled in the adapter — CONTRACTS §6).
> Mint symbols become `OPT-{ASSET}-{C|P}-{K}-{nonce}` and the option metadata
> gains `"asset"`.

### `get_price_history(hours: int = 720) -> PriceHistory`
```json
{"pool": "0x88e6...5640", "hours": 720,
 "candles": [{"ts": 1750000000, "open": 3512.1, "high": 3550.0,
              "low": 3480.2, "close": 3533.7, "volume_usd": 12345678.0}]}
```
Candles ascending by `ts`. Source: Uniswap v3 ETH/USDC 0.05% `poolHourDatas`.

### `get_spot() -> Spot`
```json
{"price": 3533.70, "ts": 1750003600, "source": "uniswap-v3-subgraph"}
```

### `estimate_vol(window: "24h"|"7d"|"30d", estimator: "close"|"parkinson" = "close") -> Vol`
```json
{"sigma_annual": 0.62, "sigma_period": 0.086, "window": "7d",
 "estimator": "close", "n_obs": 168}
```
Annualization factor: `sqrt(8760)` on hourly log returns. `sigma_period`
(additive field, 2026-07-24, P1-proposed) = `sigma_annual * sqrt(hours/8760)`:
the 1-sigma expected move over the window's own length — the intuitive number
the panel headlines (annualized stays the unit for pricing and bar heights).

### `get_vol_curve() -> VolCurve`   *(stretch — Stage 4)*
```json
{"points": [{"tenor_days": 1, "sigma": 0.71}, {"tenor_days": 7, "sigma": 0.62},
            {"tenor_days": 30, "sigma": 0.55}],
 "shape": "backwardation"}
```
`shape ∈ contango | backwardation | flat` (flat if endpoints within 2 vol pts).

### `get_regime(bands: {"calm": float, "elevated": float} | None = None) -> Regime`
```json
{"regime": "elevated", "percentile": 0.81, "window": "7d",
 "bands": {"calm": 0.33, "elevated": 0.66}}
```
Percentile of current 7d vol within its trailing 30d distribution. `bands` are the
**user-configurable** regime thresholds: `percentile < calm → calm`,
`< elevated → elevated`, else `stressed`. Defaults `{0.33, 0.66}`; validation
`0 < calm < elevated < 1`. The engine never stores them — the backend passes the
current settings on every call, and the response echoes the bands used so the UI
can always explain the badge.

### `set_regime_bands(calm: float, elevated: float) -> Settings`   *(agent tool, backend-owned)*
Lets the user set thresholds conversationally ("only the top 20% counts as
stressed" → `{calm: 0.33, elevated: 0.80}`). Writes the same settings object as
`POST /settings`; returns the updated Settings and triggers a fresh `panel` event.

### `get_risk_free_rate() -> Rate`
```json
{"rate_cc": 0.043, "source": "constant", "observed_at": 1750003600, "fallback_level": 2}
```
`source ∈ aave-v3-subgraph | fred-dgs1mo-cached | constant`, `fallback_level ∈ 0|1|2`.
Baseline ships `constant` (0.04); Aave is Stage 4. **Never fetched inside pricing.**

### `price_option(K: float, T_days: float, type: "call"|"put", qty: float = 1.0, S: float|None = None) -> Quote`
`S=None` means "use latest cached spot" (the agent normally omits it).
```json
{"price": 142.11, "qty": 1.0,
 "inputs": {"S": 3533.7, "K": 2800.0, "T_days": 6.5, "r_cc": 0.043, "sigma": 0.62,
            "sigma_source": "7d"},
 "greeks": {"delta": -0.18, "gamma": 0.0004, "vega": 3.1, "theta": -8.2, "rho": -0.9}}
```
Greeks per 1 unit: vega per 1.00 vol pt, theta per day, rho per 1.00 rate pt.
**Additive (2026-07-25):** single-option Quotes also carry `payoff`,
`breakevens`, `max_profit`, `max_loss` (same shapes as StrategyQuote,
buyer's side) so the panel draws a P&L curve for single legs too.

### `list_strategies() -> [StrategyDef]`
```json
[{"name": "bull_call_spread", "legs_template": "long call K1, short call K2>K1",
  "view": "moderately bullish, capped upside for lower cost"}]
```
Library (baseline 8): `long_call, long_put, bull_call_spread, bear_put_spread,
long_straddle, long_strangle, long_butterfly, short_straddle`.

### `price_strategy(legs: [Leg]) -> StrategyQuote`
```json
// Leg:
{"type": "call", "side": "long", "K": 3600.0, "T_days": 7.0, "qty": 1.0}
// StrategyQuote:
{"net_cost": 96.40, "net_greeks": {"delta": 0.02, "gamma": 0.0007, "vega": 5.9,
                                   "theta": -14.1, "rho": 0.1},
 "legs": ["...per-leg Quote objects..."],
 "payoff": {"prices": [2800.0, 2825.0], "pnl": [-96.4, -71.4]},
 "breakevens": [3450.2, 3749.8], "max_profit": 203.6, "max_loss": -96.4}
```
`payoff.prices`: 1spanning spot ± 3·σ·√T (min span ±15%). `max_profit`
may be `null` (unbounded). Named structures are resolved to legs **by the agent**,
using `list_strategies` — the engine only prices explicit legs.

### `check_coverage(max_payout_usd: float) -> Coverage`
```json
{"ok": true, "treasury_balance_usd": 50000.0, "open_exposure_usd": 4200.0,
 "series_cap_usd": 10000.0}
```
Backend-owned risk gate (`backend/agent/risk.py`); reads sidecar `/treasury/balances`.
Agent MUST call before any mint and refuse when `ok=false`.

---

## 2. Hedera sidecar HTTP API (Node/Express, `hedera-sidecar/`, port `7070`)

All endpoints JSON. Errors: non-2xx with `{"error": "...", "detail": "..."}`.
Every success response includes `hashscan_url` where a chain entity was touched.

| Method & path | Request body | Response |
|---|---|---|
| `GET /health` | — | `{"ok": true, "network": "testnet", "operator": "0.0.x"}` |
| `POST /setup` | `{}` | one-time: creates demo stablecoin + HCS topic + customer acct → `{"stablecoin_id", "topic_id", "customer_id"}` (also persisted to `hedera-sidecar/state.json`) |
| `POST /tokens/mint-series` | `{"symbol": "OPT-C-3600-0725", "name": "ETH Call 3600 2026-07-25", "option": {"type": "call", "strike": 3600.0, "expiry_ts": 1753459200, "qty": 1.0, "strategy_id": "stg-abc123"}}` | `{"token_id": "0.0.x", "tx_id": "...", "hashscan_url": "..."}` — option terms go in token memo/metadata |
| `POST /tokens/transfer` | `{"token_id": "0.0.x", "to": "customer", "qty": 1}` | `{"tx_id", "hashscan_url"}` — handles association |
| `POST /hcs/log` | `{"kind": "quote"\|"trade"\|"settlement", "payload": {…arbitrary…}}` | `{"topic_id", "sequence_number", "tx_id", "hashscan_url"}` |
| `POST /settlement/schedule` | `{"token_id": "0.0.x", "expiry_ts": 1753459200, "max_payout_usd": 800.0}` | `{"schedule_id": "0.0.x", "status": "armed", "hashscan_url"}` |
| `POST /settlement/execute` | `{"token_id": "0.0.x", "payout_usd": 233.70, "spot_at_expiry": 3833.7}` | `{"tx_id", "hashscan_url", "paid_usd": 233.70}` |
| `GET /treasury/balances` | — | `{"hbar": 100.0, "stablecoin_usd": 50000.0}` |

**Settlement model (be honest about it, incl. in README):** a Hedera Scheduled
Transaction fixes its transfer amount at creation (confirmed — the inner
`SchedulableTransactionBody` is immutable), so it cannot compute `max(0, S−K)` at
expiry. `/settlement/schedule` arms an on-chain scheduled transfer as the
settlement commitment; at expiry the backend settlement worker computes the payoff
from spot and calls `/settlement/execute`, which performs the stablecoin transfer
and logs the settlement record to HCS.

**Idempotency (settled: yes for settlement, keyed on `token_id`):** the backend
worker is at-least-once (retries on timeout, refires after restart), so the
sidecar is the exactly-once boundary for anything that moves money:
- `POST /settlement/execute` — **idempotent per `token_id`**. Before transferring,
  the sidecar checks `state.json`; if a settlement record exists it does NOT pay
  again and replays the stored response with `"replayed": true` added (HTTP 200).
  Write order: mark `settling` in `state.json` → transfer → record `{tx_id,
  paid_usd, ts}` → respond. A crash between transfer and record is the residual
  window; acceptable for the demo, noted in README limitations.
- `POST /settlement/schedule` — idempotent per `token_id`: one schedule per
  series; duplicate call returns the existing `schedule_id` (`"replayed": true`).
- `POST /tokens/mint-series` — idempotent per `symbol` (duplicate returns the
  existing `token_id`) so a retried mint can't create twin series.
- `POST /hcs/log` — **deliberately NOT idempotent**: it's an append-only audit
  log; a duplicate message is harmless and honest (two records of one event beats
  a dedupe bug that drops one). `/setup` is idempotent as a whole: if
  `state.json` exists it returns the existing IDs untouched.

**Verified Hedera constraints (HIP-423 era, v0.57+ — long-term scheduling is live):**
- Scheduled tx max future expiration **62 days**; default **30 min** if
  `expirationTime` unset. Use `.setExpirationTime(...)` + `.setWaitForExpiry(true)`
  (defaults to `false` = executes as soon as sigs collected) and **sign everything
  at `ScheduleCreate` time** — an under-signed schedule expires silently.
- Execution fires at the first consensus time *after* expiry (seconds-scale, not
  exact-time) — phrase the demo accordingly.
- Token memo **and** HIP-646 fungible `metadata` are each capped at **100 bytes**
  → option terms as terse JSON, e.g. `{"t":"C","K":3600,"e":1753459200}`.
- Create the customer account with `.setMaxAutomaticTokenAssociations(-1)`
  (HIP-904 unlimited auto-association) — kills `TOKEN_NOT_ASSOCIATED_TO_ACCOUNT`
  demo failures; the receiver must be associated at scheduled-execution time.
- HCS: keep each message ≤ 1024 bytes (single chunk — cleaner in Hashscan);
  mirror-node messages come back base64-encoded.
- SDK: prefer **`@hiero-ledger/sdk`** (Hiero rename; identical API to
  `@hashgraph/sdk`, which is headed for deprecation).
- Hashscan (testnet): `https://hashscan.io/testnet/{transaction|token|topic|schedule|account}/…`;
  SDK tx IDs `0.0.X@ssss.nnnnnnnnn` → URL form `0.0.X-ssss-nnnnnnnnn`.
- Schedule status for the UI: mirror node `GET /api/v1/schedules/{id}` →
  `executed_timestamp`.

---

## 3. Chat wire protocol (FastAPI ⇄ frontend)

Single endpoint: `POST /chat` with `{"message": str, "conversation_id": str|null}`.
Response: `text/event-stream` (SSE). Event types (each `data:` line is one JSON object):

| event | data | purpose |
|---|---|---|
| `token` | `{"delta": "The 7-day vol is..."}` | streamed assistant text |
| `tool_call` | `{"name": "estimate_vol", "args": {"window": "7d"}}` | render tool chip |
| `tool_result` | `{"name": "estimate_vol", "summary": "σ=62% (7d, close)"}` | resolve chip |
| `panel` | `{"spot": {...Spot}, "vols": [ ...Vol x3 ], "regime": {...Regime}, "rate": {...Rate}, "quote": Quote\|null, "strategy": StrategyQuote\|null, "curve": VolCurve\|null}` | full pricing-panel state (send whole object each time; fields may be null) |
| `chain` | `{"kind": "mint"\|"hcs"\|"schedule"\|"settle", "label": "OPT-C-3600-0725", "id": "0.0.x", "tx_id": "...", "hashscan_url": "...", "status": "ok"\|"armed"\|"paid"}` | append row to chain strip |
| `error` | `{"message": "..."}` | show inline error |
| `done` | `{"conversation_id": "..."}` | close stream |

Also: `GET /panel` returns the latest `panel` object (page-load hydration), and
`GET /health` returns `{"ok": true, "offline_mode": false}`.

**Settings** (user preferences, held by the backend in memory, defaults on restart):
```json
// GET /settings  and  POST /settings (partial update ok) — Settings object:
{"regime_bands": {"calm": 0.33, "elevated": 0.66}}
```
`POST` validates `0 < calm < elevated < 1` (else 422). After any settings change
(menu or agent tool), the backend recomputes the regime and pushes/serves an
updated `panel`. The frontend settings menu (gear icon in the pricing panel) is
the UI for this endpoint; the regime badge tooltip shows the active bands.

**Mock server:** `backend/mock_server.py` serves this exact protocol from
`fixtures/` with canned responses for 3 scripted prompts + scripted chain events.
The frontend is built against the mock and must not care which server it talks to.

---

## 4. Fixtures (`fixtures/`, committed)

- `pool_hour_datas.json` — real 720h of ETH/USDC candles, captured once in Stage 0 (raw subgraph response shape).
- `spot.json` — one real spot response.
- `chat_scripts.json` — mock server's canned SSE sequences.

`OFFLINE_MODE=1` makes `graph/subgraph.py` read fixtures instead of the network —
this is both the dev loop and the demo-day network-failure fallback.

---

## 5. Environment variables (`.env.example` mirrors this; never commit `.env`)

```
ANTHROPIC_API_KEY=            # agent loop
GRAPH_API_KEY=                # The Graph gateway key (Subgraph Studio, free 100k q/mo)
UNISWAP_SUBGRAPH_ID=5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV
AAVE_SUBGRAPH_ID=Cd2gEDVeqnjBn1hSeqFMitw8Q1iiyV9FYUZkLNRcL87g
ETH_USDC_POOL=0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640
HEDERA_NETWORK=testnet
HEDERA_OPERATOR_ID=           # treasury account 0.0.x
HEDERA_OPERATOR_KEY=          # treasury private key  (sidecar only)
SIDECAR_URL=http://localhost:7070
RISK_FREE_RATE_CONSTANT=0.04
OFFLINE_MODE=0
```
Python reads env only via `backend/config.py`; Node sidecar via its own `dotenv`.
(The two subgraph IDs are public identifiers, safe to commit.)

---

## 6. Verified Graph facts (researched 2026-07; build against these)

Gateway endpoint: `https://gateway.thegraph.com/api/<GRAPH_API_KEY>/subgraphs/id/<SUBGRAPH_ID>`

**Uniswap v3 mainnet** (`5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV`, the official one
from Uniswap dev docs):
- Pool `0x88e6…5640`: token0 = **USDC** (6 dec), token1 = **WETH** (18 dec).
- **`token0Price` ≈ ETH price in USD (~3000-scale) and `PoolHourData.open/high/low/close`
  track `token0Price` — values are already decimal-adjusted ETH/USD. NO inversion.**
  (Verified in subgraph mapping code: `poolHourData.open = pool.token0Price`.)
- History query: `poolHourDatas(first: 720, orderBy: periodStartUnix,
  orderDirection: desc, where: {pool: "<lowercase addr>"}) { periodStartUnix open
  high low close volumeUSD }` — `first` max 1000, so 720h fits one query.
- Spot query: `pool(id: "<lowercase addr>") { token0Price }`.
- Gotchas: pool address must be **lowercase**; BigDecimals arrive as **strings**
  (parse to float); newest/oldest candle of a window may be a partial hour (drop
  the newest candle for vol estimation).

**WBTC/USDC 0.3% pool** (`0x99ac8ca7087fa4a2a1fb6357269965a2014abc35`,
$128M TVL — verified live 2026-07-25): token0 = **WBTC**, so this pool is
**inverted** relative to the ETH pool: `poolHourData` OHLC is WBTC-per-USDC
(~0.0000156) → USD price = `1/x` with **high/low swapped**; spot reads
`token1Price` (≈ $63,917). The adapter's `invert` flag in `config.ASSETS`
handles both orientations; any future asset must record its orientation there.

**WETH-quoted asset pools** (verified live 2026-07-25 — all have the asset
as token0, so candles are asset-per-WETH → invert, then **cross with the
same-hour ETH/USDC close** to get USD; close-to-close returns compose
exactly, intra-hour high/low are an approximation):
- LINK/WETH 0.3% `0xa6cc3c2531fdaa6ae1a3ca84c2855806728693e8` ($53M TVL, 16% sparse hours)
- UNI/WETH 0.3% `0x1d42064fc4beb5f8aaf85f4617ae8b3b5b8bd801` ($31M TVL, 2% sparse)
- AAVE/WETH 0.3% `0x5ab53ee1d50eef2c1dd3d5402789cd27bb52c1bb` ($11M TVL, 4% sparse)
Sparse pools are handled by the gap-aware vol estimator (returns weighted by
Σr²/Σdt over a TIME window). **DOGE rejected**: the only pool (WDOGE/WETH,
$17M) trades 14% of hours — 744 candles span 7.5 months; realized vol from
it would be meaningless.

**Aave v3 mainnet** (`Cd2gEDVeqnjBn1hSeqFMitw8Q1iiyV9FYUZkLNRcL87g`, official
aave/protocol-subgraphs schema):
- `reserves(where: {underlyingAsset: "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"})
  { symbol variableBorrowRate liquidityRate lastUpdateTimestamp }`
- `variableBorrowRate` is **APR in ray**: `/1e27` → decimal APR → `r_cc = ln(1+r)`.
- Filter by `underlyingAsset` (lowercase), **not** `symbol` (duplicate symbols exist).
- **Verified live 2026-07-24:** `variableBorrowRate = 38943706239048578172608273`
  → 3.894% APR → `r_cc ≈ 0.0382`. Use this as the known-value regression case for
  the ray-conversion unit test. The `RISK_FREE_RATE_CONSTANT=0.04` fallback is
  within ~20bps of the live rate — defensible as shipped.
- Trap: subgraph `JCNWRypm…` ("Aave V3 Ethereum") is the **Messari-schema** deployment
  (`Market`/`InterestRate`, no ray `Reserve`) — do not use it.

**Subgraph MCP (the agent's second MCP server, Stage 4):** official hosted server at
`https://subgraphs.mcp.thegraph.com/sse` (SSE), auth = ordinary gateway API key as
Bearer token; tools include `execute_query_by_subgraph_id`, `get_schema_by_subgraph_id`,
`search_subgraphs_by_keyword` — ad-hoc GraphQL against arbitrary subgraphs.
(Source: graphops/subgraph-mcp; the Token API MCP is a different product with
different auth — not needed here.)
