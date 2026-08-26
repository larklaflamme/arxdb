"""Tests for refutation.py — grounded active-subgraph resolution."""

from __future__ import annotations

from arxdb.storage.storage import Storage
from arxdb.verification.schema import EdgeType, Kappa

from arxdb.query import compute_active_subgraph, reachable

from query_helpers import commit_edge, commit_refutation, node


def _storage(tmp_root, keypair) -> Storage:
    priv, pub = keypair
    return Storage(tmp_root, priv, pub)


def test_refuted_edge_excluded_and_downstream_loses_status(tmp_root, keypair):
    s = _storage(tmp_root, keypair)
    a = node("A")
    b = node("B")
    c = node("C")
    e0, _ = commit_edge(s, EdgeType.DEFINITION, [], a, Kappa.K_INF)
    e1, _ = commit_edge(s, EdgeType.DEDUCTION, [a], b, Kappa.K3)
    e2, _ = commit_edge(s, EdgeType.DEDUCTION, [b], c, Kappa.K3)
    commit_refutation(s, e1)  # attacks E1

    active = compute_active_subgraph(s)
    assert e1 not in active.in_edges
    assert e1 in active.out_edges
    assert e0 in active.in_edges
    assert e2 in active.in_edges

    # With E1 defeated, B is no longer established, so C loses derived status.
    r = reachable(c.node_id(), s, active_edges=active.in_edges)
    assert r.established is False


def test_refutation_of_refutation_reinstates(tmp_root, keypair):
    s = _storage(tmp_root, keypair)
    a = node("A")
    b = node("B")
    e0, _ = commit_edge(s, EdgeType.DEFINITION, [], a, Kappa.K_INF)
    e1, _ = commit_edge(s, EdgeType.DEDUCTION, [a], b, Kappa.K3)
    e2, _ = commit_refutation(s, e1)  # attacks E1
    e3, _ = commit_refutation(s, e2)  # attacks E2 (the refutation)

    active = compute_active_subgraph(s)
    assert e1 in active.in_edges   # reinstated
    assert e2 in active.out_edges  # the refutation is defeated
    assert e3 in active.in_edges

    r = reachable(b.node_id(), s, active_edges=active.in_edges)
    assert r.established is True


def test_mutual_contention_undecided(tmp_root, keypair):
    """Two edges concluding the same proposition with opposite polarity are
    in contention (mutual attack) and skeptically excluded as UNDECIDED."""
    s = _storage(tmp_root, keypair)
    p_pos = node("P", polarity=True)
    p_neg = node("P", polarity=False)
    e1, _ = commit_edge(s, EdgeType.DEFINITION, [], p_pos, Kappa.K_INF)
    e2, _ = commit_edge(s, EdgeType.DEFINITION, [], p_neg, Kappa.K_INF)

    active = compute_active_subgraph(s)
    assert e1 in active.undecided_edges
    assert e2 in active.undecided_edges
    assert e1 not in active.in_edges
    assert e2 not in active.in_edges


def test_grounded_fixpoint_terminates_chain(tmp_root, keypair):
    """A longer refutation chain terminates with the correct grounded labeling."""
    s = _storage(tmp_root, keypair)
    a = node("A")
    b = node("B")
    e1, _ = commit_edge(s, EdgeType.DEDUCTION, [a], b, Kappa.K3)
    r1, _ = commit_refutation(s, e1)  # attacks E1
    r2, _ = commit_refutation(s, r1)  # attacks R1
    r3, _ = commit_refutation(s, r2)  # attacks R2

    active = compute_active_subgraph(s)
    # R3 unattacked → IN; R3 attacks R2 → OUT; R1 attacked only by R2 (OUT)
    # → IN; R1 attacks E1 → OUT.
    assert r3 in active.in_edges
    assert r2 in active.out_edges
    assert r1 in active.in_edges
    assert e1 in active.out_edges
    # Every edge is labeled (no edge left unaccounted).
    all_edges = {e1, r1, r2, r3}
    assert all_edges == set(active.in_edges) | set(active.out_edges) | set(active.undecided_edges)
