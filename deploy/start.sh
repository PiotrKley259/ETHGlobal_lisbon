#!/usr/bin/env bash
# Container entrypoint: sidecar on loopback :7070 (never exposed), backend on
# $PORT (the only routed port). exec keeps uvicorn as the signal target so the
# platform's stop/restart reaches it; the sidecar dies with the container.
set -e

node /app/hedera-sidecar/src/server.js &

# Bootstrap chain state on boot: the container filesystem is ephemeral, so
# state.json starts empty after every deploy. /setup is idempotent (replays
# stored IDs), so calling it on every boot is safe — this removes the manual
# `railway ssh … /setup` step and keeps push-to-deploy fully hands-off.
(
  for _ in $(seq 1 30); do
    sleep 2
    if curl -sf http://localhost:7070/health > /dev/null 2>&1; then
      curl -s -X POST http://localhost:7070/setup > /dev/null 2>&1 || true
      break
    fi
  done
) &

cd /app/backend
exec .venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port "${PORT:-8000}"
