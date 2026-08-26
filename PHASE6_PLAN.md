# ArxDB — Phase 6 Plan: Go Storage Swap (v0.2)

> Replace the Python storage layer with Go, behind the same `Storage` interface.
> The verification layer stays Python *permanently* (ADR-005). This phase makes
> the "drop-in swap" claim in ADR-005 *true*, not aspirational.

> **v0.2 changelog** (reconciled to `PHASE6_PLAN_review.md`): Q1–Q3 resolved
> (ADR-006 override recorded, numbering maintained, gRPC confirmed, Scope A
> confirmed); transport pinned to gRPC over **UNIX domain sockets** for local
> IPC with TCP reserved for Phase 7; atomicity pinned to a **BadgerDB/Pebble
> transaction**; the cryptographic parity moat (§4) now names exact libraries;
> Go module layout (§5) and storage factory (§6) added; test plan expanded to
> the four-suite matrix (§7).

---

## 0. Two flags before we start (honest, not decorative)

**Flag 1 — "final phase" needs a call.** The roadmap has *seven* phases (0–7).
Phase 6 is the Go swap; Phase 7 is Productization (AI Trust & Audit — the public
API, docs, and the "reproduce a proof" story). **Resolved:** Phase 6 is *not*
the final phase. Phase 7 still follows. This plan covers Phase 6 as the roadmap
defines it (the Go swap); Phase 7 is untouched.

**Flag 2 — ADR-006 gates this phase behind a trigger that has not fired.** The
rewrite trigger is: (a) a single reachability query over 10⁶ edges exceeds
target latency, OR (b) concurrent append throughput saturates. We are at **9
edges**. By our own ADR, doing the Go swap now is premature optimization.

**Resolved — ADR-006 override, formally recorded.** The swap is executed now as
an **Architectural Validation Gate**, not a performance optimization. The
legitimate reason ADR-006 did not anticipate: **the "drop-in swap" claim in
ADR-005 is currently unverified.** We have asserted that the STORAGE_API
boundary is clean enough that the storage layer can be swapped without touching
the verification layer — but we have never *tested* that assertion. A minimal
Go swap is the only way to prove the boundary is real. The honest framing:
**we are not doing this for performance; we are doing it to validate the
architecture.** This override is recorded in `DECISIONS.md` as an ADR-006
amendment.

---

## 1. What Phase 6 is — and the one thing that changes everything

Phase 1 built the storage layer as Python classes (`ObjectStore`, `GraphIndex`,
`AppendLog`, `Storage`). The verification layer calls *fine-grained* methods:
`objects.put()`, `graph.register_edge()`, `log.append()`, `commit_edge_tx()`.

The Go swap is **not** a 1:1 port of those fine-grained methods. It is a
re-architecting of the boundary into **coarse-grained operations that preserve
atomicity across a process boundary.**

Why: `commit_edge_tx` is atomic across graph + log (a single `BEGIN IMMEDIATE …
COMMIT` on one SQLite connection). If Go is a separate process, three separate
RPCs (`put`, `register_edge`, `append`) would *break* that atomicity — a crash
between RPC 2 and RPC 3 leaves a half-committed edge. So the Go backend must
expose `commit_edge_tx` as **one atomic operation**, not three.

This is the single most important design fact in the plan. Everything else
follows from it.

---

## 2. The core design decision: how Python talks to Go

**Resolved: Option A — gRPC daemon.** The review endorsed gRPC and added one
refinement that matters: **UNIX domain sockets** for local IPC.

| Transport | Mechanism | Atomicity | Operational cost | Verdict |
|-----------|-----------|-----------|------------------|---------|
| **A. gRPC server** | Go daemon, Python client | Coarse RPC preserves it | Running service to manage | **Chosen** |
| **B. Subprocess (stdio JSON-RPC)** | Go binary, persistent child | Coarse call preserves it | No daemon, but a child process | Fallback |
| **C. cgo shared lib + ctypes** | Go → `.so`, Python FFI | Function call preserves it | cgo build fragility | Rejected |

