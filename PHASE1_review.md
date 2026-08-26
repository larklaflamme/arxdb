# ArxDB — Phase 1 Review & Architecture Recommendations

**Review Date:** 2026-08-26  
**Documents Reviewed:**
- [`PROJECT_STRUCTURE.md`](file:///home/ubuntu/arxdb/PROJECT_STRUCTURE.md)
- [`PHASE1_PLAN.md`](file:///home/ubuntu/arxdb/PHASE1_PLAN.md)
- [`PHASE1_TEST_PLAN.md`](file:///home/ubuntu/arxdb/PHASE1_TEST_PLAN.md)  
**Related Documents:** [`STORAGE_API.md`](file:///home/ubuntu/arxdb/STORAGE_API.md), [`DECISIONS.md`](file:///home/ubuntu/arxdb/DECISIONS.md), [`DESIGN.md`](file:///home/ubuntu/arxdb/DESIGN.md)

---

## 1. Executive Assessment

The Phase 1 planning documents establish a solid, production-grade foundation for ArxDB:
1. **Disciplined Architecture**: The upward-only dependency model (`Storage` $\leftarrow$ `Verification` $\leftarrow$ `Query`) guarantees that the storage layer remains strictly decoupled, making the future Go swap straightforward.
2. **Modular Incrementalism**: The 8-step module progression in [`PHASE1_PLAN.md`](file:///home/ubuntu/arxdb/PHASE1_PLAN.md) allows each component (`hashing`, `serialization`, `keys`, `object_store`, `merkle`, `graph_index`, `append_log`, `storage`) to be implemented and tested in isolation.
3. **Rigorous Verification Gate**: Combining unit tests, fault-injection tests for atomicity, and property-based tests (`hypothesis`) provides high assurance before moving to Phase 2.

Below are key technical refinements, edge cases, and design alignments to incorporate before or during Phase 1 execution.

---

## 2. Key Architecture Alignments & Clarifications

### 2.1 Reconcile `GraphIndex` Backend: SQLite WAL vs. In-Memory
* **Observation**: [`DECISIONS.md` (ADR-009)](file:///home/ubuntu/arxdb/DECISIONS.md#L154-L171) accepts **SQLite WAL mode** for the prototype index. However, [`PROJECT_STRUCTURE.md`](file:///home/ubuntu/arxdb/PROJECT_STRUCTURE.md#L86) and [`PHASE1_PLAN.md` Step 6](file:///home/ubuntu/arxdb/PHASE1_PLAN.md#L41-L45) describe `graph_index.py` as *"backed by in-memory dicts (prototype) with a persistence hook"*.
* **Recommendation**: Standardize directly on **SQLite with WAL mode** for both `graph_index.py` and `append_log.py` in Phase 1:
  - SQLite is standard-library in Python (`sqlite3`), adds zero external dependencies, provides immediate process crash-durability, and allows `GraphIndex` and `AppendLog` to share a single atomic transaction context during `commit_edge_tx`.

### 2.2 Shared SQLite Transaction for True Atomicity in `commit_edge_tx`
* **Observation**: [`PHASE1_PLAN.md` § commit_edge_tx](file:///home/ubuntu/arxdb/PHASE1_PLAN.md#L54-L68) specifies an all-or-nothing atomicity contract across `ObjectStore`, `GraphIndex`, and `AppendLog`.
* **Mechanism**:
  1. `ObjectStore` writes immutable files to disk (content-addressed blobs are idempotent; an orphaned blob in `objects/` causes zero corruption).
  2. `GraphIndex` and `AppendLog` can execute within the **same SQLite transaction** (`BEGIN IMMEDIATE` ... `COMMIT`).
  3. If log signing or appending fails, the SQLite transaction automatically rolls back all graph adjacency updates, leaving the database perfectly consistent.

### 2.3 Filesystem Sharding for `ObjectStore` (Prevent Inode Bottlenecks)
* **Observation**: Storing all content-addressed files flatly in a single `objects/<hex>` directory will cause filesystem degradation once the graph reaches tens of thousands of claims/proofs.
* **Recommendation**: Use a 2-character prefix subfolder structure (similar to Git and IPFS):
  - Path: `data/objects/{hash[:2]}/{hash[2:]}`
  - Example: Hash `1e20a3b8...` stored at `data/objects/1e/20a3b8...`
  - Implement atomic write via temp-file creation and `os.replace` to prevent partial reads during concurrent access.

### 2.4 Cryptographic Domain Separation in `merkle.py`
* **Observation**: Naive binary Merkle trees are susceptible to **second-preimage attacks** if leaf nodes and internal nodes use the same hash calculation.
* **Recommendation**: Implement RFC 6962 domain separation prefixes:
  - Leaf hash: $\text{BLAKE3}(\mathtt{0x00} \mathbin{\Vert} \text{leaf\_data})$
  - Internal node: $\text{BLAKE3}(\mathtt{0x01} \mathbin{\Vert} \text{left\_child} \mathbin{\Vert} \text{right\_child})$
  - Empty tree sentinel: $\text{BLAKE3}(\mathtt{0x02} \mathbin{\Vert} \mathtt{""})$

---

## 3. Module-by-Module Technical Recommendations

| Module | Key Considerations & Invariants |
| :--- | :--- |
| **`hashing.py`** | • Define `Hash = NewType("Hash", bytes)` (34-byte multihash: `0x1e` code + `0x20` length + 32-byte BLAKE3 digest).<br>• Provide `hash_bytes(data: bytes) -> Hash`, `from_hex(str) -> Hash`, and `to_hex(Hash) -> str`. |
| **`serialization.py`** | • Use `cbor2.dumps(obj, canonical=True)` for strict RFC 8949 compliance.<br>• Ensure custom types (`Hash`, tuples, sets) serialize deterministically (e.g. tuples as definite-length arrays, sets sorted before encoding). |
| **`keys.py`** | • Use `cryptography.hazmat.primitives.asymmetric.ed25519`.<br>• Invariants: Public key is exactly 32 bytes; signature is exactly 64 bytes.<br>• Support raw byte exports (`public_bytes_raw()`, `private_bytes_raw()`). |
| **`object_store.py`** | • Atomic write pattern: write to `objects/.tmp_{uuid}`, fsync, rename to `objects/{xx}/{yyy...}`.<br>• `put_batch` and `get_batch` should support parallel disk I/O / thread pools where appropriate.<br>• `has(h)` uses fast `os.path.exists` without file read. |
| **`graph_index.py`** | • SQLite schema with tables: `nodes(node_hash BLOB PRIMARY KEY)`, `edges(edge_hash BLOB PRIMARY KEY, conclusion BLOB)`, `premises(edge_hash BLOB, premise_hash BLOB, position INT)`.<br>• Create indices on `edges(conclusion)` and `premises(premise_hash)` for instant $O(1)$ adjacency lookups. |
| **`merkle.py`** | • Support dynamic appending with incremental Merkle updates (e.g., maintaining right-hand frontier peaks or standard complete tree rebuild for prototype).<br>• Inclusion proof format: `tuple[tuple[str, Hash], ...]` indicating `left`/`right` sibling hashes. |
| **`append_log.py`** | • SQLite table: `log(seq INTEGER PRIMARY KEY, timestamp_ns INT, signer_pubkey BLOB, entry_hash BLOB, prev_log_hash BLOB, signature BLOB)`.<br>• Genesis state: entry 0 has `prev_log_hash = b"\x00" * 34`.<br>• Verify signature over `canonical_encode(seq, timestamp_ns, signer_pubkey, entry_hash, prev_log_hash)`. |
| **`storage.py`** | • Top-level `Storage.open(root_dir: Path | str) -> Storage` factory creating directory hierarchy (`root/objects/`, `root/index.db`).<br>• Implement `commit_edge_tx` wrapping SQLite transaction. |

---

## 4. Test Plan Enhancements ([`PHASE1_TEST_PLAN.md`](file:///home/ubuntu/arxdb/PHASE1_TEST_PLAN.md))

### 4.1 Dependency Updates
Add `hypothesis` to dependencies in [`PHASE1_PLAN.md`](file:///home/ubuntu/arxdb/PHASE1_PLAN.md) table under dev dependencies.

### 4.2 Additional Recommended Test Scenarios

1. **Genesis & Empty-State Behavior**:
   - `AppendLog.root_hash()` returns a valid deterministic sentinel hash on an empty log.
   - `AppendLog.len() == 0`, `AppendLog.get(0) is None`.
   - `GraphIndex.incoming_edges(unregistered_node) == []`.
   - `ObjectStore.get_batch([]) == []`.

2. **Merkle Second-Preimage Attack Resistance**:
   - Verify that an internal node hash cannot be verified as an authentic leaf in `verify_inclusion`.

3. **Crash Recovery & Process Restart (Durability)**:
   - Instantiate `Storage`, execute 100 `commit_edge_tx` transactions, close `Storage`.
   - Instantiate new `Storage` pointing to the same directory.
   - Assert all 100 objects, all graph connections, and all log entries with `root_hash` match exactly.

4. **Multi-Premise Hyper-Edge Ordering**:
   - Test that `premises=(A, B)` preserves exact premise indexing order in `get_connectivity` (crucial for non-commutative inference rules).

5. **Fault Injection Coverage in `test_storage_tx.py`**:
   - **Fault 1**: ObjectStore write failure (disk full / permission error) $\to$ no GraphIndex or LogEntry created.
   - **Fault 2**: Signature verification failure $\to$ transaction rejected, no GraphIndex or LogEntry committed.
   - **Fault 3**: Simulated crash after SQLite write before return $\to$ state remains recoverable and non-corrupted.

---

## 5. Summary & Readiness Sign-Off

The project structure, Phase 1 implementation plan, and test plan are well-conceived and ready for execution.

**Action items before starting implementation:**
- [x] Update `PHASE1_PLAN.md` to list `hypothesis` in dependencies.
- [x] Explicitly note SQLite WAL backend in `PROJECT_STRUCTURE.md` and `PHASE1_PLAN.md` to match `DECISIONS.md`.
- [x] Incorporate domain separation in `merkle.py` and 2-level directory sharding in `object_store.py`.
