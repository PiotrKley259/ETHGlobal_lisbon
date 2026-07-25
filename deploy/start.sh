#!/usr/bin/env bash
# Container entrypoint: sidecar on loopback :7070 (never exposed), backend on
# $PORT (the only routed port). exec keeps uvicorn as the signal target so the
# platform's stop/restart reaches it; the sidecar dies with the container.
set -e

node /app/hedera-sidecar/src/server.js &

cd /app/backend
exec .venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port "${PORT:-8000}"
