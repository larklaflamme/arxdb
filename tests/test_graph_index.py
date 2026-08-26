"""Tests for graph_index.py — structural adjacency."""

from __future__ import annotations

from arxdb.storage.graph_index import GraphIndex
from arxdb.storage.hashing import hash_bytes


def _h(x: bytes) -> bytes:
    return hash_bytes(x)


def test_register_and_connectivity(tmp_root):
    g = GraphIndex(tmp_root / "index.db")
    a, b, c = _h(b"a"), _h(b"b"), _h(b"c")
    e = _h(b"edge")
    g.register_node(a)
    g.register_node(b)
    g.register_node(c)
    g.register_edge(e, [a, b], c)
    premises, conclusion = g.get_connectivity(e)
    assert premises == [a, b]
    assert conclusion == c


def test_incoming_outgoing(tmp_root):
    g = GraphIndex(tmp_root / "index.db")
    a, b, c = _h(b"a"), _h(b"b"), _h(b"c")
    e = _h(b"edge")
    g.register_node(a)
    g.register_node(b)
    g.register_node(c)
    g.register_edge(e, [a, b], c)
    assert e in g.incoming_edges(c)
    assert e in g.outgoing_edges(a)
    assert e in g.outgoing_edges(b)


def test_premise_order_preserved(tmp_root):
    """Premise order must be preserved (non-commutative inference rules)."""
    g = GraphIndex(tmp_root / "index.db")
    a, b, c = _h(b"a"), _h(b"b"), _h(b"c")
    e = _h(b"edge")
    g.register_node(a)
    g.register_node(b)
    g.register_node(c)
    g.register_edge(e, [a, b], c)
    premises, _ = g.get_connectivity(e)
    assert premises == [a, b]  # not [b, a]


def test_unregistered_node_empty(tmp_root):
    g = GraphIndex(tmp_root / "index.db")
    assert g.incoming_edges(_h(b"ghost")) == []
    assert g.outgoing_edges(_h(b"ghost")) == []
