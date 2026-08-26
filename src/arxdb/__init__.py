"""ArxDB — a content-addressed, signed, append-only reasoning-graph substrate.

Three layers, dependencies pointing upward only:

    Query        (Phase 3) — AND-OR hyperpath traversal, proof-tree assembly
    Verification (Phase 2) — edge schema, ELENCHUS veto, κ labels
    Storage      (Phase 1) — ObjectStore, GraphIndex, AppendLog, Merkle

Phase 1 implements only the storage layer. See PROJECT_STRUCTURE.md.
"""

__version__ = "0.1.0"
