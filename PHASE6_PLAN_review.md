# ArxDB — Phase 6 Plan Review & Sign-Off (PHASE6_PLAN.md)

**Review Date:** 2026-08-26  
**Document Reviewed:** [`PHASE6_PLAN.md`](file:///home/ubuntu/arxdb/PHASE6_PLAN.md) (v0.1)  
**Related Documents:** [`DESIGN.md`](file:///home/ubuntu/arxdb/DESIGN.md), [`DECISIONS.md`](file:///home/ubuntu/arxdb/DECISIONS.md) (ADR-005, ADR-006, ADR-007, ADR-008, ADR-009), [`STORAGE_API.md`](file:///home/ubuntu/arxdb/STORAGE_API.md), [`ROADMAP.md`](file:///home/ubuntu/arxdb/ROADMAP.md)

---

## 1. Executive Assessment & Formal Sign-Off

[`PHASE6_PLAN.md`](file:///home/ubuntu/arxdb/PHASE6_PLAN.md) outlines the architectural transition of the ArxDB storage engine from the Python SQLite prototype to a high-concurrency **Go storage daemon**.

### Assessment: **APPROVED / SIGN-OFF GRANTED** ✅

The plan demonstrates exceptional systems maturity and architectural honesty:
1. **Intellectual Honesty on ADR-006**: Clearly articulates why the Go swap is being executed now: not as a premature micro-optimization for 9 edges, but as an **Architectural Validation Gate** to prove that the `Storage` boundary is a genuine drop-in replacement that leaves the Verification and Query layers untouched.
2. **Coarse-Grained Cross-Process Atomicity**: Accurately identifies that moving across a process boundary requires server-side atomic batch transactions (`CommitEdgeTx`) in Go to prevent partial state corruption across network RPCs.
3. **Clean Protocol Separation**: Adopts gRPC over UNIX domain sockets / localhost TCP, providing strong IDL typing, streaming capabilities, and directly building the foundation for Phase 7's public productization API.

---

## 2. Core Architectural Review

### 2.1 Transport Architecture: gRPC over UNIX Domain Sockets

In [`PHASE6_PLAN.md` §2](file:///home/ubuntu/arxdb/PHASE6_PLAN.md#L56-L85):
* **Recommendation Endorsed**: **Option A (gRPC)**.
* **Optimization**: Use **UNIX domain sockets** (`unix:///tmp/arxdb.sock`) on Linux for local inter-process communication between Python and Go.
  - Eliminates TCP/IP loopback stack overhead.
  - Achieves sub-millisecond RPC latency.
  - Supports standard TCP for distributed deployment in Phase 7.

```
┌─────────────────────────────────────────────────────────────┐
│  Python Layer (Permanent)                                   │
│  - Verification Layer (schema, elenchus, z3, cas, lean)     │
│  - Query Layer (reachability, path discovery, refutation)   │
│  - Attestation Layer (roster, attest, anchor)               │
└──────────────────────────┬──────────────────────────────────┘
                           │ calls public Storage interface
┌──────────────────────────▼──────────────────────────────────┐
│  src/arxdb/storage/grpc_client.py (Storage Shim)            │
│  - Implements Storage protocol                              │
│  - Serializes to Protobuf / Deserializes from Protobuf      │
└──────────────────────────┬──────────────────────────────────┘
                           │ gRPC (UNIX Domain Socket / IPC)
┌──────────────────────────▼──────────────────────────────────┐
│  Go Daemon (go/cmd/arxdbd)                                  │
│  - ObjectStore: Content-addressed BLAKE3 file/blob store    │
│  - GraphIndex: Structural adjacency in BadgerDB / Pebble    │
│  - AppendLog: Signed Merkle log in BadgerDB / Pebble        │
│  - Atomic Commit: Single BadgerDB transaction in CommitEdge │
└─────────────────────────────────────────────────────────────┘
```

---

### 2.2 Preserving Atomicity Across the Process Boundary

In Python Phase 1, atomicity was achieved via a shared SQLite connection (`BEGIN IMMEDIATE ... COMMIT`). In Go:
* **The Server-Side Transaction**:
  - The Go daemon receives `CommitEdgeTxRequest(premises, conclusion, edge_bytes, proof_bytes)`.
  - In a single Go function:
    1. Writes `edge_bytes` and optional `proof_bytes` to `ObjectStore`.
    2. Opens an atomic **BadgerDB/Pebble transaction** (`txn = db.NewTransaction(true)`).
    3. Indexes the hyper-edge connectivity (`edges`, `premises`, `incoming`, `outgoing`).
    4. Appends to the signed log and updates the incremental Merkle tree root.
    5. Commits the transaction (`txn.Commit()`).
* If any step fails, the Badger transaction is discarded, ensuring zero orphaned graph or log state.

---

### 2.3 Scope A vs. Scope B (Storage-Only vs. Query Migration)

In [`PHASE6_PLAN.md` §4](file:///home/ubuntu/arxdb/PHASE6_PLAN.md#L117-L143):
* **Recommendation Endorsed**: **Scope A (Storage-Only)** for Phase 6.
* **Rationale**:
  - Adheres strictly to the "dumb and fast" storage philosophy (ADR-001).
  - AND-OR Horn-clause resolution, $\kappa$-lattice fixpoint, and Dung grounded refutation resolution stay in the Python Query Layer.
  - Phase 6 validates that swapping the storage backend leaves 100% of `src/arxdb/verification/` and `src/arxdb/query/` untouched.

---

## 3. Resolving the Decisions Needed (Q1–Q3)

| Question | Assessment & Decision |
| :--- | :--- |
| **Q1: Trigger Override & Phase Numbering** | **Confirm Override & Maintain Numbering**:<br>• Formally record the override of ADR-006: the swap is an *Architectural Validation Gate* to prove the drop-in boundary.<br>• Keep Phase 6 as "Go Storage Swap" and retain Phase 7 as "Productization (AI Trust & Audit / Public API)". |
| **Q2: Transport** | **Confirm Option A (gRPC Daemon)**:<br>• Type-safe Protocol Buffers (`arxdb.proto`).<br>• High concurrency via Go goroutines.<br>• Supports UNIX domain sockets for local speed and TCP for Phase 7 external consumers. |
| **Q3: Scope** | **Confirm Scope A (Storage-Only)**:<br>• Storage remains purely structural and dumb.<br>• Query semantics remain in Python. |

---

## 4. Cryptographic & Serialization Parity Moat

To prevent content-address divergence across language runtimes:

1. **Canonical CBOR (RFC 8949)**:
   - Python: `cbor2.dumps(obj, canonical=True)`
   - Go: `github.com/fxamacker/cbor/v2` with `cbor.CanonicalEncOptions()` (definite-length, sorted keys, IEEE 754 float rules).
2. **BLAKE3 Multihash**:
   - Python: `0x1e 0x20` + 32-byte BLAKE3 digest.
   - Go: `github.com/zeebo/blake3` formatted with `[]byte{0x1e, 0x20}` prefix.
3. **Ed25519 Signatures**:
   - Python: `cryptography.hazmat.primitives.asymmetric.ed25519`
   - Go: standard library `crypto/ed25519`.

---

## 5. Go Module Layout & Protobuf Specification

### 5.1 Directory Layout

```
go/
├── go.mod
├── go.sum
├── proto/
│   └── arxdb.proto
├── pkg/
│   ├── hashing/        # BLAKE3 multihash wrapper
│   ├── cbor/           # Canonical CBOR encoders/decoders
│   ├── keys/           # Ed25519 sign & verify
│   ├── merkle/         # RFC 6962 Merkle tree & inclusion proofs
│   ├── storage/        # ObjectStore, GraphIndex, AppendLog
│   └── service/        # gRPC server implementation of StorageService
└── cmd/
    └── arxdbd/         # Daemon entrypoint (CLI flags: --socket, --data-dir)

src/arxdb/storage/
├── grpc_client.py      # Storage implementation delegating to Go over gRPC
```

### 5.2 Storage Factory Agility

Enable seamless switching in Python between backends:

```python
# src/arxdb/storage/factory.py
def create_storage(
    root_dir: Path,
    priv_key: bytes,
    pub_key: bytes,
    backend: Literal["sqlite", "grpc"] = "sqlite",
    socket_path: str | None = None,
) -> StorageProtocol:
    if backend == "sqlite":
        return SQLiteStorage(root_dir, priv_key, pub_key)
    elif backend == "grpc":
        return GrpcStorageClient(socket_path or "/tmp/arxdb.sock")
```

---

## 6. Phase 6 Test Plan Matrix

| Test Suite | Test Objective | Validation Criteria |
| :--- | :--- | :--- |
| **`test_go_parity.py`** | Multi-language cryptographic parity | Vectors of empty bytes, nested dictionaries, unicode strings, and `Hash` instances produce byte-identical CBOR, BLAKE3, and Ed25519 signatures in Python and Go. |
| **`test_go_swap.py`** | Drop-in validation | The entire existing test suite (204 tests across Phases 1–5) runs green against `GrpcStorageClient` pointing to a live `arxdbd` process. |
| **`test_go_atomicity.py`**| Cross-process failure recovery | Fault injection in Go `CommitEdgeTx` verifies that failure before commit leaves zero partial state in BadgerDB/Pebble. |
| **`test_cross_language_audit.py`** | Interoperability verification | Edge signed and committed via Python client through Go daemon is retrievable, verifiable, and passes `verify_edge_attestation` and `verify_history`. |

---

## 7. Sign-Off Checklist

- [x] ADR-006 validation override acknowledged and approved.
- [x] Coarse-grained atomic RPC architecture verified.
- [x] Scope A (Storage-only in Go) validated against dumb-storage principle.
- [x] Transport confirmed as gRPC with UNIX domain socket support.
- [x] Parity test suite requirements formalized.

**Phase 6 implementation plan is fully approved for execution.**
