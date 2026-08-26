# Phase 6 — Deliverable 1: Cryptographic Parity Moat (RESULT)

**Date:** 2026-08-26
**Status:** ✅ VERIFIED — byte-identical across Python and Go

## What was built

- `go/` module (`github.com/larklaflamme/arxdb/go`), Go 1.27.0 (installed to
  `/home/ubuntu/go-sdk/go`, persisted in `~/.bashrc`).
- `pkg/hashing` — BLAKE3 multihash (0x1e 0x20 + 32-byte digest).
- `pkg/cbor` — canonical CBOR via `fxamacker/cbor/v2` `CanonicalEncOptions()`.
- `pkg/keys` — Ed25519 (32-byte seed private form).
- `pkg/merkle` — RFC 6962 domain-separated Merkle tree.
- `pkg/parity/parity_test.go` — reads the frozen corpus, asserts byte-equality.
- `scripts/gen_parity_vectors.py` — the Python reference generator.
- `tests/parity_vectors.json` — the frozen corpus (committed).
- `tests/test_go_parity.py` — pytest entry point (runs `go test`).

## The result

All vectors match byte-for-byte:

| Primitive | Vectors | Result |
|-----------|---------|--------|
| Canonical CBOR | 38 | ✅ all match |
| BLAKE3 multihash | 6 | ✅ all match |
| Ed25519 signature | 4 | ✅ all match |
| Merkle root | 5 | ✅ all match |

The #1 correctness risk (content-address divergence) is **resolved**: the two
runtimes produce byte-identical output for every vector, including the edge
cases (empty bytes, unicode, nested structures, Hash byte-strings, int64
boundaries, shortest-form floats).

## One known boundary (documented, not a bug)

Python `int` is arbitrary-precision: cbor2 encodes values > 2^64−1 as a CBOR
bignum (tag 2). Go `int64` is bounded. The actual data model (seq, timestamp_ns)
fits in int64 (timestamp_ns ≈ 1.7e18 < 2^63 ≈ 9.2e18), so this never arises in
practice. If the data model ever needs integers beyond int64, the Go side must
switch to `math/big` for those fields. Flagged, not blocking.

## Verification commands

```
ARXDB_PARITY_CORPUS=/home/ubuntu/arxdb/tests/parity_vectors.json \
  go test ./pkg/parity/ -v          # PASS
python -m pytest tests/test_go_parity.py -v   # PASS
```

## Next (remaining Phase 6 deliverables)

1. `pkg/storage` — ObjectStore, GraphIndex, AppendLog on BadgerDB/Pebble.
2. `proto/arxdb.proto` + `pkg/service` — gRPC StorageService.
3. `src/arxdb/storage/grpc_client.py` — Python client shim.
4. `src/arxdb/storage/factory.py` — backend selection.
5. `STORAGE_API.md` v0.4.
