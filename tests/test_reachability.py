"""Tests for reachability.py — AND-OR reachability with κ-propagation."""

from __future__ import annotations

from arxdb.storage.storage import Storage
from arxdb.verification.schema import EdgeType, Kappa

from arxdb.query import reachable

from query_helpers import commit_edge, node


def _storage(tmp_root, keypair) -> Storage:
    priv, pub = keypair
    return Storage(tmp_root, priv, pub)


def test_single_axiom_reachable(tmp_root, keypair):
    s = _storage(tmp_root, keypair)
    a = node("A")
    commit_edge(s, EdgeType.DEFINITION, [], a, Kappa.K_INF)
    r = reachable(a.node_id(), s)
    assert r.established is True
    assert r.kappa == Kappa.K_INF
    assert r.depth == 0


def test_and_conjunction_soundness(tmp_root, keypair):
    """C is reachable only when *both* A and B are established."""
    s = _storage(tmp_root, keypair)
    a = node("A")
    b = node("B")
    c = node("C")
    commit_edge(s, EdgeType.DEFINITION, [], a, Kappa.K_INF)
    commit_edge(s, EdgeType.DEFINITION, [], b, Kappa.K_INF)
    commit_edge(s, EdgeType.DEDUCTION, [a, b], c, Kappa.K3)

    r = reachable(c.node_id(), s)
    assert r.established is True
    assert r.kappa == Kappa.K3
    assert r.depth == 1  # one parallel step, not two


def test_unreachable_when_premise_missing(tmp_root, keypair):
    """C is unreachable when one premise (B) is not established."""
    s = _storage(tmp_root, keypair)
    a = node("A")
    b = node("B")
    c = node("C")
    commit_edge(s, EdgeType.DEFINITION, [], a, Kappa.K_INF)
    # B is NOT established; A ∧ B → C cannot fire.
    commit_edge(s, EdgeType.DEDUCTION, [a, b], c, Kappa.K3)

    r = reachable(c.node_id(), s)
    assert r.established is False
    assert r.kappa is None
    assert r.depth is None


def test_series_min_propagation(tmp_root, keypair):
    """A --κ3--> B --κ1--> C ⟹ κ(C) = κ1 (weakest link)."""
    s = _storage(tmp_root, keypair)
    a = node("A")
    b = node("B")
    c = node("C")
    commit_edge(s, EdgeType.DEFINITION, [], a, Kappa.K_INF)
    commit_edge(s, EdgeType.DEDUCTION, [a], b, Kappa.K3)
    commit_edge(s, EdgeType.REDUCTION, [b], c, Kappa.K1)

    r = reachable(c.node_id(), s)
    assert r.established is True
    assert r.kappa == Kappa.K1


def test_corroboration_max_propagation(tmp_root, keypair):
    """Two independent paths (κ1 and κ3) ⟹ κ(C) = κ3 (strongest wins)."""
    s = _storage(tmp_root, keypair)
    a = node("A")
    c = node("C")
    commit_edge(s, EdgeType.DEFINITION, [], a, Kappa.K_INF)
    commit_edge(s, EdgeType.REDUCTION, [a], c, Kappa.K1)   # path 1
    commit_edge(s, EdgeType.DEDUCTION, [a], c, Kappa.K3)   # path 2

    r = reachable(c.node_id(), s)
    assert r.established is True
    assert r.kappa == Kappa.K3


def test_kappa_threshold_filter(tmp_root, keypair):
    """A κ2 derivation is reachable at min_kappa=K2 but not at K3."""
    s = _storage(tmp_root, keypair)
    a = node("A")
    c = node("C")
    commit_edge(s, EdgeType.DEFINITION, [], a, Kappa.K_INF)
    commit_edge(s, EdgeType.NUMERICAL, [a], c, Kappa.K2)

    assert reachable(c.node_id(), s, min_kappa=Kappa.K2).established is True
    assert reachable(c.node_id(), s, min_kappa=Kappa.K3).established is False


def test_cyclic_graph_terminates(tmp_root, keypair):
    """A cycle with no axiom grounding establishes nothing, and terminates."""
    s = _storage(tmp_root, keypair)
    a = node("A")
    b = node("B")
    commit_edge(s, EdgeType.DEDUCTION, [a], b, Kappa.K3)
    commit_edge(s, EdgeType.DEDUCTION, [b], a, Kappa.K3)

    r = reachable(a.node_id(), s)
    assert r.established is False
    assert r.kappa is None


def test_hypothetical_seed_reachability(tmp_root, keypair):
    """extra_seeds=[H] establishes conditional derivations without mutating."""
    s = _storage(tmp_root, keypair)
    h = node("H")
    c = node("C")
    commit_edge(s, EdgeType.DEDUCTION, [h], c, Kappa.K3)

    # Without the seed, C is unreachable.
    assert reachable(c.node_id(), s).established is False
    # With H assumed, C follows.
    r = reachable(c.node_id(), s, extra_seeds=[h.node_id()])
    assert r.established is True
    assert r.kappa == Kappa.K3
