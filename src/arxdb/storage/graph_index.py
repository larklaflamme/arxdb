"""GraphIndex — structural node↔edge adjacency over SQLite.

Stores *structural* connectivity only: which nodes exist, which edges connect
which premises to which conclusion. No semantic traversal, no κ, no proof
correctness — that lives in the verification layer.

Backed by SQLite (WAL mode), sharing `index.db` with AppendLog so that
`commit_edge_tx` can wrap both in one transaction.

Public API (Phase 1):
    GraphIndex(db_path: Path)
        register_node(node_hash: Hash) -> None
        register_edge(edge_hash: Hash, premises: list[Hash], conclusion: Hash) -> None
        incoming_edges(node_hash: Hash) -> list[Hash]
        outgoing_edges(node_hash: Hash) -> list[Hash]
        get_connectivity(edge_hash: Hash) -> (premises, conclusion) | None
"""

from __future__ import annotations

from pathlib import Path

from .hashing import Hash


class GraphIndex:
    """Structural adjacency index over a shared SQLite database."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        raise NotImplementedError

    def register_node(self, node_hash: Hash) -> None:
        raise NotImplementedError

    def register_edge(
        self, edge_hash: Hash, premises: list[Hash], conclusion: Hash
    ) -> None:
        raise NotImplementedError

    def incoming_edges(self, node_hash: Hash) -> list[Hash]:
        raise NotImplementedError

    def outgoing_edges(self, node_hash: Hash) -> list[Hash]:
        raise NotImplementedError

    def get_connectivity(
        self, edge_hash: Hash
    ) -> tuple[list[Hash], Hash] | None:
        raise NotImplementedError
