"""Verification layer (Phase 2) — the moat.

Edge schema, ELENCHUS hard-veto predicates, formal checkers, κ labels.

Modules (built incrementally):
    schema    — Node/Edge dataclasses, EdgeType/Kappa/Verdict enums, canonical
                CBOR serialization (IMPLEMENTED)
    kappa     — the κ scale + propagation algebra (series/parallel/corroboration) (IMPLEMENTED)
    elenchus  — ELENCHUS adapter: hard-veto / soft-flag / pass (IMPLEMENTED)
    checkers  — pluggable formal checkers behind a bounded protocol (IMPLEMENTED)
    verifier  — the κ-tiering pipeline: dispatch by type → run check → verdict (IMPLEMENTED)
    commit    — verify-then-commit facade (IMPLEMENTED)

Boundary discipline: this package imports only the public storage primitives
(`hashing`, `serialization`) and the public `Storage` API — never `sqlite3`,
`pathlib`, or private `Storage` attributes.
"""
