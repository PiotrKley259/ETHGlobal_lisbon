"""GraphQL client for The Graph gateway: get_price_history, get_spot,
get_risk_free_rate. PLAN track A2. OFFLINE_MODE=1 reads fixtures/ via the
same code path. Caching: history 10min TTL, spot 30s TTL — pricing never
triggers network. Verified queries + gotchas: docs/CONTRACTS.md §6.
"""