**Transport detail (from review §2.1):** the gRPC server listens on a **UNIX
domain socket** (`unix:///tmp/arxdb.sock`) for local Python↔Go IPC. This
eliminates the TCP/IP loopback stack overhead and achieves sub-millisecond RPC
latency. The same server can also bind TCP for Phase 7's distributed/external
consumers — so the transport is *one* server, *two* listeners.

Reasons for gRPC:

1. **Phase 7 needs a public API anyway.** The roadmap's Phase 7 deliverable is
   "Public API (HTTP/gRPC) over the two queries." Building the Go backend as a
   gRPC server now means Phase 7's public API is *already half-built* — the
   same server that serves the Python verification layer can serve external
   clients. This collapses two phases' worth of work.

2. **Atomicity is natural.** A single `CommitEdge` RPC maps cleanly to the
   atomic `commit_edge_tx` contract.

3. **cgo (C) is the wrong tool.** The verification layer stays Python because
   that's where sympy/mpmath/z3/Lean live — but those tools don't need to talk
   to storage over FFI. An FFI boundary couples the two languages at the ABI
   level, which is exactly the coupling ADR-005 was trying to avoid. A process
   boundary (gRPC or subprocess) keeps them cleanly separated.

---

## 3. Preserving atomicity across the process boundary

In Python Phase 1, atomicity came from a shared SQLite connection
(`BEGIN IMMEDIATE … COMMIT`). In Go, the review pins it to a **BadgerDB/Pebble
transaction** (embedded LSM, per ADR-009):

The Go daemon receives `CommitEdgeTxRequest(premises, conclusion, edge_bytes,
proof_bytes)` and, in a single server-side function:

1. Writes `edge_bytes` and optional `proof_bytes` to the ObjectStore.
2. Opens an atomic **BadgerDB/Pebble transaction** (`txn = db.NewTransaction(true)`).
3. Indexes the hyper-edge connectivity (`edges`, `premises`, `incoming`, `outgoing`).
4. Appends to the signed log and updates the incremental Merkle tree root.
5. Commits the transaction (`txn.Commit()`).

If any step fails, the transaction is discarded — zero orphaned graph or log
state. This is the cross-process analogue of the Phase 1 `BEGIN IMMEDIATE …
COMMIT`, and it is the thing `test_go_atomicity.py` (below) exists to prove.

---

## 4. Cryptographic & serialization parity moat

The #1 correctness risk is **content-address divergence**: if Go's CBOR or
BLAKE3 output differs from Python's by one byte, every hash changes and the two
implementations can't interoperate. The review pins the exact libraries so the
two runtimes produce byte-identical output:

1. **Canonical CBOR (RFC 8949):**
   - Python: `cbor2.dumps(obj, canonical=True)`
   - Go: `github.com/fxamacker/cbor/v2` with `cbor.CanonicalEncOptions()`
     (definite-length, sorted keys, IEEE 754 float rules).

2. **BLAKE3 multihash:**
   - Python: `0x1e 0x20` prefix + 32-byte BLAKE3 digest.
   - Go: `github.com/zeebo/blake3`, formatted with `[]byte{0x1e, 0x20}` prefix.

3. **Ed25519 signatures:**
   - Python: `cryptography.hazmat.primitives.asymmetric.ed25519`
   - Go: standard library `crypto/ed25519`.

The discipline is: **freeze a test-vector corpus and assert byte-equality** —
do not "trust the libraries." `test_go_parity.py` is the first deliverable, not
an afterthought.

---

## 5. Go module layout

