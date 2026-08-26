# ArxDB — Storage API (v0.2)

The boundary between the verification layer (Python, permanent) and the storage
layer (Python prototype → Go). This interface is the contract that makes the
swap a drop-in replacement, not a rewrite.

> **v0.2 changelog** (post-review): semantic `reachable`/`shortest_path` removed
> from storage (moved to Query layer); `predecessors`/`successors` renamed to
> `incoming_edges`/`outgoing_edges`/`get_connectivity`; batch operations added;
> `LogEntry` + Merkle inclusion proofs specified; atomic `commit_edge_tx` added.

## Design principle

The storage layer is **dumb and fast**. It knows nothing about verification
semantics, κ-strength, or proof correctness. It stores opaque content-addressed
objects, maintains a *structural* graph index for adjacency, and keeps an
append-only signed log for provenance. All *meaning* lives in the verification
layer above it.

Three responsibilities, three sub-interfaces:

1. **Object store** — content-addressed put/get (immutable blobs).
2. **Graph index** — structural node↔edge adjacency (no semantic traversal).
3. **Append log** — ordered, signed sequence of appends (provenance + Merkle).

---

## 1. Object store (content-addressed)

```python
class ObjectStore:
    def put(self, data: bytes) -> Hash:
        """Store bytes, return content hash (BLAKE3). Idempotent: same bytes
        → same hash, no duplicate storage."""

    def put_batch(self, items: Sequence[bytes]) -> list[Hash]:
        """Store multiple blobs in one batch. Returns hashes in order."""

    def get(self, h: Hash) -> bytes | None:
        """Return bytes for hash, or None if absent."""

    def get_batch(self, hashes: Sequence[Hash]) -> list[bytes | None]:
        """Fetch multiple blobs in a single round-trip (parallel to input)."""

    def has(self, h: Hash) -> bool:
        """Membership check without fetching the body."""

    def has_batch(self, hashes: Sequence[Hash]) -> list[bool]:
        """Membership check for multiple hashes in one round-trip."""
```

**Invariants:**
- `put` is idempotent and content-addressed: `put(x) == put(x)` always.
- `get(put(x)) == x` always.
- Objects are immutable once stored (append-only).

---

## 2. Graph index (structural adjacency only)

The storage layer understands the *minimal* graph structure — enough to index
connectivity, not enough to judge. It does **not** perform AND-OR resolution,
κ-filtering, or refutation resolution; those are semantic and live in the Query
layer.

```python
@dataclass(frozen=True)
class EdgeConnectivity:
    edge_hash: Hash
    premises: tuple[Hash, ...]
    conclusion: Hash


class GraphIndex:
    def add_node(self, node_hash: Hash) -> None:
        """Register a node (claim) in the index."""

    def add_edge(self, edge_hash: Hash,
                 premises: Sequence[Hash],
                 conclusion: Hash) -> None:
        """Register a hyper-edge and its connectivity: premises → conclusion."""

    def incoming_edges(self, node_hash: Hash) -> list[Hash]:
        """All edge hashes whose conclusion == node_hash."""

    def outgoing_edges(self, node_hash: Hash) -> list[Hash]:
        """All edge hashes whose premises contain node_hash."""

    def get_connectivity(self, edge_hash: Hash) -> EdgeConnectivity | None:
        """Return (premises, conclusion) for an edge, or None if absent."""
```

**Key point:** the index stores *connectivity* (which edges touch which nodes),
not *content*, and not *semantics*. The verification layer decides what an edge
*means*; the storage layer just knows it connects premises to a conclusion.

**Deliberately absent:** `reachable` and `shortest_path`. A "dumb" BFS/Dijkstra
over a hypergraph would mark a conclusion reachable as soon as *any one* premise
is connected — logically unsound for multi-premise inference. AND-OR proof-tree
resolution is the Query layer's job, built on these structural primitives.

---

## 3. Append log (provenance + Merkle)

