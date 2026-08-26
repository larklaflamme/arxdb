# ArxDB — Storage API Review (STORAGE_API.md)

**Review Date:** 2026-08-26  
**Document Reviewed:** [`STORAGE_API.md`](file:///home/ubuntu/arxdb/STORAGE_API.md) (draft v0.1)  
**Related Documents:** [`DESIGN.md`](file:///home/ubuntu/arxdb/DESIGN.md), [`DECISIONS.md`](file:///home/ubuntu/arxdb/DECISIONS.md), [`ROADMAP.md`](file:///home/ubuntu/arxdb/ROADMAP.md), [`DESIGN_review.md`](file:///home/ubuntu/arxdb/DESIGN_review.md)

---

## 1. Executive Evaluation

The design principle articulated in [`STORAGE_API.md`](file:///home/ubuntu/arxdb/STORAGE_API.md) is sound and disciplined:
> *"The storage layer is **dumb and fast**. It knows nothing about verification semantics, $\kappa$-strength, or proof correctness... All meaning lives in the verification layer above it."*

Splitting the responsibilities into **ObjectStore** (content-addressed blobs), **GraphIndex** (connectivity), and **AppendLog** (provenance/Merkle root) provides the clean modularity required to swap a Python prototype for a high-concurrency Go engine without touching verification logic.

However, the current draft has several API contract omissions, naming ambiguities, graph traversal mismatches, and cryptographic verifiability gaps that should be addressed before Phase 1 code is written.

---

## 2. Key Findings & Critical Gaps

### 2.1 Hypergraph vs. Simple Digraph Mismatch in `GraphIndex`

In [`STORAGE_API.md` §2](file:///home/ubuntu/arxdb/STORAGE_API.md#L66-L72), `GraphIndex` defines:
```python
def reachable(self, from_hashes: list[Hash], to_hash: Hash) -> bool: ...
def shortest_path(self, from_hashes: list[Hash], to_hash: Hash) -> list[Hash] | None: ...
```

* **The Problem**: 
  1. An inference step in ArxDB is a hyper-edge: $P_1 \land P_2 \land \dots \to C$. If `GraphIndex` is "dumb" and runs standard BFS/Dijkstra digraph traversal, it will mark $C$ as reachable as soon as *any one* premise is connected. This is logically unsound.
  2. Pure topological reachability ignores verification status ($\kappa$-strength, ELENCHUS vetoes, active refutations).
* **Recommendation**:
  - Remove semantic `reachable` and `shortest_path` from the dumb storage layer, or restrict them to explicit topological connectivity queries.
  - Storage should provide fast structural adjacency primitives (`incoming_edges`, `outgoing_edges`, `get_connectivity`), while the **Verification/Query Layer** executes AND-OR proof-tree resolution and $\kappa$-threshold filtering.

---

### 2.2 Naming Ambiguity: Nodes vs. Edges

In [`STORAGE_API.md` §2](file:///home/ubuntu/arxdb/STORAGE_API.md#L60-L64):
```python
def predecessors(self, node_hash: Hash) -> list[Hash]:
    """Edges whose conclusion is this node."""
def successors(self, node_hash: Hash) -> list[Hash]:
    """Edges whose premises include this node."""
```

* **The Problem**: In graph theory and standard graph libraries (NetworkX, igraph), `predecessors(n)` returns *neighbor nodes* that have edges to $n$. Here, it returns *edge hashes*. This will lead to type confusion.
* **Recommendation**: Standardize names:
  - `incoming_edges(node_hash: Hash) -> list[Hash]`
  - `outgoing_edges(node_hash: Hash) -> list[Hash]`
  - `get_edge_connectivity(edge_hash: Hash) -> EdgeConnectivity` (returning `premises: list[Hash]`, `conclusion: Hash`)

---

### 2.3 Lack of Atomic Multi-Subsystem Commit (Consistency Hazard)

Storing a single reasoning step requires updates across all three sub-interfaces:
1. `ObjectStore.put(proof_bytes)` & `ObjectStore.put(edge_bytes)`
2. `GraphIndex.add_edge(edge_hash, premises, conclusion)`
3. `AppendLog.append(log_entry, signature)`

* **The Problem**: Without an atomic transaction or unified commit method, a process crash or I/O failure midway leaves the store corrupted (e.g., an edge indexed in the graph but missing in the append log or object store).
* **Recommendation**: Provide an atomic transaction / batch ingestion method in `Storage`:
```python
def commit_edge(
    self,
    edge_bytes: bytes,
    premises: list[Hash],
    conclusion: Hash,
    signature: bytes,
    signer_pubkey: bytes,
    proof_bytes: bytes | None = None
) -> tuple[Hash, LogEntry]: ...
```

---

### 2.4 Missing Batch / High-Throughput I/O Operations

The current `ObjectStore` only exposes single-item operations (`put`, `get`, `has`).

* **The Problem**: When traversing a proof tree or importing a multi-step derivation (e.g., 50 intermediate lemmas from the RH phaser thread), issuing 50 individual synchronous `get()` calls incurs heavy I/O overhead.
* **Recommendation**: Add batch methods:
  - `put_batch(items: list[bytes]) -> list[Hash]`
  - `get_batch(hashes: list[Hash]) -> list[bytes | None]`
  - `has_batch(hashes: list[Hash]) -> list[bool]`

---

### 2.5 `AppendLog` & Merkle Verifiability Gaps

In [`STORAGE_API.md` §3](file:///home/ubuntu/arxdb/STORAGE_API.md#L83-L96), `AppendLog` defines `root_hash()` and `verify(seq: int) -> bool`.

* **The Problem**:
  1. `LogEntry` structure is not formally defined.
  2. To anchor to a blockchain or prove tampering to an external auditor, the API must provide **Merkle inclusion proofs** (audit paths), not just a local boolean check.
* **Recommendation**:
  - Define `LogEntry` with `seq`, `timestamp`, `signer_pubkey`, `entry_hash`, `prev_entry_hash`, `signature`.
  - Expose `get_inclusion_proof(seq: int) -> MerkleProof` and `verify_inclusion(root: Hash, proof: MerkleProof) -> bool`.

---

## 3. Proposed Revised Storage API Specification

Here is the recommended concrete Python interface specification for Phase 1.

```python
from dataclasses import dataclass
from typing import NewType, Sequence

# Canonical 32-byte BLAKE3 hash
Hash = NewType("Hash", bytes)


@dataclass(frozen=True)
class EdgeConnectivity:
    edge_hash: Hash
    premises: tuple[Hash, ...]
    conclusion: Hash


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


class ObjectStore:
    """Immutable, content-addressed blob store."""

    def put(self, data: bytes) -> Hash:
        """Store bytes, return BLAKE3 hash. Idempotent."""
        ...

    def put_batch(self, items: Sequence[bytes]) -> list[Hash]:
        """Store multiple blobs atomically or in a batch."""
        ...

    def get(self, h: Hash) -> bytes | None:
        """Fetch bytes for hash, or None if absent."""
        ...

    def get_batch(self, hashes: Sequence[Hash]) -> list[bytes | None]:
        """Fetch multiple blobs in a single round-trip."""
        ...

    def has(self, h: Hash) -> bool:
        """Check presence without fetching body."""
        ...


class GraphIndex:
    """Structural index of node and hyper-edge connectivity."""

    def add_node(self, node_hash: Hash) -> None:
        """Index a node/claim."""
        ...

    def add_edge(self, edge_hash: Hash, premises: Sequence[Hash], conclusion: Hash) -> None:
        """Index an inference step."""
        ...

    def incoming_edges(self, node_hash: Hash) -> list[Hash]:
        """Return all edge hashes where conclusion == node_hash."""
        ...

    def outgoing_edges(self, node_hash: Hash) -> list[Hash]:
        """Return all edge hashes where premises contain node_hash."""
        ...

    def get_connectivity(self, edge_hash: Hash) -> EdgeConnectivity | None:
        """Fetch premises and conclusion for an edge without loading full object payload."""
        ...

    def get_premises(self, edge_hash: Hash) -> list[Hash]:
        """Fetch premise node hashes for an edge."""
        ...

    def get_conclusion(self, edge_hash: Hash) -> Hash | None:
        """Fetch conclusion node hash for an edge."""
        ...

    def leaf_nodes(self) -> list[Hash]:
        """Nodes with no incoming edges (assumptions, axioms, or open frontiers)."""
        ...


class AppendLog:
    """Cryptographically signed, append-only provenance log."""

    def append(self, entry_hash: Hash, signer_pubkey: bytes, signature: bytes) -> LogEntry:
        """Append an entry hash with signer's Ed25519 signature."""
        ...

    def get(self, seq: int) -> LogEntry | None:
        """Fetch log entry by sequence number."""
        ...

    def len(self) -> int:
        """Total entries in log."""
        ...

    def root_hash(self) -> Hash:
        """Current Merkle tree root hash for blockchain anchoring."""
        ...

    def get_inclusion_proof(self, seq: int) -> MerkleInclusionProof | None:
        """Generate cryptographic Merkle proof for external audit."""
        ...

    def verify_inclusion(self, proof: MerkleInclusionProof) -> bool:
        """Verify an inclusion proof against root_hash."""
        ...


class Storage:
    """Unified storage engine combining ObjectStore, GraphIndex, and AppendLog."""

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
        """
        ...
```

---

## 4. Go & IPC Migration Readiness

When transitioning to the Go storage engine (Phase 6):
1. **gRPC / Protocol Buffers**: The above dataclasses map 1:1 to standard protobuf messages (`bytes` fields for hashes/signatures, repeated fields for batches/premises).
2. **Concurrency Invariants**:
   - `ObjectStore`: Concurrent lock-free reads, deduplicated append.
   - `GraphIndex`: Concurrent read-shared / write-exclusive or MVCC index.
   - `AppendLog`: Serialized atomic appends with synchronized Merkle tree recalculation.

---

## 5. Summary of Recommended Edits to `STORAGE_API.md`

1. **Replace `predecessors` / `successors`** with explicit `incoming_edges` / `outgoing_edges` / `get_connectivity`.
2. **Move AND-OR reachability and $\kappa$-filtering** to the Verification/Query Layer specification; keep `GraphIndex` purely structural.
3. **Add Batching Methods** (`put_batch`, `get_batch`) to `ObjectStore`.
4. **Specify `LogEntry` and Merkle Inclusion Proofs** in `AppendLog`.
5. **Add `commit_edge_tx`** to guarantee multi-store atomicity.
