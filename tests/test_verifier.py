"""Tests for verifier.py — the κ-tiering pipeline."""

from __future__ import annotations

from arxdb.verification.schema import EdgeType, Kappa, Node, Verdict
from arxdb.verification.verifier import VerificationResult, verify


def _node(claim: str, domain: str = "math") -> Node:
    return Node(claim=claim, domain=domain)


# --- definition (roster) ---

def test_definition_roster_match_kappa_inf():
    r = verify([], _node("0 is a natural number"), "definition", EdgeType.DEFINITION)
    assert r.verdict == Verdict.PASS
    assert r.kappa == Kappa.K_INF
    assert not r.rejected


def test_definition_unlisted_kappa1():
    r = verify([], _node("a widget is a thing"), "definition", EdgeType.DEFINITION)
    assert r.verdict == Verdict.PASS
    assert r.kappa == Kappa.K1
    assert not r.rejected


# --- deduction (z3) ---

def test_deduction_valid_z3_kappa3():
    r = verify(
        [_node("x > 0")],
        _node("x + 1 > 0"),
        "modus ponens",
        EdgeType.DEDUCTION,
    )
    assert r.verdict == Verdict.PASS
    assert r.kappa == Kappa.K3
    assert not r.rejected
    assert r.checker is not None


def test_deduction_invalid_z3_rejects():
    r = verify(
        [_node("x > 0")],
        _node("x > 5"),
        "modus ponens",
        EdgeType.DEDUCTION,
    )
    assert r.verdict == Verdict.HARD_VETO
    assert r.kappa == Kappa.K0
    assert r.rejected
    assert r.checker is not None
    assert "counter" in r.checker.error_msg


# --- numerical (cas) ---

def test_numerical_valid_cas_kappa2():
    r = verify(
        [],
        _node("x**2 - 1 = (x - 1)*(x + 1)"),
        "algebra",
        EdgeType.NUMERICAL,
    )
    assert r.verdict == Verdict.PASS
    assert r.kappa == Kappa.K2
    assert not r.rejected


def test_numerical_invalid_cas_rejects():
    r = verify(
        [],
        _node("x**2 - 1 = x**2 + 1"),
        "algebra",
        EdgeType.NUMERICAL,
    )
    assert r.verdict == Verdict.HARD_VETO
    assert r.kappa == Kappa.K0
    assert r.rejected


# --- ELENCHUS hard-veto (runs before any checker) ---

def test_elenchus_hard_veto_rejects_before_checker():
    # Category error: conclusion domain absent from premises on a deduction.
    r = verify(
        [_node("A implies B", "math")],
        _node("C implies D", "physics"),
        "modus ponens",
        EdgeType.DEDUCTION,
    )
    assert r.verdict == Verdict.HARD_VETO
    assert r.kappa == Kappa.K0
    assert r.rejected
    assert r.checker is None  # no formal checker ever ran


def test_self_model_leak_rejects():
    r = verify(
        [_node("x > 0")],
        _node("x is conscious", "math"),
        "modus ponens",
        EdgeType.DEDUCTION,
    )
    assert r.verdict == Verdict.HARD_VETO
    assert r.rejected


# --- edge types with no dedicated checker ---

def test_analogy_no_checker_kappa0():
    r = verify(
        [_node("A implies B", "math")],
        _node("C implies D", "physics"),
        "structural analogy",
        EdgeType.ANALOGY,
    )
    assert r.verdict == Verdict.PASS
    assert r.kappa == Kappa.K0
    assert r.checker is None
    assert not r.rejected


def test_citation_no_checker_kappa1():
    r = verify([], _node("some cited claim"), "citation", EdgeType.CITATION)
    assert r.verdict == Verdict.PASS
    assert r.kappa == Kappa.K1
    assert r.checker is None


def test_reduction_no_checker_kappa1():
    r = verify(
        [_node("A implies B", "math")],
        _node("C implies D", "physics"),
        "isomorphism",
        EdgeType.REDUCTION,
    )
    assert r.verdict == Verdict.PASS
    assert r.kappa == Kappa.K1
    assert r.checker is None


def test_refutation_no_checker_kappa1():
    r = verify(
        [_node("x > 0")],
        _node("x < 0"),
        "counterexample",
        EdgeType.REFUTATION,
    )
    assert r.verdict == Verdict.PASS
    assert r.kappa == Kappa.K1
    assert r.checker is None


# --- soft-flag survives (stored, but flagged) ---

def test_soft_flag_survives_with_kappa():
    # A deduction with no named rule soft-flags (empty_rule) but still passes
    # the formal check, so it is stored with the checker's κ and a SOFT_FLAG.
    r = verify(
        [_node("x > 0")],
        _node("x + 1 > 0"),
        "",
        EdgeType.DEDUCTION,
    )
    assert r.verdict == Verdict.SOFT_FLAG
    assert r.kappa == Kappa.K3
    assert not r.rejected


# --- deduction with a Lean proof (dispatch to Lean) ---

def test_deduction_lean_proof_dispatch():
    r = verify(
        [],
        _node("1 + 1 = 2"),
        "rfl",
        EdgeType.DEDUCTION,
        proof_bytes=b"theorem t : 1 + 1 = 2 := by rfl\n",
    )
    assert r.verdict == Verdict.PASS
    assert r.kappa == Kappa.K3
    assert not r.rejected


def test_deduction_lean_invalid_proof_rejects():
    r = verify(
        [],
        _node("1 + 1 = 3"),
        "rfl",
        EdgeType.DEDUCTION,
        proof_bytes=b"theorem t : 1 + 1 = 3 := by rfl\n",
    )
    assert r.verdict == Verdict.HARD_VETO
    assert r.kappa == Kappa.K0
    assert r.rejected


# --- VerificationResult.rejected property ---

def test_rejected_property_matches_verdict():
    assert VerificationResult(
        verdict=Verdict.HARD_VETO, kappa=Kappa.K0,
        elenchus=None, checker=None, edge_type=EdgeType.ANALOGY, rule="",
    ).rejected is True
    assert VerificationResult(
        verdict=Verdict.PASS, kappa=Kappa.K1,
        elenchus=None, checker=None, edge_type=EdgeType.ANALOGY, rule="",
    ).rejected is False
