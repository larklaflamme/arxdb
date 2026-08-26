"""Tests for commit.py — the verify-then-commit facade."""

from __future__ import annotations

from arxdb.storage.hashing import hash_bytes
from arxdb.storage.storage import Storage
from arxdb.verification.commit import verify_and_commit
from arxdb.verification.schema import EdgeType, Kappa, Node, Verdict


def _node(claim: str, domain: str = "math") -> Node:
    return Node(claim=claim, domain=domain)


def _storage(tmp_root, keypair) -> Storage:
    priv, pub = keypair
    return Storage(tmp_root, priv, pub)


# --- store on pass ---

def test_valid_deduction_committed(tmp_root, keypair):
    s = _storage(tmp_root, keypair)
    _, pub = keypair
    r = verify_and_commit(
        s, pub,
        [_node("x > 0")], _node("x + 1 > 0"),
        "modus ponens", EdgeType.DEDUCTION,
    )
    assert not r.rejected
    assert r.edge is not None
    assert r.edge_hash is not None
    assert r.log_entry is not None
    # Verdict + κ embedded in the stored edge record.
    assert r.edge.verdict == Verdict.PASS
    assert r.edge.kappa == Kappa.K3
    assert r.verification.kappa == Kappa.K3


# --- reject on veto ---

def test_invalid_deduction_rejected(tmp_root, keypair):
    s = _storage(tmp_root, keypair)
    _, pub = keypair
    r = verify_and_commit(
        s, pub,
        [_node("x > 0")], _node("x > 5"),
        "modus ponens", EdgeType.DEDUCTION,
    )
    assert r.rejected
    assert r.edge is None
    assert r.edge_hash is None
    assert r.log_entry is None
    assert r.verification.verdict == Verdict.HARD_VETO


# --- node payload persistence (closes the Phase 1 gap) ---

def test_node_payloads_persisted(tmp_root, keypair):
    s = _storage(tmp_root, keypair)
    _, pub = keypair
    premise = _node("x > 0")
    conclusion = _node("x + 1 > 0")
    r = verify_and_commit(
        s, pub, [premise], conclusion, "modus ponens", EdgeType.DEDUCTION
    )
    assert not r.rejected
    # Anyone holding a node_hash can retrieve the claim text.
    assert s.objects.get(premise.node_id()) == premise.node_bytes()
    assert s.objects.get(conclusion.node_id()) == conclusion.node_bytes()


# --- proof binding ---

def test_proof_hash_embedded_and_binding(tmp_root, keypair):
    s = _storage(tmp_root, keypair)
    _, pub = keypair
    proof = b"theorem t : 1 + 1 = 2 := by rfl\n"
    r = verify_and_commit(
        s, pub, [], _node("1 + 1 = 2"), "rfl", EdgeType.DEDUCTION,
        proof_bytes=proof,
    )
    assert not r.rejected
    assert r.edge.proof_hash == hash_bytes(proof)
    # The proof blob is content-addressed and retrievable.
    assert s.objects.get(hash_bytes(proof)) == proof


def test_swapping_proof_changes_edge_hash(tmp_root, keypair):
    s = _storage(tmp_root, keypair)
    _, pub = keypair
    r1 = verify_and_commit(
        s, pub, [], _node("1 + 1 = 2"), "rfl", EdgeType.DEDUCTION,
        proof_bytes=b"theorem t : 1 + 1 = 2 := by rfl\n",
    )
    r2 = verify_and_commit(
        s, pub, [], _node("1 + 1 = 2"), "rfl", EdgeType.DEDUCTION,
        proof_bytes=b"theorem t : 1 + 1 = 2 := by norm_num\n",
    )
    assert r1.edge_hash != r2.edge_hash


# --- edge retrievable (end-to-end: propose → verify → commit → retrieve) ---

def test_edge_retrievable_from_object_store(tmp_root, keypair):
    s = _storage(tmp_root, keypair)
    _, pub = keypair
    r = verify_and_commit(
        s, pub, [_node("x > 0")], _node("x + 1 > 0"),
        "modus ponens", EdgeType.DEDUCTION,
    )
    assert not r.rejected
    assert s.objects.get(r.edge_hash) == r.edge.edge_bytes()


# --- soft-flag is stored (not rejected) ---

def test_soft_flag_stored(tmp_root, keypair):
    s = _storage(tmp_root, keypair)
    _, pub = keypair
    r = verify_and_commit(
        s, pub, [_node("x > 0")], _node("x + 1 > 0"),
        "", EdgeType.DEDUCTION,  # empty rule → SOFT_FLAG
    )
    assert not r.rejected
    assert r.edge is not None
    assert r.edge.verdict == Verdict.SOFT_FLAG
    assert r.edge.kappa == Kappa.K3


# --- rejected edge leaves no trace in the graph ---

def test_rejected_edge_not_in_graph(tmp_root, keypair):
    s = _storage(tmp_root, keypair)
    _, pub = keypair
    conclusion = _node("x > 5")
    r = verify_and_commit(
        s, pub, [_node("x > 0")], conclusion,
        "modus ponens", EdgeType.DEDUCTION,
    )
    assert r.rejected
    # The conclusion node was never registered in the graph index.
    assert s.graph.incoming_edges(conclusion.node_id()) == []
    assert s.graph.outgoing_edges(conclusion.node_id()) == []
