"""Storage — the unified facade and the atomic `commit_edge_tx`.

`Storage` composes ObjectStore, GraphIndex, and AppendLog behind one interface.
The single most important method is `commit_edge_tx`, which commits a reasoning
edge *atomically* across all three sub-interfaces.

Atomicity is real (not rollback-on-exception) because GraphIndex and AppendLog
share one SQLite database: the graph mutation and the log append happen inside
a single `BEGIN IMMEDIATE … COMMIT`. The ObjectStore write is idempotent, so an
orphaned blob is harmless rather than corruption.

Public API (Phase 1):
    Storage(root: Path, priv_key: bytes, pub_key: bytes)
        commit_edge_tx(premises, conclusion, edge_data, proof) -> (edge_hash, LogEntry)
"""

from __future__ import annotations

from pathlib import Path

from .append_log import AppendLog, LogEntry
from .graph_index import GraphIndex
from .hashing import Hash
from .object_store import ObjectStore


class Storage:
    """Unified storage facade: ObjectStore + GraphIndex + AppendLog."""

    def __init__(self, root: Path, priv_key: bytes, pub_key: bytes) -> None:
        self.root = Path(root)
        self.objects = ObjectStore(self.root / "objects")
        self.graph = GraphIndex(self.root / "index.db")
        self.log = AppendLog(self.root / "index.db", priv_key, pub_key)

    def commit_edge_tx(
        self,
        premises: list[Hash],
        conclusion: Hash,
        edge_data: bytes,
        proof: bytes | None = None,
    ) -> tuple[Hash, LogEntry]:
        """Atomically commit a reasoning edge across all three sub-interfaces."""
        raise NotImplementedError
