# ArxDB — Storage API (v0.3)

The boundary between the verification layer (Python, permanent) and the storage
layer (Python prototype → Go). This interface is the contract that makes the
swap a drop-in replacement, not a rewrite.

> **v0.3 changelog** (reconciled to Phase 1 implementation): `add_node`/`add_edge`
> renamed to `register_node`/`register_edge`; `EdgeConnectivity` dataclass replaced
> by a `(premises, conclusion)` tuple return; `commit_edge_tx` simplified to
> `(premises, conclusion, edge_data, proof)` with the keypair held internally;
> `LogEntry` gained `payload`; `AppendLog.append` takes the raw entry bytes and
> signs internally; `MerkleInclusionProof` uses `leaf_hash`/`index`/`path`; the
> `hashing`/`serialization`/`keys`/`merkle` module-level APIs are now documented.

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

## 0. Primitives (shared by all sub-interfaces)

### Hashing (`hashing.py`)

```python
class Hash(bytes):
    """A 34-byte BLAKE3 multihash: 0x1e ‖ 0x20 ‖ 32-byte digest."""

def hash_bytes(data: bytes) -> Hash: ...
def hash_hex(data: bytes) -> str: ...
def from_hex(hexstr: str) -> Hash: ...
def is_valid_hash(h: bytes) -> bool: ...
```

### Serialization (`serialization.py`)

```python
def canonical_encode(obj) -> bytes: ...
def canonical_decode(data: bytes) -> obj: ...
```

**Invariant:** `canonical_encode(x) == canonical_encode(y)` iff `x == y`
(structurally). Tuples encode as definite-length arrays, sets as sorted lists,
`Hash` as a byte string.

### Keys (`keys.py`)

```python
def generate_keypair() -> tuple[bytes, bytes]:  # (priv_seed, pub) — 32 bytes each
def sign(priv: bytes, message: bytes) -> bytes:  # 64-byte Ed25519 signature
def verify(pub: bytes, message: bytes, sig: bytes) -> bool: ...
```

---

## 1. Object store (content-addressed)

```python
class ObjectStore:
    def put(self, data: bytes) -> Hash:
        """Store bytes, return content hash (BLAKE3). Idempotent: same bytes
        → same hash, no duplicate storage."""

    def put_batch(self, items: list[bytes]) -> list[Hash]:
        """Store multiple blobs. Returns hashes in order."""

    def get(self, h: Hash) -> bytes | None:
        """Return bytes for hash, or None if absent."""

    def get_batch(self, hashes: list[Hash]) -> list[bytes | None]:
        """Fetch multiple blobs (parallel to input)."""

    def has(self, h: Hash) -> bool:
        """Membership check without fetching the body."""

    def has_batch(self, hashes: list[Hash]) -> list[bool]:
        """Membership check for multiple hashes."""
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
class GraphIndex:
    def register_node(self, node_hash: Hash) -> None:
        """Register a node (claim) in the index."""

    def register_edge(self, edge_hash: Hash,
                      premises: list[Hash],
                      conclusion: Hash) -> None:
        """Register a hyper-edge and its connectivity: premises → conclusion.
        Also registers the endpoints so the graph stays self-consistent."""

    def incoming_edges(self, node_hash: Hash) -> list[Hash]:
        """All edge hashes whose conclusion == node_hash."""

    def outgoing_edges(self, node_hash: Hash) -> list[Hash]:
        """All edge hashes whose premises contain node_hash."""

    def get_connectivity(self, edge_hash: Hash) -> tuple[list[Hash], Hash] | None:
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
    entry_hash: Hash        # content hash of `payload`
    prev_log_hash: Hash
    signature: bytes        # over canonical_encode([seq, ts, pubkey, entry_hash, prev_log_hash])
    payload: bytes          # the raw entry bytes


@dataclass(frozen=True)
class MerkleInclusionProof:
    leaf_hash: Hash
    index: int
    path: list[Hash]        # sibling hashes, bottom-up


class AppendLog:
    def append(self, entry: bytes) -> LogEntry:
        """Append `entry`, signing internally with the agent's keypair."""

    def get(self, seq: int) -> LogEntry | None:
        """Fetch log entry by sequence number."""

    def __len__(self) -> int:
        """Total entries in the log."""

    def root_hash(self) -> Hash:
        """Merkle root of the entire log — the anchor point for a future
        blockchain commit."""

    def get_inclusion_proof(self, seq: int) -> MerkleInclusionProof:
        """Generate a cryptographic Merkle proof for external audit."""

    def verify_entry(self, entry: LogEntry) -> bool:
        """Verify an entry's signature AND that entry_hash == hash(payload)."""
```

**Key point:** `root_hash()` is the single value that, if committed to a
blockchain later, makes the *entire history* trustlessly verifiable. The
inclusion-proof methods make that verifiability *portable* — an external auditor
can check a single entry against a published root without trusting us.

**Merkle module functions (`merkle.py`):**

```python
def root_hash(leaf_hashes: list[Hash]) -> Hash: ...
def inclusion_proof(leaf_hashes: list[Hash], index: int) -> MerkleInclusionProof: ...
def verify_inclusion(proof: MerkleInclusionProof, root: Hash) -> bool: ...
```

---

## The unified Storage interface

```python
class Storage:
    """The single interface the verification layer talks to."""

    # Sub-interfaces
    objects: ObjectStore
    graph: GraphIndex
    log: AppendLog

    def __init__(self, root: Path, priv_key: bytes, pub_key: bytes) -> None:
        """Owns one SQLite connection shared by graph + log (for atomicity)."""

    def commit_edge_tx(
        self,
        premises: list[Hash],
        conclusion: Hash,
        edge_data: bytes,
        proof: bytes | None = None,
    ) -> tuple[Hash, LogEntry]:
        """
        Atomic commit across all three subsystems:
        1. Store edge_data (and proof, if provided) in ObjectStore.
        2. Register nodes + edge connectivity in GraphIndex.
        3. Append signed entry to AppendLog.
        Returns (edge_hash, log_entry).
        """

    def close(self) -> None:
        """Close the underlying SQLite connection."""
```

**Why `commit_edge_tx`:** a single reasoning step touches all three
sub-interfaces. Without an atomic transaction, a crash or I/O failure midway
leaves the store corrupted (an edge indexed in the graph but missing from the
object store or append log). The transaction guarantees all-or-nothing.

**Note on the proof:** `commit_edge_tx` stores the proof blob in ObjectStore but
does *not* return its hash. A caller retrieves it by computing `hash_bytes(proof)`
themselves. Phase 2's edge schema makes the edge→proof binding explicit via a
`proof_hash` field in the edge record.

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
