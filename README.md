# OptoPuts — an insurance for your wallet

A mini options desk for ETH: a Python engine prices European cash-settled calls and
puts using realized volatility from Uniswap v3 price history (The Graph), a Claude
agent quotes and explains them in plain language, and each option series is minted,
audited, and automatically settled on Hedera testnet (HTS · HCS · Scheduled
Transactions).

**Team workflow — start here:**

1. [`docs/PLAN.md`](docs/PLAN.md) — stages, parallel lanes, task checklists, demo gates
2. [`docs/CONTRACTS.md`](docs/CONTRACTS.md) — frozen interfaces between the lanes
3. [`docs/options_desk_summary.md`](docs/options_desk_summary.md) — full product spec
4. `CLAUDE.md` — constraints for Claude Code sessions

Setup: copy `.env.example` → `.env` and fill keys (never commit `.env`).
