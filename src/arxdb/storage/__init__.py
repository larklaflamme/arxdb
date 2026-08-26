"""Storage layer (Phase 1) — the dumb-and-fast substrate.

Modules:
    hashing        — BLAKE3 multihash + Hash type
    serialization  — canonical CBOR encode/decode
    keys           — Ed25519 keypair, sign, verify
    object_store   — content-addressed put/get (sharded filesystem)
    graph_index    — structural adjacency (SQLite)
    merkle         — Merkle tree + inclusion proofs (RFC 6962)
    append_log     — signed append-only log (SQLite)
    storage        — unified Storage + atomic commit_edge_tx

Storage knows nothing about verification or query semantics.
"""
