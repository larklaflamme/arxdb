"""Tests for schema.py — Node/Edge dataclasses, enums, canonical serialization."""

from __future__ import annotations

from arxdb.storage.hashing import hash_bytes
from arxdb.verification.schema import Edge, EdgeType, Kappa, Node, Verdict


def _node(claim="RH ⟺ Λ ≤ 0", domain="math", polarity=True) -> Node:
    return Node(claim=claim, domain=domain, polarity=polarity)


def _edge(**overrides) -> Edge:
    a = _node("A").node_id()
    b = _node("B").node_id()
    c = _node("C").node_id()
    defaults = dict(
        type=EdgeType.DEDUCTION,
        premises=(a, b),
        conclusion=c,
        rule="modus ponens",
        proof_hash=hash_bytes(b"proof-bytes"),
        verdict=Verdict.PASS,
        kappa=Kappa.K3,
        signer_pubkey=b"\x01" * 32,
    )
    defaults.update(overrides)
    return Edge(**defaults)


# --- Node: content-addressing ---

def test_node_id_stable():
    assert _node().node_id() == _node().node_id()


def test_node_id_distinguishes_claim():
    assert _node("A").node_id() != _node("B").node_id()


def test_node_id_distinguishes_domain():
    assert _node(domain="math").node_id() != _node(domain="physics").node_id()


def test_node_id_distinguishes_polarity():
    assert _node(polarity=True).node_id() != _node(polarity=False).node_id()


def test_node_roundtrip():
    n = _node()
    assert Node.from_bytes(n.node_bytes()) == n


def test_node_canonical_stability_field_order():
    """Constructing with kwargs in a different order must not change the id."""
    a = Node(claim="X", domain="math", polarity=True)
    b = Node(polarity=True, domain="math", claim="X")
    assert a.node_id() == b.node_id()


# --- Edge: content-addressing + proof binding ---

def test_edge_hash_stable():
    assert _edge().edge_hash() == _edge().edge_hash()


def test_edge_roundtrip():
    e = _edge()
    assert Edge.from_bytes(e.edge_bytes()) == e


def test_proof_hash_binding():
    """Swapping the proof changes proof_hash, which changes edge_hash."""
    e1 = _edge(proof_hash=hash_bytes(b"proof one"))
    e2 = _edge(proof_hash=hash_bytes(b"proof two"))
    assert e1.proof_hash != e2.proof_hash
    assert e1.edge_hash() != e2.edge_hash()


def test_edge_hash_distinguishes_verdict():
    assert _edge(verdict=Verdict.PASS).edge_hash() != _edge(
        verdict=Verdict.HARD_VETO
    ).edge_hash()


def test_edge_hash_distinguishes_kappa():
    assert _edge(kappa=Kappa.K3).edge_hash() != _edge(kappa=Kappa.K1).edge_hash()


def test_edge_hash_distinguishes_rule():
    assert _edge(rule="modus ponens").edge_hash() != _edge(
        rule="modus tollens"
    ).edge_hash()


def test_edge_hash_distinguishes_premises():
    a = _node("A").node_id()
    b = _node("B").node_id()
    c = _node("C").node_id()
    d = _node("D").node_id()
    e1 = _edge(premises=(a, b), conclusion=c)
    e2 = _edge(premises=(a, d), conclusion=c)
    assert e1.edge_hash() != e2.edge_hash()


def test_node_vs_edge_no_collision():
    """A node and an edge must never share a content address."""
    n = _node()
    e = _edge()
    assert n.node_id() != e.edge_hash()


def test_proof_hash_none_roundtrip():
    """An edge with no proof must round-trip with proof_hash=None."""
    e = _edge(proof_hash=None)
    assert Edge.from_bytes(e.edge_bytes()) == e
    assert e.proof_hash is None
