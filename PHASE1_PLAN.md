# ArxDB — Phase 1 Implementation Plan

**Goal:** a correct, tested, content-addressed, signed, append-only storage
substrate in Python, behind the exact interface in `STORAGE_API.md`.

**Scope:** the storage layer only. No verification, no query, no edge schema.

## Dependencies (add to `pyproject.toml`)

| Package | Why | Kind |
|---------|-----|------|
| `blake3` | content hashing (fast, native bindings) | runtime |
| `cbor2` | canonical CBOR serialization (deterministic bytes) | runtime |
| `cryptography` | Ed25519 sign/verify (stdlib-grade, audited) | runtime |
| `pytest` | test runner | dev |
| `hypothesis` | property-based tests | dev |

## Implementation order (each step is independently testable)

1. **`hashing.py`** — `Hash` type and BLAKE3 multihash.
   - `class Hash(bytes)` — a **34-byte multihash**: `0x1e` (BLAKE3
     code) ‖ `0x20` (32-byte length) ‖ 32-byte digest. A `bytes` subclass
     (not a `NewType`) because runtime length validation in `__new__` beats a
     type-only alias for a value that must be exactly 34 bytes.
   - `hash_bytes(data: bytes) -> Hash`, `from_hex(str) -> Hash`,
     `to_hex(Hash) -> str`.
   - *No dependencies.*

2. **`serialization.py`** — `canonical_encode(obj) -> bytes` and
   `canonical_decode(bytes) -> obj` using `cbor2.dumps(obj, canonical=True)`
   (strict RFC 8949: sorted keys, definite-length arrays).
   - Custom types (`Hash`, tuples, sets) must serialize deterministically:
     tuples as definite-length arrays, sets sorted before encoding.
   - **Invariant:** `canonical_encode(x) == canonical_encode(y)` iff `x == y`
     (structurally). This is what makes content-addressing stable.
   - *No dependencies.*

3. **`keys.py`** — `generate_keypair() -> (priv, pub)`, `sign(priv, msg)`,
   `verify(pub, msg, sig)`. Ed25519 via
   `cryptography.hazmat.primitives.asymmetric.ed25519`.
   - **Invariants:** public key is exactly 32 bytes; signature is exactly 64
     bytes. Support raw byte exports (`public_bytes_raw()`,
     `private_bytes_raw()`).
   - *No dependencies.*

4. **`object_store.py`** — `ObjectStore` with `put`, `put_batch`, `get`,
   `get_batch`, `has`, `has_batch`. Backed by a **sharded** directory of files.
   - **Sharding:** 2-char prefix subfolders — `objects/{hash[:2]}/{hash[2:]}`.
     Prevents inode bottlenecks at scale (same pattern as Git/IPFS).
   - **Atomic write:** write to `objects/.tmp_{uuid}`, `fsync`, then
     `os.replace` to the final path. Prevents partial reads under concurrency.
   - `put` skips if the file already exists (idempotent), returns hash.
   - `has(h)` uses `os.path.exists` (no file read).
   - *Depends on hashing, serialization.*

5. **`merkle.py`** — Merkle tree over a sequence of leaf hashes. `root_hash()`,
   `inclusion_proof(seq)`, `verify_inclusion(proof, root)`.
   - **RFC 6962 domain separation** (prevents second-preimage attacks):
     - Leaf: `BLAKE3(0x00 ‖ leaf_data)`
     - Internal: `BLAKE3(0x01 ‖ left_child ‖ right_child)`
     - Empty sentinel: `BLAKE3(0x02 ‖ "")`
   - Balanced binary tree; odd counts duplicate the last node.
   - Inclusion proof format: `tuple[tuple[str, Hash], ...]` of `left`/`right`
     sibling hashes.
   - *Depends on hashing.*

6. **`graph_index.py`** — `GraphIndex` with `register_node`, `register_edge`,
   `incoming_edges`, `outgoing_edges`, `get_connectivity`. Backed by **SQLite
   (WAL mode)**.
   - Schema:
     - `nodes(node_hash BLOB PRIMARY KEY)`
     - `edges(edge_hash BLOB PRIMARY KEY, conclusion BLOB)`
     - `premises(edge_hash BLOB, premise_hash BLOB, position INT)`
   - Indices on `edges(conclusion)` and `premises(premise_hash)` for O(1)
     adjacency lookups.
   - `get_connectivity` returns a plain `(premises, conclusion)` tuple (not a
     dataclass) so callers can tuple-unpack it directly; `register_*` naming
     signals idempotency (re-registering is a no-op).
   - *No dependencies (uses stdlib `sqlite3`).*

