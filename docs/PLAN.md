# OptoPuts — Build Plan & Team Workflow

> *An insurance for your wallet.* A mini options desk for ETH: a Python engine prices
> European cash-settled options off realized vol from Uniswap v3 history (The Graph),
> a Claude agent quotes and explains them, and every series is minted, logged, and
> settled on Hedera testnet (HTS + HCS + Scheduled Transactions).

This file is the working agreement: stages, lanes, task checklists, and the demo
gates. The frozen interfaces both lanes code against live in
[`CONTRACTS.md`](./CONTRACTS.md) — read that first, it is what makes parallel work
safe. The original product spec is in [`options_desk_summary.md`](./options_desk_summary.md).

**Team:** 2 people · **Budget:** ~48h · **Stack:** Python (FastAPI, vol engine, agent) ·
Node sidecar (Hedera JS SDK) · React + Vite (frontend).

---

## 0. The one diagram

```
                       ┌────────────────────────────────────────────┐
Browser ──POST /chat──►│ FastAPI  backend/app.py                    │
   ▲  SSE stream       │   agent/loop.py (Claude tool use)          │
   │                   │     ├─ vol_engine/*  (quant core, MCP too) │
 React UI              │     ├─ graph/subgraph.py ──► The Graph gw  │
 chat | panel | strip  │     └─ tools → HTTP ──► hedera-sidecar     │
                       └────────────────────────────┬───────────────┘
                                                    ▼
                                     Node + @hashgraph/sdk (testnet)
                                     HTS mint · HCS log · Scheduled settle
```

**Division of labor principle (from the spec):** the agent computes nothing. Every
number comes from deterministic, tested Python. The agent parses intent, orchestrates
tools, explains, and triggers chain actions.

---

## 1. Lanes and ownership

| | **Lane A — Quant & Agent (P1, Python)** | **Lane B — Chain & UI (P2, JS/TS)** |
|---|---|---|
| Owns | `backend/` (all Python): `vol_engine/`, `graph/`, `agent/`, `app.py`, `mock_server.py` | `hedera-sidecar/`, `frontend/` |
| Never touches | `hedera-sidecar/`, `frontend/` | Python code |
| Shared (change only together) | `docs/CONTRACTS.md`, `fixtures/`, `.env.example` | same |

Directory ownership is the merge-conflict firewall: with this split, the two lanes
**cannot** conflict on files. The only coupling is `CONTRACTS.md`.

### Git workflow
- `main` must always demo. Work on short-lived branches (`laneA/vol-engine`,
  `laneB/sidecar`), merge to `main` yourselves as soon as your piece runs — no PR
  reviews required between lanes, since directories don't overlap. Rebase, don't
  merge-commit, if it's clean; don't waste hackathon time on git ceremony.
- Contract changes: pair for 5 minutes, edit `CONTRACTS.md` in its own commit,
  *then* change code on both sides.
- Commit small and often; push at least hourly (laptop death insurance).
- Tick the checkboxes in this file as tasks land (edit PLAN.md in the same commit).

### Using Claude Code in parallel (fan-out inside each lane)
Each person runs their own Claude Code session in their lane's directories.
Within a lane, components below are marked **[independent]** when they share no
files — fan those out to parallel subagents (or two terminal sessions) and
integrate after. `CLAUDE.md` at the repo root points every session at
`CONTRACTS.md` so agents build against the same shapes without coordinating.
Suggested prompts per task are implicit in the task descriptions — paste the task
row plus the relevant CONTRACTS section.

---

## 2. Stages

Dependencies run *down* the page; inside a stage, everything is parallel.

### Stage 0 — Contracts, scaffold, keys (both, together, H0–H2)

The only serial stage. Done when both people can run their half offline.

