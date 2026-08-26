"""Tests for resolve.py — hash → Node/Edge record resolution."""

from __future__ import annotations

from arxdb.storage.hashing import hash_bytes
from arxdb.storage.storage import Storage
from arxdb.verification.schema import EdgeType, Kappa

from arxdb.query import resolve_edge, resolve_node

from query_helpers import commit_edge, node


def _storage(tmp_root, keypair) -> Storage:
    priv, pub = keypair
    return Storage(tmp_root, priv, pub)


def test_resolve_node_round_trip(tmp_root, keypair):
    s = _storage(tmp_root, keypair)
    n = node("x > 0")
    commit_edge(s, EdgeType.DEFINITION, [], n, Kappa.K1)
    resolved = resolve_node(n.node_id(), s)
    assert resolved is not None
    assert resolved.claim == "x > 0"
    assert resolved.domain == "math"
    assert resolved.polarity is True


def test_resolve_edge_round_trip(tmp_root, keypair):
    s = _storage(tmp_root, keypair)
    a = node("x > 0")
    b = node("x + 1 > 0")
    h, edge = commit_edge(s, EdgeType.DEDUCTION, [a], b, Kappa.K3)
    resolved = resolve_edge(h, s)
    assert resolved is not None
    assert resolved.type == EdgeType.DEDUCTION
    assert resolved.kappa == Kappa.K3
    assert resolved.conclusion == b.node_id()
    assert resolved.premises == (a.node_id(),)


def test_resolve_missing_returns_none(tmp_root, keypair):
    s = _storage(tmp_root, keypair)
    absent = hash_bytes(b"not in the store")
    assert resolve_node(absent, s) is None
    assert resolve_edge(absent, s) is None


def test_resolve_wrong_kind_returns_none(tmp_root, keypair):
    """A node hash resolved as an edge (and vice versa) is None, not an error."""
    s = _storage(tmp_root, keypair)
    n = node("x > 0")
    commit_edge(s, EdgeType.DEFINITION, [], n, Kappa.K1)
    # The node hash is not an edge.
    assert resolve_edge(n.node_id(), s) is None