7. **`append_log.py`** — `AppendLog` with `append`, `get`, `len`, `root_hash`,
   `get_inclusion_proof`, `verify_entry`. Backed by **SQLite (WAL mode)**,
   sharing the same database file as `graph_index.py`.
   - Table: `log(seq INTEGER PRIMARY KEY, timestamp_ns INT, signer_pubkey BLOB,
     entry_hash BLOB, prev_log_hash BLOB, signature BLOB, payload BLOB)`.
     (`payload` is stored in the log table so `get(seq)` can reconstruct the
     full `LogEntry` without an external object store.)
   - `LogEntry` carries `seq, timestamp_ns, signer_pubkey, entry_hash,
     prev_log_hash, signature, payload` — everything needed to verify it.
   - **Genesis:** entry 0 has `prev_log_hash = b"\x00" * 34`.
   - Signature is over `canonical_encode(seq, timestamp_ns, signer_pubkey,
     entry_hash, prev_log_hash)`; `entry_hash = hash_bytes(payload)`.
   - `verify_entry(entry)` checks both the signature and that
     `entry_hash == hash_bytes(payload)` (payload integrity).
   - *Depends on merkle, keys, serialization.*

8. **`storage.py`** — `Storage` composing the three sub-interfaces, plus
   `commit_edge_tx` (atomic across all three).
   - `Storage.open(root_dir: Path | str) -> Storage` factory creating the
     directory hierarchy (`root/objects/`, `root/index.db`).
   - *Depends on all above.*

## `commit_edge_tx` — the atomicity contract

```
commit_edge_tx(premises, conclusion, edge_data, proof=None)
    -> (edge_hash, log_entry)
```

`Storage` holds the agent's keypair (passed to `__init__`) and signs the log
entry internally, so `signer_pubkey`/`signature` are not caller-supplied args.
`edge_hash = hash_bytes(edge_data)` — the edge is content-addressed by its
payload; premises/conclusion live in the graph index keyed by that hash.

The atomicity is achieved by **splitting the two failure domains**:

1. **ObjectStore (filesystem, idempotent):** write `proof_bytes` (if any) and
   `edge_bytes`. Blobs are content-addressed and idempotent — an orphaned blob
   causes zero corruption, so this step needs no rollback.

2. **GraphIndex + AppendLog (shared SQLite transaction):** `BEGIN IMMEDIATE`,
   register nodes + edge connectivity, append the signed log entry, `COMMIT`.
   If signing or appending fails, the transaction rolls back *all* graph
   adjacency updates automatically, leaving the database perfectly consistent.

   To make this possible, `GraphIndex` and `AppendLog` each accept an optional
   `conn` argument: when provided, they share that connection and do **not**
   commit (the owner controls the transaction); when `None`, they open their
   own connection and commit after each write (standalone use). `Storage` owns
   one connection (autocommit mode, `isolation_level=None`) and passes it to
   both, so `commit_edge_tx` can wrap graph + log in a single explicit
   `BEGIN IMMEDIATE … COMMIT`.

This is stronger than rollback-on-exception: it gives **process-crash
durability** for the mutable state, because SQLite WAL guarantees the
transaction is atomic even if the process dies mid-write. The only thing it
does *not* cover is a power-loss during the ObjectStore blob write — which is
harmless, because an orphaned blob is not corruption.

## Exit criteria (Phase 1 is "done" when ALL hold)

- [ ] `get(put(x)) == x` for arbitrary bytes, verified by property test.
- [ ] `put` is idempotent: `put(x) == put(x)`.
- [ ] Store survives process restart (reopen → `get` still works).
- [ ] `root_hash()` is deterministic and changes when any entry changes.
- [ ] `verify_inclusion(get_inclusion_proof(seq))` is `True` for every seq.
- [ ] Tampering with a stored object is detectable (inclusion proof fails).
- [ ] Merkle second-preimage attack is resisted (internal node ≠ valid leaf).
- [ ] `commit_edge_tx` is atomic under injected failure (all three fault cases).
- [ ] Full test suite green (`pytest`), no skipped tests.

## Explicitly deferred (do NOT build in Phase 1)

- Edge schema / proof checking / κ labels → Phase 2.
- AND-OR traversal / the two queries → Phase 3.
- Go reimplementation → Phase 6 (gated by a latency trigger).
- Hand-rolled write-ahead journal → unnecessary; SQLite WAL provides it.
