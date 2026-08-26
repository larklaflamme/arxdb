"""Tests for path.py — proof-tree depth and the goal-specific missing frontier."""

from __future__ import annotations

from arxdb.storage.storage import Storage
from arxdb.verification.schema import EdgeType, Kappa

from arxdb.query import path_discovery

from query_helpers import commit_edge, node


def _storage(tmp_root, keypair) -> Storage:
    priv, pub = keypair
    return Storage(tmp_root, priv, pub)


def test_proof_tree_depth_parallel(tmp_root, keypair):
    """Parallel premises count once: A∧B→C is depth 1, not 2."""
    s = _storage(tmp_root, keypair)
    a = node("A")
    b = node("B")
    c = node("C")
    d = node("D")
    commit_edge(s, EdgeType.DEFINITION, [], a, Kappa.K_INF)
    commit_edge(s, EdgeType.DEFINITION, [], b, Kappa.K_INF)
    commit_edge(s, EdgeType.DEDUCTION, [a, b], c, Kappa.K3)  # depth 1
    commit_edge(s, EdgeType.DEDUCTION, [c], d, Kappa.K3)     # depth 2

    r = path_discovery(d.node_id(), s)
    assert r.reachable is True
    assert r.depth == 2
    assert r.kappa == Kappa.K3
    assert r.missing_edges == ()


def test_missing_edge_frontier_goal_specific(tmp_root, keypair):
    """The frontier names only blocking premises in C's cone, not the global one."""
    s = _storage(tmp_root, keypair)
    a = node("A")
    b = node("B")
    c = node("C")
    d = node("D")  # an unrelated missing node, outside C's cone
    commit_edge(s, EdgeType.DEFINITION, [], a, Kappa.K_INF)
    # A ∧ B → C, but B is never established.
    commit_edge(s, EdgeType.DEDUCTION, [a, b], c, Kappa.K3)
    # D is referenced by nothing; it is a global missing node, not in C's cone.

    r = path_discovery(c.node_id(), s)
    assert r.reachable is False
    assert r.depth is None
    assert r.kappa is None

    # Collect every hash mentioned anywhere in the frontier.
    mentioned: set = set()
    for me in r.missing_edges:
        mentioned.add(me.conclusion)
        mentioned.update(me.premises)
        mentioned.update(me.blocking_nodes)

    assert b.node_id() in mentioned      # B blocks C
    assert d.node_id() not in mentioned  # D is outside the goal cone


def test_path_discovery_reachable_returns_no_missing(tmp_root, keypair):
    """A reachable target reports no missing edges."""
    s = _storage(tmp_root, keypair)
    a = node("A")
    b = node("B")
    commit_edge(s, EdgeType.DEFINITION, [], a, Kappa.K_INF)
    commit_edge(s, EdgeType.DEDUCTION, [a], b, Kappa.K3)

    r = path_discovery(b.node_id(), s)
    assert r.reachable is True
    assert r.depth == 1
    assert r.missing_edges == ()
