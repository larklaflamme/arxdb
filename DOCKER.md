# ArxDB — Docker

A ready-to-run image of the full ArxDB stack: the **Go/Pebble storage engine**
(`arxdbd`) and the **Python verification/query layer** (the HTTP API), wired
together over gRPC inside a single container.

## Pull

```bash
docker pull ghcr.io/larklaflamme/arxdb:latest
```

The image is built and published automatically by GitHub Actions on every push
to `master` (tag `latest`), on every version tag (`vX.Y.Z`), and on every commit
(`sha-<short>`). Multi-arch: `linux/amd64` and `linux/arm64`.

## Run

```bash
docker run -d -p 8080:8080 ghcr.io/larklaflamme/arxdb:latest
```

Then:

```bash
curl http://localhost:8080/health
# {"status": "ok", "version": "0.1.0"}
```

That's it. The container starts the Go daemon, waits for its gRPC socket, then
serves the HTTP API on port 8080.

## Persist data

The storage engine (Pebble) and the API's keypair/roster live under `/data`.
Mount a volume to keep them across restarts:

```bash
docker run -d -p 8080:8080 -v arxdb-data:/data ghcr.io/larklaflamme/arxdb:latest
```

## Configuration

Everything is overridable via environment variables:

| Variable | Default | Meaning |
|----------|---------|---------|
| `ARXDB_BACKEND` | `grpc` | `grpc` (Go/Pebble) or `sqlite` (in-process) |
| `ARXDB_DATA_DIR` | `/data` | Go daemon data dir (Pebble + daemon keypair) |
| `ARXDB_API_ROOT` | `/data/api` | API keypair + roster |
| `ARXDB_SOCKET` | `/tmp/arxdb.sock` | gRPC UNIX socket |
| `ARXDB_HOST` | `0.0.0.0` | HTTP bind host |
| `ARXDB_PORT` | `8080` | HTTP bind port |

### Lightweight mode (SQLite, no Go daemon)

```bash
docker run -d -p 8080:8080 -e ARXDB_BACKEND=sqlite ghcr.io/larklaflamme/arxdb:latest
```

This skips the Go daemon entirely and runs the in-process SQLite backend — a
single process, useful for quick experiments. The default (`grpc`) is the
production configuration.

## Try the API

```bash
# Commit a reasoning edge (definition: x > 0)
curl -s -X POST http://localhost:8080/commit \
  -H 'Content-Type: application/json' \
  -d '{"edge_type":"DEFINITION","claim":"x > 0","rule":"assumption"}'

# Reachability
curl -s -X POST http://localhost:8080/query/reachable \
  -H 'Content-Type: application/json' \
  -d '{"claim":"x > 0"}'

# The anchor record (root hash)
curl -s http://localhost:8080/anchor
```

See `PUBLIC_API.md` for the full endpoint reference.

## docker compose

```bash
docker compose up -d
curl http://localhost:8080/health
```

## Build from source

```bash
docker build -t arxdb .
docker run -d -p 8080:8080 arxdb
```

## How it works

The image is a two-stage build:

1. **Builder** (`golang:1.27`) compiles `arxdbd` into a static binary
   (`CGO_ENABLED=0` — Pebble is pure Go).
2. **Runtime** (`python:3.14-slim`) installs the pinned Python deps
   (`requirements.txt`), copies the package and the daemon binary, and runs
   `tini` as PID 1 so signals reach both processes.

The entrypoint (`docker-entrypoint.sh`) starts `arxdbd`, waits for its gRPC
socket, then `exec`s the HTTP API (`scripts/arxdb_serve.py --backend grpc`).
`tini -g` forwards SIGTERM/SIGINT to the whole process group, so the daemon
shuts down gracefully alongside the API.
