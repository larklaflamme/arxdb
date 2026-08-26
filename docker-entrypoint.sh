#!/bin/sh
set -e

DATA_DIR="${ARXDB_DATA_DIR:-/data}"
API_ROOT="${ARXDB_API_ROOT:-/data/api}"
SOCKET="${ARXDB_SOCKET:-/tmp/arxdb.sock}"
BACKEND="${ARXDB_BACKEND:-grpc}"
HOST="${ARXDB_HOST:-0.0.0.0}"
PORT="${ARXDB_PORT:-8080}"

mkdir -p "$DATA_DIR" "$API_ROOT"

if [ "$BACKEND" = "grpc" ]; then
    # Start the Go storage daemon (Pebble) over a UNIX socket.
    arxdbd --data-dir "$DATA_DIR" --socket "$SOCKET" &

    # Wait for the gRPC socket to appear.
    i=0
    while [ ! -S "$SOCKET" ] && [ "$i" -lt 100 ]; do
        sleep 0.1
        i=$((i + 1))
    done
    if [ ! -S "$SOCKET" ]; then
        echo "arxdbd failed to start (no socket at $SOCKET)" >&2
        exit 1
    fi
fi

# Run the HTTP API in the foreground. tini (-g) forwards SIGTERM/SIGINT to the
# whole process group, so the daemon shuts down gracefully alongside the API.
exec python scripts/arxdb_serve.py \
    --root "$API_ROOT" \
    --host "$HOST" \
    --port "$PORT" \
    --backend "$BACKEND" \
    --socket "$SOCKET"
