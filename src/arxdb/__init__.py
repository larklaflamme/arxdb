"""ArxDB — a content-addressed, signed, append-only reasoning-graph substrate.

Three layers, dependencies pointing upward only:

    Query        — AND-OR hyperpath traversal, proof-tree assembly
    Verification — edge schema, ELENCHUS veto, κ labels, formal checkers
    Storage      — ObjectStore, GraphIndex, AppendLog, Merkle (SQLite or Go/Pebble)

All seven roadmap phases are complete. See README.md for the pitch,
DESIGN.md for the architecture, and DEV_GUIDE.md for integration.
"""

__version__ = "0.1.0"
