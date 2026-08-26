"""Tests for checkers/ — the bounded formal checkers."""

from __future__ import annotations

import time

import pytest

from arxdb.verification.checkers import (
    CasChecker,
    CheckerTimeout,
    LeanChecker,
    RosterChecker,
    Z3Checker,
    check_roster,
    run_bounded,
)
from arxdb.verification.schema import Kappa, Node


def _node(claim: str, domain: str = "math") -> Node:
    return Node(claim=claim, domain=domain)


# --- roster (the κ∞ gate) ---

def test_roster_kappa_inf_for_known_axiom():
    assert check_roster(_node("0 is a natural number")) == Kappa.K_INF


def test_roster_kappa1_for_unlisted_definition():
    assert check_roster(_node("a widget is a thing that widgets")) == Kappa.K1


def test_roster_normalizes_whitespace():
    assert check_roster(_node("  0   is a   natural number  ")) == Kappa.K_INF


def test_roster_checker_always_passes():
    r = RosterChecker().check([], _node("0 is a natural number"), "definition", None)
    assert r.passed
    assert r.kappa == Kappa.K_INF


def test_roster_checker_unlisted_is_kappa1():
    r = RosterChecker().check([], _node("a widget is a thing"), "definition", None)
    assert r.passed
    assert r.kappa == Kappa.K1


# --- CAS (sympy) ---

def test_cas_verifies_true_identity():
    r = CasChecker().check([], _node("x**2 - 1 = (x - 1)*(x + 1)"), "algebra", None)
    assert r.passed
    assert r.kappa == Kappa.K2


def test_cas_rejects_false_identity():
    r = CasChecker().check([], _node("x**2 - 1 = x**2 + 1"), "algebra", None)
    assert not r.passed
    assert r.error_msg


def test_cas_rejects_non_equation():
    r = CasChecker().check([], _node("x**2 - 1"), "algebra", None)
    assert not r.passed
    assert r.error_msg


def test_cas_rejects_parse_error():
    r = CasChecker().check([], _node("this is not math = neither is this"), "algebra", None)
    assert not r.passed
    assert r.error_msg


# --- Z3 ---

def test_z3_verifies_valid_implication():
    r = Z3Checker().check([_node("x > 0")], _node("x + 1 > 0"), "arithmetic", None)
    assert r.passed
    assert r.kappa == Kappa.K3


def test_z3_rejects_counter_model():
    r = Z3Checker().check([_node("x > 0")], _node("x > 5"), "arithmetic", None)
    assert not r.passed
    assert "countermodel" in r.details


def test_z3_rejects_parse_error():
    r = Z3Checker().check(
        [_node("x > 0")], _node("this is not z3"), "arithmetic", None
    )
    assert not r.passed
    assert r.error_msg


def test_z3_multiple_premises():
    r = Z3Checker().check(
        [_node("x > 0"), _node("x < 2")], _node("x > -1"), "arithmetic", None
    )
    assert r.passed


# --- Lean ---

def test_lean_accepts_valid_proof():
    proof = b"theorem t : 1 + 1 = 2 := by rfl\n"
    r = LeanChecker().check([], _node("1 + 1 = 2"), "lean", proof)
    assert r.passed
    assert r.kappa == Kappa.K3


def test_lean_rejects_invalid_proof():
    proof = b"theorem t : 1 + 1 = 3 := by rfl\n"
    r = LeanChecker().check([], _node("1 + 1 = 3"), "lean", proof)
    assert not r.passed
    assert r.error_msg


def test_lean_requires_proof():
    r = LeanChecker().check([], _node("1 + 1 = 2"), "lean", None)
    assert not r.passed
    assert r.error_msg


# --- guardrail: timeout ---

def test_run_bounded_timeout():
    with pytest.raises(CheckerTimeout):
        run_bounded(lambda: time.sleep(10), 0.2)


def test_run_bounded_returns_value():
    assert run_bounded(lambda: 42, 5.0) == 42
