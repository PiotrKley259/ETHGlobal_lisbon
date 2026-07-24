#!/usr/bin/env bash
# OptoPuts sidecar smoke test (B1.5): full option lifecycle against Hedera
# testnet — mint → transfer → HCS log → schedule → execute (twice, to prove
# settlement idempotency) — printing Hashscan links as it goes.
# Requires: the sidecar running (npm run dev), HEDERA_OPERATOR_ID/KEY in .env,
# node on PATH (used for JSON parsing so we don't depend on jq).
set -euo pipefail

BASE="${SIDECAR_URL:-http://localhost:7070}"

jget() { # jget '<json>' <field>  → value or empty
  node -e "const o=JSON.parse(process.argv[1]); const v=o[process.argv[2]]; console.log(v===undefined||v===null?'':v)" "$1" "$2"
}

req() { # req <method> <path> [json-body]  → response body; dies on non-2xx
  local method="$1" path="$2" body="${3:-}"
  local out code
  if [ -n "$body" ]; then
    out=$(curl -s -w $'\n%{http_code}' -X "$method" "$BASE$path" -H "Content-Type: application/json" -d "$body")
  else
    out=$(curl -s -w $'\n%{http_code}' -X "$method" "$BASE$path")
  fi
  code="${out##*$'\n'}"
  body="${out%$'\n'*}"
  if [ "${code:0:1}" != "2" ]; then
    echo "FAIL $method $path → HTTP $code" >&2
    echo "$body" >&2
    exit 1
  fi
  echo "$body"
}

step() { echo; echo "── $1"; }

step "health"
HEALTH=$(req GET /health)
echo "$HEALTH"
[ "$(jget "$HEALTH" ok)" = "true" ] || { echo "FAIL: sidecar not healthy (keys set? testnet up?)"; exit 1; }

step "setup (idempotent)"
SETUP=$(req POST /setup '{}')
echo "$SETUP"
STABLECOIN=$(jget "$SETUP" stablecoin_id)
TOPIC=$(jget "$SETUP" topic_id)
CUSTOMER=$(jget "$SETUP" customer_id)

SYMBOL="OPT-C-3600-$(date +%H%M%S)"
EXPIRY=$(( $(date +%s) + 120 ))

step "mint series $SYMBOL"
MINT=$(req POST /tokens/mint-series "{\"symbol\":\"$SYMBOL\",\"name\":\"ETH Call 3600 smoke\",\"option\":{\"type\":\"call\",\"strike\":3600.0,\"expiry_ts\":$EXPIRY,\"qty\":1.0,\"strategy_id\":\"stg-smoke\"}}")
echo "$MINT"
TOKEN=$(jget "$MINT" token_id)

step "re-mint same symbol (must replay, not create a twin)"
REMINT=$(req POST /tokens/mint-series "{\"symbol\":\"$SYMBOL\",\"name\":\"ETH Call 3600 smoke\",\"option\":{\"type\":\"call\",\"strike\":3600.0,\"expiry_ts\":$EXPIRY,\"qty\":1.0}}")
[ "$(jget "$REMINT" replayed)" = "true" ] || { echo "FAIL: duplicate mint was not replayed"; exit 1; }
[ "$(jget "$REMINT" token_id)" = "$TOKEN" ] && echo "ok: replayed token_id $TOKEN"

step "transfer option token to customer"
req POST /tokens/transfer "{\"token_id\":\"$TOKEN\",\"to\":\"customer\",\"qty\":1}"

step "HCS trade log"
req POST /hcs/log "{\"kind\":\"trade\",\"payload\":{\"symbol\":\"$SYMBOL\",\"token_id\":\"$TOKEN\",\"premium_usd\":142.11}}"

step "arm settlement (expiry in 120s)"
SCHED=$(req POST /settlement/schedule "{\"token_id\":\"$TOKEN\",\"expiry_ts\":$EXPIRY,\"max_payout_usd\":800.0}")
echo "$SCHED"

step "execute settlement"
EXEC1=$(req POST /settlement/execute "{\"token_id\":\"$TOKEN\",\"payout_usd\":25.50,\"spot_at_expiry\":3625.50}")
echo "$EXEC1"

step "execute settlement AGAIN (must replay, not pay twice)"
EXEC2=$(req POST /settlement/execute "{\"token_id\":\"$TOKEN\",\"payout_usd\":25.50,\"spot_at_expiry\":3625.50}")
[ "$(jget "$EXEC2" replayed)" = "true" ] || { echo "FAIL: duplicate execute was not replayed — DOUBLE PAY RISK"; exit 1; }
[ "$(jget "$EXEC2" tx_id)" = "$(jget "$EXEC1" tx_id)" ] && echo "ok: replayed settlement tx $(jget "$EXEC1" tx_id)"

step "treasury balances"
req GET /treasury/balances

echo
echo "══ smoke PASSED — Hashscan links ══"
echo "stablecoin : https://hashscan.io/testnet/token/$STABLECOIN"
echo "topic      : https://hashscan.io/testnet/topic/$TOPIC"
echo "customer   : https://hashscan.io/testnet/account/$CUSTOMER"
echo "series     : $(jget "$MINT" hashscan_url)"
echo "schedule   : $(jget "$SCHED" hashscan_url)"
echo "settlement : $(jget "$EXEC1" hashscan_url)"
