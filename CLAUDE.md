# OptoPuts — Claude Code instructions

Mini options desk for ETH: Python vol engine prices options off Uniswap v3 realized
vol (The Graph), Claude agent quotes/explains, Hedera testnet mints/logs/settles.

## Read before writing any code
1. `docs/CONTRACTS.md` — **frozen interfaces** between the two lanes (tool schemas,
   sidecar HTTP API, SSE chat protocol, env vars). Never change a shape unilaterally.
2. `docs/PLAN.md` — stages, lane ownership, task checklists, gates.
3. `docs/options_desk_summary.md` — full product spec.

## Hard constraints
- **The agent computes nothing.** All numbers come from deterministic, tested Python
  in `backend/vol_engine/` and `backend/graph/`. The agent parses intent, calls
  tools, explains, and triggers chain actions.
- `price_option` / `price_strategy` are network-free: data comes in via cached
  fetchers, never fetched inside pricing.
- Tests first for pricing math (`backend/vol_engine/tests/`), against known
  Black–Scholes values.
- Secrets only via env (`backend/config.py` / sidecar dotenv). Never commit `.env`;
  keep `.env.example` in sync with CONTRACTS §5.
- `OFFLINE_MODE=1` must always work: `fixtures/` replaces every network call.

## Lane ownership (merge-conflict firewall)
- Lane A (Python): `backend/` — vol_engine, graph, agent, app.py, mock_server.py
- Lane B (JS/TS): `hedera-sidecar/`, `frontend/`
- Shared, change only by joint commit: `docs/CONTRACTS.md`, `fixtures/`, `.env.example`
Stay inside your lane's directories. If a task seems to need a change on the other
side of a contract, stop and flag it instead of editing across the boundary.

## Working style
- Tick task checkboxes in `docs/PLAN.md` in the same commit that lands the task.
- `main` must always demo; use short-lived branches per track.
- Within a lane, tasks marked **[independent]** in PLAN Stage 1 share no files —
  they may be built by parallel subagents/sessions and integrated after.

## Run
- Backend: `cd backend && uv run uvicorn app:app --reload` (mock: `uv run python mock_server.py`)
- Tests: `cd backend && uv run pytest`
- Sidecar: `cd hedera-sidecar && npm run dev` (port 7070) · smoke: `./smoke.sh`
- Frontend: `cd frontend && npm run dev`
