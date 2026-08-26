"""GraphIndex — structural node↔edge adjacency over SQLite.

Stores *structural* connectivity only: which nodes exist, which edges connect
which premises to which conclusion. No semantic traversal, no κ, no proof
correctness — that lives in the verification layer.

Backed by SQLite (WAL mode), sharing `index.db` with AppendLog so that
`commit_edge_tx` can wrap both in one transaction.

Public API (Phase 1):
    GraphIndex(db_path: Path, conn: sqlite3.Connection | None = None)
        register_node(node_hash: Hash) -> None
        register_edge(edge_hash: Hash, premises: list[Hash], conclusion: Hash) -> None
        incoming_edges(node_hash: Hash) -> list[Hash]
        outgoing_edges(node_hash: Hash) -> list[Hash]
        get_connectivity(edge_hash: Hash) -> (premises, conclusion) | None

When `conn` is provided, the instance shares that connection and does NOT
commit (the owner controls the transaction). When `conn` is None, the instance
opens its own connection and commits after each write.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .hashing import Hash


class GraphIndex:
    """Structural adjacency index over a shared SQLite database."""

    def __init__(self, db_path: Path, conn: sqlite3.Connection | None = None) -> None:
        self.db_path = Path(db_path)
        self._owns_conn = conn is None
        if self._owns_conn:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        else:
            self._conn = conn
        self._init_schema()

    def _commit(self) -> None:
        """Commit only if this instance owns its connection."""
        if self._owns_conn:
            self._conn.commit()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                node_hash BLOB PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS edges (
                edge_hash BLOB PRIMARY KEY,
                conclusion BLOB NOT NULL
            );
            CREATE TABLE IF NOT EXISTS premises (
                edge_hash BLOB NOT NULL,
                premise_hash BLOB NOT NULL,
                position INTEGER NOT NULL,
                PRIMARY KEY (edge_hash, position)
            );
            CREATE INDEX IF NOT EXISTS idx_edges_conclusion
                ON edges(conclusion);
            CREATE INDEX IF NOT EXISTS idx_premises_premise
                ON premises(premise_hash);
            """
        )
        self._commit()

    def register_node(self, node_hash: Hash) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO nodes (node_hash) VALUES (?)", (node_hash,)
        )
        self._commit()

    def register_edge(
        self, edge_hash: Hash, premises: list[Hash], conclusion: Hash
    ) -> None:
        # Register the edge's endpoints so the graph stays self-consistent.
        self._conn.execute(
            "INSERT OR IGNORE INTO nodes (node_hash) VALUES (?)", (conclusion,)
        )
        for p in premises:
            self._conn.execute(
                "INSERT OR IGNORE INTO nodes (node_hash) VALUES (?)", (p,)
            )
        self._conn.execute(
            "INSERT OR IGNORE INTO edges (edge_hash, conclusion) VALUES (?, ?)",
            (edge_hash, conclusion),
        )
        for position, p in enumerate(premises):
            self._conn.execute(
                "INSERT OR IGNORE INTO premises "
                "(edge_hash, premise_hash, position) VALUES (?, ?, ?)",
                (edge_hash, p, position),
            )
        self._commit()

    def incoming_edges(self, node_hash: Hash) -> list[Hash]:
        rows = self._conn.execute(
            "SELECT edge_hash FROM edges WHERE conclusion = ? ORDER BY edge_hash",
            (node_hash,),
        ).fetchall()
        return [Hash(r[0]) for r in rows]

    def outgoing_edges(self, node_hash: Hash) -> list[Hash]:
        rows = self._conn.execute(
            "SELECT edge_hash FROM premises WHERE premise_hash = ? ORDER BY edge_hash",
            (node_hash,),
        ).fetchall()
        return [Hash(r[0]) for r in rows]

    def get_connectivity(
        self, edge_hash: Hash
    ) -> tuple[list[Hash], Hash] | None:
        row = self._conn.execute(
            "SELECT conclusion FROM edges WHERE edge_hash = ?", (edge_hash,)
        ).fetchone()
        if row is None:
            return None
        conclusion = Hash(row[0])
        prem_rows = self._conn.execute(
            "SELECT premise_hash FROM premises WHERE edge_hash = ? ORDER BY position",
            (edge_hash,),
        ).fetchall()
        premises = [Hash(r[0]) for r in prem_rows]
        return (premises, conclusion)
