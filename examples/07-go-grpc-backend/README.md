# 07 — Go gRPC backend

The drop-in swap: the same facade operations run against the Go storage engine
(Pebble) over gRPC instead of the in-process SQLite backend.

## The scenario

The Python prototype (Phases 1–5) uses an in-process SQLite backend. Phase 6
replaces it with a Go daemon (`arxdbd`) backed by Pebble, exposed over gRPC.
The claim: **the verification, query, and attestation layers are identical** —
only the storage backend changes.

This example proves it by driving the same `verify_and_commit` and `reachable`
calls through a live daemon.

## Run it

```bash
cd /home/ubuntu/arxdb
conda activate arxdb
python examples/07-go-grpc-backend/grpc_demo.py
```

Requires the Go toolchain (see `SETUP.md` §3). The script builds `arxdbd` on
first run.

## Expected output

```
[grpc] verdict=PASS kappa=K3
[grpc] B established=True
```

## Walkthrough

### Build and start the daemon

```python
build_daemon()   # go build -o /tmp/arxdbd ./cmd/arxdbd
proc = subprocess.Popen([str(DAEMON_BIN), "--data-dir", ..., "--socket", ...])
```

The daemon owns the storage engine and the signing keypair. It listens on a
UNIX socket.

### The drop-in swap

```python
store = create_storage(Path(tmp), b"", b"", backend="grpc", socket_path=str(socket_path))
```

`root`/`priv`/`pub` are ignored for the gRPC backend — the daemon owns them.
Only `socket_path` matters. Everything else is identical to the SQLite backend.

### Same operations

```python
verify_and_commit(store, pub, [], a, "assume", EdgeType.DEFINITION)
r = verify_and_commit(store, pub, [a], b, "add 1", EdgeType.DEDUCTION)
q = reachable(b.node_id(), store)
```

The verification pipeline (Z3, κ-tiering) runs in Python; the storage engine
runs in Go. The two are glued by the gRPC contract in `go/proto/arxdb.proto`.

## Handling scenarios

- **Run the daemon as a service** — start `arxdbd` under systemd or a process
  supervisor; point every client at the same socket.
- **Cross-language clients** — the gRPC contract is language-neutral: a Go,
  Rust, or TypeScript client can talk to the same daemon (see
  `tests/test_cross_language_audit.py` for the Go-signs/Python-verifies proof).
- **Crash recovery** — the daemon persists to Pebble; restart it on the same
  `--data-dir` and the state survives (see `tests/test_go_swap.py`).
- **Atomicity** — `commit_edge_tx` commits graph + log in a single Pebble
  indexed batch; a failure leaves zero partial state (see
  `tests/test_go_atomicity.py`).

## Key API

`create_storage` (with `backend="grpc"`), `GrpcStorage`, the `arxdbd` daemon.
