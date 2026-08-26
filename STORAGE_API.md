# ArxDB — Storage API (draft v0.1)

The boundary between the verification layer (Python, permanent) and the storage
layer (Python prototype → Go). This interface is the contract that makes the
swap a drop-in replacement, not a rewrite.

## Design principle

The storage layer is **dumb and fast**. It knows nothing about verification
semantics, κ-strength, or proof correctness. It stores opaque content-addressed
objects, maintains a graph index for traversal, and keeps an append-only log for
provenance. All *meaning* lives in the verification layer above it.

Three responsibilities, three sub-interfaces:

1. **Object store** — content-addressed put/get (immutable blobs).
2. **Graph index** — node→edge adjacency for traversal.
3. **Append log** — ordered, signed sequence of appends (provenance).

---

## 1. Object store (content-addressed)

```python
class ObjectStore:
    def put(self, data: bytes) -> Hash:
        """Store bytes, return content hash (BLAKE3). Idempotent: same bytes
        → same hash, no duplicate storage."""

    def get(self, h: Hash) -> bytes | None:
        """Return bytes for hash, or None if absent."""

    def has(self, h: Hash) -> bool:
        """Membership check."""
```

**Invariants:**
- `put` is idempotent and content-addressed: `put(x) == put(x)` always.
- `get(put(x)) == x` always.
- Objects are immutable once stored (append-only).

---

## 2. Graph index (traversal)

The storage layer *does* understand the minimal graph structure — enough to
traverse, not enough to judge. Nodes and edges are typed records; the storage
layer indexes their connectivity.

```python
class GraphIndex:
    def add_node(self, node_hash: Hash) -> None:
        """Register a node (claim) in the index."""

    def add_edge(self, edge_hash: Hash,
                 premises: list[Hash],
                 conclusion: Hash) -> None:
        """Register an edge and its connectivity: premises → conclusion."""

    def predecessors(self, node_hash: Hash) -> list[Hash]:
        """Edges whose conclusion is this node."""

    def successors(self, node_hash: Hash) -> list[Hash]:
        """Edges whose premises include this node."""

    def reachable(self, from_hashes: list[Hash], to_hash: Hash) -> bool:
        """Is there a directed path from any of `from_hashes` to `to_hash`?"""

    def shortest_path(self, from_hashes: list[Hash], to_hash: Hash
                      ) -> list[Hash] | None:
        """Return the edge-hash path (or None). Hop count = len(path)."""
```

**Key point:** the index stores *connectivity* (which edges touch which nodes),
not *content*. The verification layer decides what an edge *means*; the storage
layer just knows it connects A to B.

---

## 3. Append log (provenance)

```python
class AppendLog:
    def append(self, entry: bytes, signature: bytes) -> LogEntry:
        """Append a signed entry; return (sequence_number, entry_hash)."""

    def get(self, seq: int) -> LogEntry | None:
        """Fetch entry by sequence number."""

    def root_hash(self) -> Hash:
        """Merkle root of the entire log — the anchor point for a future
        blockchain commit."""

    def verify(self, seq: int) -> bool:
        """Verify the signature and Merkle path for entry `seq`."""
```

**Key point:** `root_hash()` is the single value that, if committed to a
blockchain later, makes the *entire history* trustlessly verifiable. This is the
"blockchain-anchorable" seam.

---

## The unified Storage interface

```python
class Storage:
    """The single interface the verification layer talks to."""

    # Object store
    def put(self, data: bytes) -> Hash: ...
    def get(self, h: Hash) -> bytes | None: ...

    # Graph index
    def add_node(self, node_hash: Hash) -> None: ...
    def add_edge(self, edge_hash: Hash, premises: list[Hash],
                 conclusion: Hash) -> None: ...
    def reachable(self, from_hashes: list[Hash], to_hash: Hash) -> bool: ...
    def shortest_path(self, from_hashes: list[Hash], to_hash: Hash
                      ) -> list[Hash] | None: ...

    # Append log
    def append(self, entry: bytes, signature: bytes) -> LogEntry: ...
    def root_hash(self) -> Hash: ...
```

---

## What the verification layer does NOT ask storage to do

- **No proof checking.** Storage never inspects proof content.
- **No κ computation.** Storage never labels strength.
- **No ELENCHUS.** Storage never vetoes.
- **No signature *verification* of edge content** (only of log entries, for
  provenance). Edge-signature verification is the verification layer's job.

This is the discipline that keeps the boundary clean: **storage is a dumb,
fast, append-only content-addressed graph. All judgment is above it.**

---

## Serialization contract

Nodes and edges are serialized to bytes *by the verification layer* before
`put`. The storage layer treats them as opaque. The serialization format
(JSON, CBOR, msgpack) is a verification-layer concern — but it must be
**canonical** (deterministic byte output) so that content-addressing is stable
across implementations. Recommendation: **CBOR with canonical ordering**, or
JSON with sorted keys. This is a decision to record (see open questions).

---

## Open questions (for the interface)

1. **Serialization format** — canonical JSON vs CBOR vs msgpack? Must be
   deterministic for content-addressing.
2. **Hash function** — BLAKE3 (fast, modern) vs SHA-256 (ubiquitous, FIPS)?
   Leaning BLAKE3 for speed; SHA-256 if we need FIPS compliance for the
   enterprise AI-audit use case.
3. **Graph index implementation** — in-memory adjacency (prototype) vs
   on-disk (SQLite/RocksDB) vs embedded (BadgerDB in Go)? The interface above
   is agnostic; the choice is a storage-layer-internal detail.
4. **Concurrency model** — the interface is synchronous; the Go implementation
   will need to decide read-write locking vs MVCC. Not visible at this boundary.
