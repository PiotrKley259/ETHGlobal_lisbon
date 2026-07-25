# OptoPuts — an insurance for your wallet

A mini options desk for ETH. A deterministic Python engine prices European
cash-settled calls, puts, and multi-leg strategies using **realized volatility
measured from Uniswap v3 trade history** (The Graph); a Claude agent quotes and
explains them in plain language; every sold series is **minted, audit-logged,
and auto-settled on Hedera testnet** (HTS + HCS + Scheduled Transactions).

> *"Protect my ETH below $1,770 for the next week"* → the agent reads live spot
> ($1,858), measures 7-day realized vol (37%), checks the regime, prices the
> put, explains why and on confirmation mints it as an HTS token,
> logs the trade to HCS, and arms on-chain settlement that pays
> max(0, K−S) in demo stablecoin at expiry, automatically.

## Why it's interesting

- **The agent computes nothing.** Every number comes from tested Python
  (78 unit tests, Black–Scholes verified against textbook values). Claude
  parses intent, orchestrates tools, explains, and triggers chain actions —
  the UI shows the tool calls and the pricing panel updates from the same
  data that produced the quote, live.
- **The vol term structure is load-bearing.** 24h/7d/30d realized vols define
  a curve; pricing interpolates **linear in variance-time (σ²·T)** and clamps
  flat outside the observed range. Right now the curve is in contango
  (33%→37%→53%), so a 3-day option costs **33% less** than the 30d headline
  vol would suggest — and the agent says so.
- **Internally consistent financing rate.** Options settle in stablecoin, so
  r is the **USDC variable borrow rate from Aave v3** (ray→APR→ln(1+r)),
  falling back to FRED DGS1MO, then a constant — the fallback level is
  surfaced in every quote.
- **A desk, not a toy.** Treasury coverage gate (per-series cap + open-exposure
  ledger, fails closed), view-to-strategy reasoning ("profit from calm" →
  *short* straddle vs "protect against a break" → *long* straddle — opposites
  the agent disambiguates), payoff diagrams with breakevens and max P/L.

## Architecture

```
Browser (React) ── POST /chat (SSE) ──► FastAPI backend
  chat | pricing panel | chain strip      └─ Claude agent (tool use)
                                              ├─ vol engine (pure math + MCP server)
                                              ├─ Graph adapter ──► Uniswap v3 / Aave v3 subgraphs
                                              └─ HTTP ──► Hedera sidecar (Node + Hiero SDK)
                                                            HTS mint · HCS log · Scheduled settle
```

Settlement model (honest version): a Hedera **Scheduled Transaction cannot
compute max(0, S−K) at expiry** — its amount is fixed at creation. So the
scheduled transfer is the on-chain settlement *commitment*; at expiry a
backend worker computes the payoff from live spot and triggers
`/settlement/execute`, which pays out and writes the settlement record to HCS.
Both settlement endpoints are idempotent per token — the desk can never pay
twice.

## Run it

```bash
cp .env.example .env       # fill: ANTHROPIC_API_KEY, GRAPH_API_KEY, Hedera creds
cd backend && uv sync && uv run pytest          # 78 tests
uv run uvicorn app:app --port 8000              # backend (or: python mock_server.py)
cd ../hedera-sidecar && npm i && npm run dev    # sidecar :7070 (+ POST /setup once)
cd ../frontend && npm i && npm run dev          # UI
```

`OFFLINE_MODE=1` runs the whole desk from committed fixtures — zero network.
Team workflow docs: [`docs/PLAN.md`](docs/PLAN.md) ·
[`docs/CONTRACTS.md`](docs/CONTRACTS.md) ·
[`docs/options_desk_summary.md`](docs/options_desk_summary.md).

## Sponsor tracks

- **The Graph** — pricing inputs are entirely subgraph-fed: Uniswap v3
  `poolHourDatas` (vol + spot) and Aave v3 `Reserve` (financing rate), via the
  decentralized gateway. The vol engine is also exposed as an MCP server.
- **Hedera** — three services doing real work: HTS (each option series is a
  token with terms in metadata), HCS (tamper-proof quote/trade/settlement
  log), Scheduled Transactions (settlement commitment, HIP-423).
- **AI** — Claude tool-use agent with a hard compute-nothing rule; the
  view-to-strategy mapping is the reasoning showcase.

## Honest limitations & path to production

| Today (48h build) | Production path |
|---|---|
| Realized vol ≈ pricing vol (no options market to imply from) | Blend implied vol from Deribit/Lyra; add jump/stochastic-vol models |
| Desk is the sole counterparty; one prefunded treasury | Margined LP vault, collateralized writers, liquidation engine |
| Payoff computed off-chain by a worker (scheduled tx = commitment) | Oracle-fed settlement contract; the HCS log already makes every step auditable |
| In-memory exposure ledger & conversation state | Persistent store; signed quotes with expiry |
| Crash window between transfer & record in the sidecar | Mirror-node reconciliation before retry |
| Testnet, demo stablecoin | Mainnet, audited contracts, real stablecoin rails |
