# OptoPuts : an insurance for your wallet 🐙

<p align="center">
  <img src="docs/octopus-intro.gif" alt="OptoPuts mascot: a pixel-art octopus appears, then vanishes leaving a scatter of glowing pixel coins — ETH, WBTC, LINK, UNI, AAVE" width="960">
</p>

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


## Pitch deck
<p align="center"><img src="docs/deck-slides/slide-1.png" alt="Slide 1 — cover: OptoPuts, insurance for your wallet; The Graph AI and Hedera HTS bounty chips" width="100%"></p>
<p align="center"><img src="docs/deck-slides/slide-2.png" alt="Slide 2 — the problem: options are opaque, AI alone can't be trusted, settlement is a promise" width="100%"></p>
<p align="center"><img src="docs/deck-slides/slide-3.png" alt="Slide 3 — life of a trade: ask, measure, price, mint, settle" width="100%"></p>
<p align="center"><img src="docs/deck-slides/slide-4.png" alt="Slide 4 — The Graph as the load-bearing wall: Uniswap v3 vol curve, Aave v3 rate, agent reasons but never computes" width="100%"></p>
<p align="center"><img src="docs/deck-slides/slide-5.png" alt="Slide 5 — who pays whom: treasury Francesco 0.0.9695676 and customer Piotr 0.0.9651354, five on-chain hops, real $21.88 settlement" width="100%"></p>
<p align="center"><img src="docs/deck-slides/slide-6.png" alt="Slide 6 — tokenization on Hedera: each option series is an HTS token, no smart contract" width="100%"></p>
<p align="center"><img src="docs/deck-slides/slide-7.png" alt="Slide 7 — qualification scorecard for both bounties" width="100%"></p>
<p align="center"><img src="docs/deck-slides/slide-8.png" alt="Slide 8 — close: watch money move in 30 seconds" width="100%"></p>

The scheduled transfer is the on-chain settlement *commitment*; at expiry a
backend worker computes the payoff from live spot and triggers
`/settlement/execute`, which pays out and writes the settlement record to HCS.
Both settlement endpoints are idempotent per token, the desk can never pay
twice.

## Run it

```bash
cp .env.example .env       # fill: ANTHROPIC_API_KEY, GRAPH_API_KEY, Hedera creds
cd backend && uv sync && uv run pytest          # 86 tests
uv run uvicorn app:app --port 8000              # backend (or: python mock_server.py)
cd ../hedera-sidecar && npm i && npm start      # sidecar :7070 (+ POST /setup once)
                                                # (npm start, NOT run dev — the
                                                #  watcher restarts on state.json)
cd ../frontend && npm i && npm run dev          # UI
```

`OFFLINE_MODE=1` runs the whole desk from committed fixtures, zero network.
