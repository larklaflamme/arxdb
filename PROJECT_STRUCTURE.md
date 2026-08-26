# ArxDB — Project Structure

The high-level layout of the codebase, and the dependency discipline that keeps
the Python→Go swap a *replacement*, not a rewrite.

## The three layers (and their dependency direction)

```
┌──────────────────────────────────────────────────────────────┐
│  Query Layer (Python, permanent)                             │
│  AND-OR hyperpath traversal · proof-tree assembly            │
│  κ-threshold filtering · refutation resolution               │
│  → the two queries: reachability, path discovery             │
└──────────────────────────────────┬───────────────────────────┘
                                   │  depends on
┌──────────────────────────────────▼───────────────────────────┐
│  Verification Layer (Python, permanent)                      │
│  edge schema · ELENCHUS veto · formal checkers · κ labels    │
│  → the moat: what can you stand on?                          │
└──────────────────────────────────┬───────────────────────────┘
                                   │  depends on
┌──────────────────────────────────▼───────────────────────────┐
│  Storage Layer (Python now → Go later)                       │
│  ObjectStore · GraphIndex · AppendLog · Merkle               │
│  → dumb and fast: opaque blobs, connectivity, signed log     │
└──────────────────────────────────────────────────────────────┘
```

**The rule:** dependencies point *upward only*. Storage knows nothing about
verification or query semantics. Verification knows nothing about query
traversal. A layer may only import the layer directly beneath it. No cycles.

This is what makes the Go swap possible: the Go implementation only has to
satisfy the `Storage` interface (see `STORAGE_API.md`). Nothing above it changes.

## Storage backend split (Phase 1)

The storage layer uses **two physical backends**, chosen for their distinct
failure modes:

| Sub-interface | Backend | Why |
|---------------|---------|-----|
| `ObjectStore` | Filesystem, sharded (`objects/xx/…`) | Content-addressed blobs are immutable and idempotent; the filesystem is the natural home. Orphaned blobs are harmless. |
| `GraphIndex` | SQLite (WAL mode), table `nodes`/`edges`/`premises` | Structural adjacency is mutable and must be crash-durable. |
| `AppendLog` | SQLite (WAL mode), table `log` | Same — mutable, ordered, must survive process death. |

`GraphIndex` and `AppendLog` share **one SQLite database** (`data/index.db`) so
that `commit_edge_tx` can wrap both in a single `BEGIN IMMEDIATE … COMMIT`
transaction. This is what makes the atomicity contract *real* rather than
rollback-on-exception (see `PHASE1_PLAN.md`).

## Directory tree

```
arxdb/
├── README.md                  # product-facing first impression
├── DESIGN.md                  # architecture + reasoning-graph model
├── DECISIONS.md               # ADR log (what/why/rejected)
├── STORAGE_API.md             # the storage boundary contract
├── ROADMAP.md                 # execution phases + exit criteria
├── PROJECT_STRUCTURE.md       # this file
├── PHASE1_PLAN.md             # Phase 1 implementation plan
├── PHASE1_TEST_PLAN.md        # Phase 1 test plan
├── pyproject.toml             # package metadata + deps
├── src/
│   └── arxdb/
│       ├── __init__.py
│       ├── storage/           # ── PHASE 1 ──
│       │   ├── __init__.py
│       │   ├── hashing.py         # BLAKE3 multihash + Hash type
│       │   ├── serialization.py   # canonical CBOR encode/decode
│       │   ├── keys.py            # Ed25519 keypair + sign/verify
│       │   ├── object_store.py    # content-addressed put/get (sharded fs)
│       │   ├── graph_index.py     # structural adjacency (SQLite)
│       │   ├── merkle.py          # Merkle tree + inclusion proofs
│       │   ├── append_log.py      # signed append-only log (SQLite)
│       │   └── storage.py         # unified Storage + commit_edge_tx
│       ├── verification/     # ── PHASE 2 (later) ──
│       │   └── __init__.py
│       └── query/            # ── PHASE 3 (later) ──
│           └── __init__.py
├── tests/
│   ├── conftest.py               # fixtures: temp dirs, keypairs
│   ├── test_hashing.py
│   ├── test_serialization.py
│   ├── test_object_store.py
│   ├── test_graph_index.py
│   ├── test_merkle.py
│   ├── test_append_log.py
│   └── test_storage_tx.py
└── data/                     # runtime store (gitignored)
    ├── objects/              # content-addressed blobs
    │   └── xx/               # 2-char shard prefix
    └── index.db              # SQLite (WAL): graph index + append log
```

## Module responsibilities (Phase 1)

| Module | Responsibility | Depends on |
|--------|----------------|------------|
| `hashing.py` | `Hash` type (34-byte multihash); BLAKE3 hashing; hex↔bytes | — |
| `serialization.py` | canonical CBOR encode/decode (deterministic bytes) | — |
| `keys.py` | Ed25519 keypair generation, sign, verify | — |
| `object_store.py` | content-addressed put/get/has (+ batch), sharded fs, atomic write | hashing, serialization |
| `graph_index.py` | node/edge registration, structural adjacency (SQLite) | — |
| `merkle.py` | Merkle tree, root hash, inclusion proofs (RFC 6962 domain separation) | hashing |
| `append_log.py` | signed append, seq lookup, root, inclusion proofs (SQLite) | merkle, keys |
| `storage.py` | unified `Storage`; atomic `commit_edge_tx` (shared SQLite tx) | all above |

## Dependency graph (Phase 1)

```
storage.py ──► object_store.py ──► hashing.py, serialization.py
    │
    ├─────────► graph_index.py ──► (SQLite: index.db)
    │
    └─────────► append_log.py ──► merkle.py ──► hashing.py
                        │            └──► keys.py
                        └──► (SQLite: index.db, shared with graph_index)
```

No module imports `storage.py` except the verification layer (Phase 2). The
sub-interfaces are independently testable and independently swappable.

## What is deliberately NOT in Phase 1

- **No edge schema** (Phase 2) — storage treats edges as opaque bytes.
- **No κ computation** (Phase 2) — storage never labels strength.
- **No ELENCHUS** (Phase 2) — storage never vetoes.
- **No AND-OR traversal** (Phase 3) — storage only indexes connectivity.
- **No refutation resolution** (Phase 3) — that's query-layer semantics.

Phase 1 is *only* the dumb-and-fast substrate. Getting that boundary clean is
the entire point of the phase.