- [x] **S0.1** This commit: `docs/PLAN.md`, `docs/CONTRACTS.md`, `CLAUDE.md`, `.env.example`.
- [ ] **S0.2** Keys & accounts (do in parallel on two laptops). Keys live **only**
  in each person's local `.env` (copied from `.env.example`, exact var names from
  CONTRACTS §5 — e.g. `GRAPH_API_KEY`, not `API_KEY`). Never in git, never in
  chat logs that get screen-shared.
  - P1: Anthropic API key · The Graph gateway key (Subgraph Studio, free plan)
  - P2: Hedera testnet account via portal.hedera.com (operator = treasury); note ID + key

  Who needs what locally:
  | key | P1 (.env) | P2 (.env) |
  |---|---|---|
  | `ANTHROPIC_API_KEY` | ✔ (agent loop) | — |
  | `GRAPH_API_KEY` | ✔ (fixtures, engine) | — |
  | `HEDERA_OPERATOR_ID/KEY` | only from Stage 3 (worker → sidecar runs on P2's machine until then) | ✔ |

  The **treasury key is the only credential that must be shared** (P2 → P1 for
  Stage 3 integration): pass it out-of-band (password manager / AirDrop /
  Signal), not via git, Discord, or the team doc. It's throwaway testnet — but
  practicing hygiene is free, and judges read repos. If it ever leaks into a
  commit: portal.hedera.com → new account, update `.env`s, done (don't try to
  scrub history mid-hackathon).
- [x] **S0.3** Capture fixtures (P1, ~20 min): one gateway query for 720 hourly
  candles of the ETH/USDC 0.05% pool (exact query + verified endpoint/IDs in
  CONTRACTS §6 — `first: 720` fits one page) → `fixtures/pool_hour_datas.json`,
  `fixtures/spot.json`. Sanity-check `close` ≈ current ETH/USD (it is
  `token0Price`, already USD — no inversion). From here on, **everything Python
  develops offline**.
- [ ] **S0.4** Scaffold skeletons so imports/paths exist: **backend ✅ (P1 done:
  uv + pyproject, all modules stubbed with task pointers, pytest green)**;
  still open for P2: `hedera-sidecar/` (npm init, express + @hiero-ledger/sdk,
  `/health` returns ok), `frontend/` (`npm create vite@latest -- --template
  react-ts`, renders three empty regions).
- [x] **S0.5** `backend/mock_server.py` (P1): serves the full SSE protocol from
  `fixtures/chat_scripts.json` — 3 canned conversations (protective put /
  short straddle incl. the disambiguation beat / mint→settle chain flow) +
  `/panel`, `/settings`, `/health`. Numbers derived from the real fixtures
  (spot $1,858.67; vols 33%/37%/53%). **Frontend lane is unblocked** —
  `cd backend && uv run python mock_server.py` → port 8000.
- [ ] **S0.6** P2 runs sidecar `POST /setup` once when ready: creates demo stablecoin
  (e.g. `dUSDC`, 6 decimals, mint 50,000 to treasury), HCS topic, customer account;
  IDs land in `hedera-sidecar/state.json` (gitignored) and are echoed for the README.

**Gate G0:** `pytest` runs; mock server streams a canned quote; frontend dev server
shows three regions; sidecar `/health` ok against testnet.

---

### Stage 1 — Parallel core build (H2–H14) · 4 independent tracks

#### Track A1 — `backend/vol_engine/` — the quant core (P1) **[independent — pure math, fixtures only]**
Build order inside the track = test-first, per the spec.

- [x] **A1.1** `pricing.py`: Black–Scholes price + closed-form Greeks (delta, gamma,
  vega, theta, rho), call & put. `tests/test_pricing.py` **first**, against known
  BSM values (Hull case, reference ATM Greeks set, parity grid, ITM/OTM limits,
  expiry intrinsic, validation) — 12 tests green.
- [x] **A1.2** `vol.py`: hourly log returns → close-to-close σ (baseline) and
  Parkinson high/low σ (upgrade), annualized `sqrt(8760)`; windows 24h/7d/30d;
  `get_regime` percentile vs trailing 30d with **caller-supplied bands** (defaults
  0.33/0.66, echoed in the response — user-configurable, CONTRACTS §1/§3). Tests:
  GBM recovers known σ, Parkinson exact analytic case, spike→stressed,
  band-relabeling, validation — 9 tests green. Also `select_sigma_window`
  (baseline tenor-matching; Stage 4 replaces with `sigma_for_horizon`).
- [x] **A1.3** `strategies.py`: the 8-structure library as declarative leg templates;
  `price_strategy` = signed sum of priced legs; 121-pt payoff grid, interpolated
  breakevens, max P/L evaluated exactly at strike kinks with unbounded-side
  detection (None) and S_T=0 floor extrapolation. Tests: butterfly tent, spread
  caps, straddle breakevens K±premium, long/short mirror, leg cancellation,
  resolve_named — 10 tests green (suite: 30).
- [x] **A1.4** `server.py`: FastMCP wrapper exposing every CONTRACTS §1 tool
  (9 tools incl. resolve_strategy), delegating to the new `vol_engine/api.py`
  facade — the single place cached Graph data meets the math; agent/tools.py
  will consume the same facade. Offline end-to-end tests green (43 total).
  Note: fixture recaptured at **744 candles (31d)** so the 30d window has its
  required 721 closes.

> A1.1, A1.2, A1.3 share no files → fan out to parallel Claude subagents, then one
> integration pass for shared types in `vol_engine/types.py`.

#### Track A2 — `backend/graph/subgraph.py` — data adapter (P1) **[independent]**
- [x] **A2.1** httpx GraphQL client; `get_price_history(hours)` (asc candles,
  strings→floats), `get_spot()` per CONTRACTS; `OFFLINE_MODE=1` reads `fixtures/`
  through the same code path. Verified live + offline.
- [x] **A2.2** In-memory TTL cache: history 10 min, spot 30 s, rate 1 h —
  pricing never triggers network. Cache test proves single fixture read.
- [x] **A2.3** `get_risk_free_rate()`: live Aave v3 USDC borrow (ray→APR→ln(1+r),
  fallback_level 0, verified 3.82% cc) with constant fallback (level 2) —
  already ahead of baseline; Stage 4 adds only the FRED middle tier + its tests.

#### Track B1 — `hedera-sidecar/` — Hedera adapter (P2) **[independent — tests straight against testnet]**
Use **`@hiero-ledger/sdk`** (the Hiero rename of `@hashgraph/sdk`, identical API).
Verified constraints are in CONTRACTS §2 — read that box before B1.2/B1.4.
- [x] **B1.1** Client setup, env loading, `/health`, `/setup` (stablecoin + topic +
  customer acct created with `maxAutomaticTokenAssociations(-1)`), `state.json`
  persistence.
- [x] **B1.2** `/tokens/mint-series` (fungible HTS token per series; option terms as
  terse JSON ≤100 bytes in memo/metadata) + `/tokens/transfer` (association-safe).
- [x] **B1.3** `/hcs/log` — submit JSON ≤1024 bytes to topic; return sequence number.
- [x] **B1.4** `/settlement/schedule` (`setExpirationTime` + `setWaitForExpiry(true)`,
  treasury signs at create) + `/settlement/execute` per CONTRACTS §2 settlement
  model (scheduled tx = on-chain commitment; execute = actual payoff transfer +
  HCS settlement record). **Both idempotent per `token_id`** (CONTRACTS §2
  idempotency box — the worker retries; the sidecar must never pay twice; test by
  calling execute twice in `smoke.sh` and asserting one transfer + `replayed`).
  `/treasury/balances`.
- [x] **B1.5** `smoke.sh`: curl script that runs the whole lifecycle end to end
  (mint → log → schedule → execute) and prints Hashscan links. This is Lane B's
  test suite *and* the demo rehearsal.

#### Track B2 — `frontend/` — React app (P2) **[independent — runs against mock server]**
- [x] **B2.1** SSE client + chat column: streamed tokens, tool-call chips
  (name flashes while running, collapses to a badge with summary on result).
- [x] **B2.2** Pricing panel: spot, 3 vol bars (24h/7d/30d), regime badge, rate
  source line; on `quote`: price + Greeks grid. Renders whatever the `panel`
  event carries — nulls collapse gracefully.
- [x] **B2.2b** Settings menu: gear icon in the panel → two regime-threshold
  inputs (calm / stressed boundaries, `0 < calm < elevated < 1`) against
  `GET/POST /settings`; regime badge tooltip shows the active bands ("stressed =
  top 20%" is a user choice, not our constant).
- [x] **B2.3** Payoff diagram (strategy quotes): P/L vs terminal price from
  `payoff.prices/pnl`, breakevens and max P/L marked. Hand-rolled SVG or recharts
  — whichever is faster; it must read instantly (this is the "options for
  non-experts" money shot).
- [x] **B2.4** Chain activity strip: dark terminal-style append-only log of `chain`
  events with Hashscan links + status pills (`armed` → `paid`).
- [ ] **B2.5** Aesthetic pass LAST: quant-terminal, muted, monospace. No time on
  styling before Stage 3 gate.

**Gate G1:** `pytest` green across vol_engine (incl. known-value BSM tests);
`smoke.sh` completes a full on-chain lifecycle with Hashscan links; frontend
renders all four surfaces correctly against the mock server.

---

### Stage 2 — Integration I: the Graph-track demo (H14–H20) · mostly P1, P2 finishes B-tracks

- [x] **I1.1 (P1)** `agent/tools.py`: 9 tool schemas bound to the api facade,
  per-tool chip summaries, `build_panel`, `set_regime_bands` mutating state;
  `agent/loop.py`: streaming `claude-sonnet-5` tool-use loop yielding CONTRACTS
  §3 events, panel refresh after every tool batch, error tool_results let the
  agent recover, 8-round guard. Desk persona enforces compute-nothing +
  flat-market disambiguation. Dispatch tests offline (48 green).
- [x] **I1.2 (P1)** `app.py`: `POST /chat` streaming SSE per CONTRACTS §3 with
  conversation store; panel emitted after every tool batch; `GET /panel`
  hydration; `GET/POST /settings` validated + regime recompute; `/health`.
  Endpoint tests offline (52 green) + **two live smokes passed**: protective-put
  quote (4 tools, all numbers tool-sourced) and income-from-calm → SHORT
  straddle with credit/breakevens/unbounded-loss on the panel. Backend side of
  Gate G2 is proven; G2 closes when P2 points the frontend at :8000 (I1.3).
- [ ] **I1.3 (P2)** Point frontend at real backend (one env var swap — protocol is
  identical to mock). Fix drift. Keep chain strip on mock until Stage 3.
- [ ] **I1.4 (both, 30 min)** Script and run the three demo prompts end to end:
  1. "Protect my ETH below $2,800 through next Friday" → put quote + Greeks + regime.
  2. "ETH stays flat — I want to profit from the calm" → agent surfaces the
     short-straddle vs long-straddle tension, prices the short straddle, payoff tent.
  3. "I hold 1 ETH, maximize the position if ETH goes nowhere" → covered-call-style
     short call reasoning.

**Gate G2 — FALLBACK DEMO EXISTS.** Chat + live pricing panel on real Graph data
is a complete, submittable Graph-track demo. Tag it: `git tag demo-graph`.

---

### Stage 3 — Integration II: on-chain lifecycle (H20–H30) · both

- [x] **I2.1 (P1)** `agent/risk.py`: `check_coverage` (treasury balance via sidecar,
  $10k per-series cap, open-exposure ledger, put payout K·qty vs capped calls);
  **fails closed** when the sidecar is unreachable. Tested against a mocked
  sidecar (57 green) — snaps onto the real one untouched.
- [x] **I2.2 (P1)** Chain tools in the agent: `mint_option` (coverage-gated in
  dispatch — refusal happens before any chain call; shared `strategy_id` for
  multi-leg), `log_trade` to HCS, `arm_settlement`; `agent/sidecar.py` client
  per CONTRACTS §2; every chain-tool result forwarded as a `chain` SSE event.
  Tested against a faked sidecar — snaps onto the real one when P2 lands it.
- [x] **I2.3 (P1)** Settlement worker: `agent/settlement.py` registry +
  `execute_due()` (payoff from live spot, exposure released, idempotent
  client-side; sidecar idempotency covers retries) + asyncio loop in app
  lifespan. Settle events queue in `_pending_chain` and flush at the start of
  the next `/chat` stream. Tests: put settles at K−S from fixtures, unarmed/
  unexpired skipped, double-sweep no-op (63 green). *Note for I2.5 rehearsal:
  if the strip needs settle events with no chat open, propose adding a
  `GET /chain` poll endpoint to CONTRACTS §3 as a joint commit.*
- [ ] **I2.4 (P2)** Chain strip on real events; `armed → paid` transition; Hashscan
  links verified clickable for token, topic, schedule, and settlement tx.
- [ ] **I2.5 (both)** Full rehearsal: quote → explain → mint → HCS log → armed →
  auto-settle on screen. Tag `demo-full`.

**Gate G3:** the complete story runs end to end twice in a row without touching a
terminal.

---

### Stage 4 — Stretch (H30–H40) · strictly in this order, drop from the bottom

1. - [x] **(P1)** Vol term structure per spec: `curve.py` variance-time
   interpolation with flat clamps + all four spec'd unit tests green;
   `price_option`/`price_strategy` source σ ONLY from `sigma_for_horizon`
   (`sigma_source: "curve"`); `get_vol_curve` exposed as agent tool, MCP tool,
   and in `panel.curve` (P2's overlay can consume it now); agent prompt
   explains shape when material. Live check: 3d ATM call $23.12 off the
   contango curve vs $34.29 at 30d headline vol (−33%). 74 tests green.
2. - [ ] **(P2)** Panel upgrade: fitted curve over the three bars, quoted (T, σ)
   marked on it — the price visibly comes *from* the curve.
3. - [x] **(P1)** `get_risk_free_rate()` full fallback chain: Aave v3 (level 0,
   live-verified 3.82% cc) → FRED DGS1MO via public fredgraph.csv (level 1,
   live-verified 3.75% cc, '.'-observation handling) → constant (level 2).
   Tests: ray + ln conversions vs known values, csv parser, all three branches
   forced via monkeypatch (78 green). OFFLINE_MODE still goes straight to
   constant — no network at all.
4. - [ ] **(P1)** Subgraph MCP as the agent's second MCP server for ad-hoc
   questions ("what was the pool's busiest hour this week?") — The Graph's hosted
   server at `subgraphs.mcp.thegraph.com/sse`, auth = the same gateway API key as
   Bearer (details CONTRACTS §6).
5. - [ ] **(P2)** Long strangle & butterfly mint flow polish; UI styling pass.

### Stage 5 — Hardening & submission (H40–H48) · both

- [ ] **H.1** `OFFLINE_MODE=1` full-demo dry run (conference wifi insurance):
  fixtures for Graph; chain strip can replay `chat_scripts.json` events if testnet
  is down. One env var flips the whole app.
- [ ] **H.2** Record a backup demo video of the full flow.
- [ ] **H.3** README: pitch, architecture diagram, honest limitations (realized ≠
  implied vol; desk is the sole counterparty; scheduled tx amount fixed at
  creation → worker computes payoff; testnet), path to production, sponsor-track
  mapping (Graph / Hedera / AI), run instructions from clean clone.
- [ ] **H.4** Secrets sweep: `git log -p | grep -iE 'key|secret'` sanity check,
  `.env` never committed, `.env.example` complete.
- [ ] **H.5** Demo script rehearsed with a timer; `demo-graph` tag is the panic
  fallback.

---

## 3. Timeline at a glance

```
H0   H2      H14        H20            H30         H40      H48
├─S0─┼──Stage 1 (A1·A2·B1·B2 parallel)─┤            │        │
     │                  ├─Stage 2──────┤            │        │
     │                  │       G2 ✦ fallback demo  │        │
     │                             ├─Stage 3────────┤        │
     │                                   G3 ✦ full demo      │
     │                                       ├─Stage 4───────┤
     │                                              ├─Stage 5┤
```

Rule of thumb: if a stage overruns its window by >3h, cut scope from Stage 4
first, then from Stage 3 (settlement worker can demo via `smoke.sh` manually).

---

## 4. Risk register

| Risk | Detection | Mitigation |
|---|---|---|
| Scheduled tx can't compute payoff at expiry | verified (immutable inner tx) | Settlement model in CONTRACTS §2: schedule = commitment, worker computes, execute pays; stated honestly in README |
| Scheduled tx silently expires if under-signed, or fires "sometime after" expiry | verified HIP-423 behavior | Sign everything at `ScheduleCreate`; `setWaitForExpiry(true)`; max 62d future expiry (fine — demo uses minutes); don't promise exact-second execution on stage |
| Hedera testnet quarterly reset wipes token/topic/schedule IDs | `smoke.sh` fails on old IDs | Never hardcode chain IDs; `/setup` recreates everything from scratch in one call; check status.hedera.com hackathon week |
| Graph gateway down / rate-limited at demo | any 4xx/5xx | `OFFLINE_MODE=1` fixtures path, identical code |
| Hedera testnet flaky at demo | `smoke.sh` fails | Backup video (H.2) + pre-minted series from rehearsal already on Hashscan |
| Agent hallucinates numbers | tool-chip audit in UI | System prompt forbids arithmetic; every number in text must echo a tool result; panel shows source data simultaneously |
| Token association surprises | B1.2 testing | Customer account created by `/setup` with auto-association slots; sidecar retries with explicit associate |
| Two-person merge conflicts | git | Directory ownership (§1) — no shared code files |
| USDC decimals / price inversion in pool data | **resolved by research** | `token0Price` / OHLC are already decimal-adjusted **ETH in USD** for this pool (CONTRACTS §6) — still eyeball the fixture against a known ETH price at capture, and drop the newest (partial) candle for vol |
| Wrong Aave subgraph (Messari-schema lookalike) | query returns no `Reserve` | Use `Cd2gEDVeqnjBn…` per CONTRACTS §6, filter by `underlyingAsset` |

---

## 5. Definition of done (submission checklist)

- [ ] Live demo: plain-English request → priced, explained quote with visible tool
  calls and live vol/regime panel (Graph data load-bearing).
- [ ] View-to-strategy moment: flat-market ambiguity surfaced and resolved, payoff
  diagram rendered.
- [ ] Mint on Hedera: HTS token with terms, HCS audit log, settlement armed, and an
  auto-settlement paying out on screen; all four Hashscan links work.
- [ ] `pytest` green; `smoke.sh` green.
- [ ] README complete with honest-limitations section.
- [ ] No secrets in history.
```
