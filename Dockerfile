# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1 — build the Go storage daemon (arxdbd) as a static binary.
# Pebble is pure Go (no CGO), so CGO_ENABLED=0 yields a fully static binary.
# ---------------------------------------------------------------------------
FROM golang:1.27 AS builder
WORKDIR /src
COPY go/ ./go/
RUN cd go && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/arxdbd ./cmd/arxdbd

# ---------------------------------------------------------------------------
# Stage 2 — runtime: Python verification/query layer + the Go daemon binary.
# ---------------------------------------------------------------------------
FROM python:3.14-slim

# tini: proper PID-1 signal forwarding + zombie reaping (the entrypoint runs
# two processes — the Go daemon and the HTTP API — so a real init matters).
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini \
    && apt-get clean

WORKDIR /app

# Python dependencies (full runtime set, pinned).
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# The package (importable via PYTHONPATH) + the serve script.
COPY src/ ./src/
COPY scripts/arxdb_serve.py ./scripts/arxdb_serve.py
ENV PYTHONPATH=/app/src

# The Go daemon binary.
COPY --from=builder /out/arxdbd /usr/local/bin/arxdbd

# Entrypoint.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Runtime configuration (all overridable via -e / environment).
ENV ARXDB_DATA_DIR=/data \
    ARXDB_API_ROOT=/data/api \
    ARXDB_SOCKET=/tmp/arxdb.sock \
    ARXDB_BACKEND=grpc \
    ARXDB_HOST=0.0.0.0 \
    ARXDB_PORT=8080

EXPOSE 8080
VOLUME /data

ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/usr/local/bin/docker-entrypoint.sh"]