```
go/
├── go.mod
├── go.sum
├── proto/
│   └── arxdb.proto          # StorageService definition (the language-agnostic contract)
├── pkg/
│   ├── hashing/              # BLAKE3 multihash wrapper
│   ├── cbor/                 # Canonical CBOR encoders/decoders
│   ├── keys/                 # Ed25519 sign & verify
│   ├── merkle/               # RFC 6962 Merkle tree & inclusion proofs
│   ├── storage/              # ObjectStore, GraphIndex, AppendLog
│   └── service/              # gRPC server implementation of StorageService
└── cmd/
    └── arxdbd/               # Daemon entrypoint (CLI flags: --socket, --data-dir)
```

The Python side gains one new module:

```
src/arxdb/storage/
├── grpc_client.py            # Storage implementation delegating to Go over gRPC
└── factory.py                # backend selection (see §6)
```

---

## 6. Storage factory agility

Enable seamless switching in Python between backends, so the existing test
suite can run against *either* SQLite (Phase 1) or gRPC (Phase 6) without
touching the verification/query layers:

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

This is the *mechanism* by which the drop-in claim is tested: the same 204-test
suite runs against both backends, and the only thing that changes is the
`backend=` argument.

---

## 7. Deliverables

1. **`go/` module** — the Go storage engine implementing the three
   sub-interfaces (object store, graph index, append log) + the atomic
   `CommitEdge` operation, on BadgerDB/Pebble (ADR-009).

2. **`go/` gRPC service** — exposes the coarse-grained storage API:
   - `PutObject` / `GetObject` / `HasObject` (batch variants)
   - `RegisterNode` / `RegisterEdge` / `GetConnectivity`
   - `Append` / `GetEntry` / `RootHash` / `InclusionProof`
   - `CommitEdge` (the atomic one)

3. **Python client shim** — `grpc_client.py`, a new `Storage` implementation
   (same class signature) that delegates to the Go server over gRPC. The
   verification layer is *untouched* — it keeps calling
   `storage.commit_edge_tx(...)` and gets the same `(edge_hash, LogEntry)` back.

4. **Storage factory** — `factory.py` with `create_storage(backend=...)` for
   SQLite↔gRPC switching.

5. **Canonical-serialization parity** — the Go side must reproduce Python's
   canonical CBOR (ADR-007) and BLAKE3 multihash (ADR-008) *byte-for-byte*
   (§4). This is the hardest correctness risk.

6. **`STORAGE_API.md` v0.4** — the interface doc updated to describe the
   *process* boundary (gRPC service definition) alongside the Python class
   interface, so the contract is language-agnostic.

---

## 8. Scope decision: do the two queries move to Go?

**Resolved: Scope A (storage-only).** The review endorsed this and the
rationale is unchanged:

The roadmap's Phase 3 built `reachable` and `path_discovery` in the Python
**query** layer (on top of storage), deliberately *not* in storage (the
STORAGE_API.md "deliberately absent" note: a dumb BFS over a hypergraph is
unsound for multi-premise AND-OR inference).

- **Scope A (storage-only):** Go implements only the three sub-interfaces +
  `CommitEdge`. The Python query layer stays Python, calling Go for raw
  connectivity. *Chosen — matches the "dumb storage" principle (ADR-001).*

- **Scope B (storage + queries):** Go also implements `Reachable` /
  `PathDiscovery`, moving AND-OR resolution to Go. *Deferred to Phase 7.*

The "dumb storage" principle says storage should not do semantic traversal.
Moving AND-OR resolution to Go is a *query-layer* decision, not a storage
decision, and it belongs with the productization work. Phase 6 proves the
*storage* swap; Phase 7 decides where the queries live.

---

## 9. Exit criteria

- **Same test suite passes against the Go backend.** The existing `tests/`
  suite (204 tests) runs unchanged against the Python client shim, which
  delegates to Go. This is the *proof* of the drop-in claim.
- **Content-address parity.** `hash_bytes(x)` in Python == `hash_bytes(x)` in Go
  for a corpus of test vectors (including edge cases: empty bytes, unicode,
  nested structures, `Hash` byte-strings).
- **Atomicity holds across the boundary.** A `CommitEdge` that fails mid-way
  (injected fault) leaves no partial edge — the graph and log are both
  unchanged.
