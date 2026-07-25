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


## Architecture

<p align="center">
  <img src="docs/architecture.svg" alt="OptoPuts architecture: React UI talks SSE to the FastAPI agent core, where the Claude agent-octopus reaches into the vol engine, the Graph adapter (Uniswap v3 + Aave v3 subgraphs), and the Hedera sidecar (HTS mint, HCS log, scheduled settlement); a settlement worker pays max(0, K−S) at expiry." width="100%">
</p>

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