```python
@dataclass(frozen=True)
class LogEntry:
    seq: int
    timestamp_ns: int
    signer_pubkey: bytes
    entry_hash: Hash
    prev_log_hash: Hash
    signature: bytes


@dataclass(frozen=True)
class MerkleInclusionProof:
    seq: int
    leaf_hash: Hash
    audit_path: tuple[tuple[str, Hash], ...]  # ('left'|'right', Hash)
    root_hash: Hash


class AppendLog:
    def append(self, entry_hash: Hash,
               signer_pubkey: bytes,
               signature: bytes) -> LogEntry:
        """Append an entry hash with the signer's Ed25519 signature."""

    def get(self, seq: int) -> LogEntry | None:
        """Fetch log entry by sequence number."""

    def len(self) -> int:
        """Total entries in the log."""

    def root_hash(self) -> Hash:
        """Merkle root of the entire log — the anchor point for a future
        blockchain commit."""

    def get_inclusion_proof(self, seq: int) -> MerkleInclusionProof | None:
        """Generate a cryptographic Merkle proof for external audit."""

    def verify_inclusion(self, proof: MerkleInclusionProof) -> bool:
        """Verify an inclusion proof against the current root_hash."""
```

**Key point:** `root_hash()` is the single value that, if committed to a
blockchain later, makes the *entire history* trustlessly verifiable. The
inclusion-proof methods make that verifiability *portable* — an external auditor
can check a single entry against a published root without trusting us.

---

## The unified Storage interface

```python
class Storage:
    """The single interface the verification layer talks to."""

    # Sub-interfaces
    objects: ObjectStore
    graph: GraphIndex
    log: AppendLog

    def commit_edge_tx(
        self,
        edge_bytes: bytes,
        premises: Sequence[Hash],
        conclusion: Hash,
        signer_pubkey: bytes,
        signature: bytes,
        proof_bytes: bytes | None = None,
    ) -> tuple[Hash, LogEntry]:
        """
        Atomic commit across all three subsystems:
        1. Store proof (if provided) and edge in ObjectStore.
        2. Register nodes and edge connectivity in GraphIndex.
        3. Append signed entry to AppendLog.
        Returns (edge_hash, log_entry).
        """
```

**Why `commit_edge_tx`:** a single reasoning step touches all three
sub-interfaces. Without an atomic transaction, a crash or I/O failure midway
leaves the store corrupted (an edge indexed in the graph but missing from the
object store or append log). The transaction guarantees all-or-nothing.

---

## What the verification layer does NOT ask storage to do

- **No proof checking.** Storage never inspects proof content.
- **No κ computation.** Storage never labels strength.
- **No ELENCHUS.** Storage never vetoes.
- **No AND-OR resolution.** Storage never decides reachability across
  multi-premise hyper-edges.
- **No refutation resolution.** Storage never computes the active subgraph.
- **No signature *verification* of edge content** (only of log entries, for
  provenance). Edge-signature verification is the verification layer's job.

This is the discipline that keeps the boundary clean: **storage is a dumb,
fast, append-only content-addressed graph. All judgment is above it.**

---

## Serialization contract

Nodes and edges are serialized to bytes *by the verification layer* before
`put`. The storage layer treats them as opaque. The serialization format is a
verification-layer concern — but it must be **canonical** (deterministic byte
output) so that content-addressing is stable across implementations.

**Decision (recorded):** Canonical CBOR (RFC 8949) — deterministic key sorting,
binary compact, native support in Python (`cbor2`) and Go (`fxamacker/cbor`).
Avoids JSON float/whitespace ambiguity.

---

## Go & IPC migration readiness (Phase 6)

The dataclasses above map 1:1 to protobuf messages (`bytes` for hashes and
signatures, `repeated` for batches and premises), so the Go engine can be
exposed over gRPC without changing the contract.

Concurrency invariants for the Go implementation:
- **ObjectStore** — concurrent lock-free reads, deduplicated append.
- **GraphIndex** — read-shared / write-exclusive, or MVCC.
- **AppendLog** — serialized atomic appends with synchronized Merkle recalculation.

---

## Resolved decisions (2026-08-26)

| Question | Decision |
|----------|----------|
| Serialization format | Canonical CBOR (RFC 8949) |
| Hash function | BLAKE3 (multihash-prefixed for agility) |
| Graph index backend | SQLite WAL (proto) → BadgerDB/Pebble (Go) |
| Key management | Per-agent Ed25519 keys + genesis roster |

Remaining open (deferred, not blocking Phase 1):
- Concurrency model for the Go engine (read-write lock vs MVCC).