- **The verification layer is untouched.** `git diff` on `src/arxdb/verification/`
  and `src/arxdb/query/` is empty (or only import-path changes).

---

## 10. Test plan (four-suite matrix)

**`test_go_parity.py`** (the correctness moat)
- Multi-language cryptographic parity: vectors of empty bytes, nested
  dictionaries, unicode strings, and `Hash` instances produce byte-identical
  CBOR, BLAKE3, and Ed25519 signatures in Python and Go.

**`test_go_swap.py`** (the drop-in proof)
- The entire existing test suite (204 tests across Phases 1–5) runs green
  against `GrpcStorageClient` pointing at a live `arxdbd` process.

**`test_go_atomicity.py`** (cross-process failure recovery)
- Fault injection in Go `CommitEdgeTx` verifies that failure before commit
  leaves zero partial state in BadgerDB/Pebble.

**`test_cross_language_audit.py`** (interoperability verification)
- An edge signed and committed via the Python client through the Go daemon is
  retrievable, verifiable, and passes `verify_edge_attestation` and
  `verify_history`.

---

## 11. Adjacent frames & failure modes (breadth)

**Adjacent frame — IPFS / go-ipfs.** ADR-005 already named this: a
content-addressed signed Merkle-DAG is structurally a minimal IPFS, and the
reference implementation is Go. The Go swap is, in effect, "adopt the IPFS
storage model without the DHT/network layer." The known hard parts (content
addressing, Merkle proofs, chunking) are solved in that codebase; we are
re-deriving a tiny subset.

**Failure mode 1 — content-address divergence.** If Go's CBOR or BLAKE3 output
differs from Python's by even one byte, every hash changes and the two
implementations can't interoperate. This is the #1 risk and the reason
`test_go_parity.py` is the first deliverable, not an afterthought. The fix is
to freeze a *test-vector corpus* (not "trust the libraries") and assert
byte-equality.

**Failure mode 2 — atomicity silently broken by the process boundary.** If
`CommitEdge` is implemented as three RPCs instead of one, a crash between them
corrupts the graph. This is the trap §1 is designed to avoid, but it is easy to
reintroduce under time pressure. `test_go_atomicity.py` is the guard.

**Failure mode 3 — the swap becomes a rewrite.** The moment the Go side starts
"improving" the interface (renaming methods, changing return types, adding
semantics), the drop-in claim dies and the verification layer has to change.
The discipline is: **the Python `Storage` class signature is frozen; Go
conforms to it, not the other way around.**

**Failure mode 4 — premature optimization (the ADR-006 trap).** If we do this
swap and then measure "no meaningful speedup at 9 edges," that is *expected*,
not a failure — the swap is a validation exercise, not a performance win. The
plan must not let "it's not faster" be read as "it failed."

---

## 12. What would strengthen or refute this plan

- **Strengthen:** a real cross-language round-trip — Skye (Python) signs an
  edge, the Go backend stores it, Lark (a second Python client) retrieves and
  verifies it — proving the boundary is genuinely language-agnostic.
- **Refute:** if `test_go_parity.py` cannot be made to pass (CBOR/BLAKE3
  divergence that can't be reconciled), then the "drop-in swap" claim is false
  and ADR-005 needs rework — the boundary is not as clean as we asserted.
- **Open question for later:** whether the Go server should be the *public*
  API (Phase 7) or a *private* backend with a separate public gateway. This is
  a Phase 7 decision.

---

## 13. Decisions (resolved)

- **Q1 — Trigger override + numbering.** ✅ Override ADR-006 (validation gate,
  not performance); Phase 6 is *not* final — Phase 7 still follows.
- **Q2 — Transport.** ✅ gRPC daemon over UNIX domain sockets (TCP reserved for
  Phase 7).
- **Q3 — Scope.** ✅ Storage-only (Scope A); queries stay in Python, deferred
  to Phase 7.
