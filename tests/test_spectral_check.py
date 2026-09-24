"""Tests for the spectral checker (numpy/mpmath)."""

from __future__ import annotations

from arxdb.verification.checkers import SpectralChecker
from arxdb.verification.schema import EdgeType, Kappa, Node, Verdict
from arxdb.verification.verifier import verify


def _node(claim: str, domain: str = "math") -> Node:
    return Node(claim=claim, domain=domain)


# --- self-adjointness (the RH finding: L_{1/4} is self-adjoint) ---

def test_self_adjoint_bessel_kernel_passes_kappa2():
    r = verify([], _node("self_adjoint bessel_kernel(-0.5, 60)"), "spectral", EdgeType.SPECTRAL)
    assert r.verdict == Verdict.PASS
    assert r.kappa == Kappa.K2
    assert not r.rejected
    assert r.checker is not None
    assert r.checker.details["hermitian_err"] < 1e-10


def test_self_adjoint_complex_nu_rejects():
    # Complex order breaks self-adjointness (broken PT-symmetry).
    r = verify([], _node("self_adjoint bessel_kernel(-0.5+2j, 40)"), "spectral", EdgeType.SPECTRAL)
    assert r.verdict == Verdict.HARD_VETO
    assert r.kappa == Kappa.K0
    assert r.rejected


# --- real spectrum ---

def test_real_spectrum_symmetric_passes():
    r = verify([], _node("real_spectrum array([[2,1],[1,2]])"), "spectral", EdgeType.SPECTRAL)
    assert r.verdict == Verdict.PASS
    assert r.kappa == Kappa.K2


# --- rank ---

def test_rank_leq_1_rank_one_matrix_passes():
    r = verify([], _node("rank_leq:1 array([[1,2],[2,4]])"), "spectral", EdgeType.SPECTRAL)
    assert r.verdict == Verdict.PASS
    assert r.kappa == Kappa.K2
    assert r.checker.details["n_above_tol"] == 1


def test_rank_leq_1_full_rank_rejects():
    r = verify([], _node("rank_leq:1 array([[1,0],[0,1]])"), "spectral", EdgeType.SPECTRAL)
    assert r.verdict == Verdict.HARD_VETO
    assert r.rejected


# --- malformed / unknown ---

def test_malformed_claim_clean_failure():
    r = verify([], _node("self_adjoint"), "spectral", EdgeType.SPECTRAL)
    assert r.verdict == Verdict.HARD_VETO
    assert r.kappa == Kappa.K0
    assert r.checker is not None
    assert r.checker.error_msg


def test_unknown_property_clean_failure():
    r = verify([], _node("frobnicate array([[1,0],[0,1]])"), "spectral", EdgeType.SPECTRAL)
    assert r.verdict == Verdict.HARD_VETO
    assert r.kappa == Kappa.K0


def test_non_matrix_clean_failure():
    r = verify([], _node("self_adjoint array([1,2,3])"), "spectral", EdgeType.SPECTRAL)
    assert r.verdict == Verdict.HARD_VETO
    assert r.kappa == Kappa.K0
