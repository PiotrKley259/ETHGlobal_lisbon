# OptoPuts deploy image: backend (FastAPI) + hedera-sidecar (Node) in one
# machine. Only the backend port ($PORT) is exposed by the platform; the
# sidecar binds :7070 on loopback and is unreachable from outside — that is
# the security boundary (it has no auth and moves treasury funds).
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv

WORKDIR /app

# Dependency layers first so code edits don't bust the caches
COPY hedera-sidecar/package.json hedera-sidecar/package-lock.json hedera-sidecar/
RUN cd hedera-sidecar && npm ci --omit=dev
COPY backend/pyproject.toml backend/uv.lock backend/
RUN cd backend && uv sync --frozen --no-dev

COPY hedera-sidecar hedera-sidecar
COPY backend backend
COPY fixtures fixtures
COPY deploy/start.sh /start.sh
RUN chmod +x /start.sh

# Railway/Fly inject PORT; 8000 is the local-run default
EXPOSE 8000
CMD ["/start.sh"]
