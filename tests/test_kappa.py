"""Tests for kappa.py — the κ scale and propagation algebra."""

from __future__ import annotations

import pytest

from arxdb.verification.kappa import (
    corroborate,
    max_kappa,
    min_kappa,
    parallel,
    rank,
    series,
)
from arxdb.verification.schema import Kappa


# --- total order ---

def test_rank_is_strictly_increasing():
    ranks = [rank(k) for k in (Kappa.K0, Kappa.K1, Kappa.K2, Kappa.K3)]
    assert ranks == sorted(ranks)
    assert rank(Kappa.K_INF) == float("inf")


def test_min_kappa_weakest():
    assert min_kappa(Kappa.K3, Kappa.K1) == Kappa.K1
    assert min_kappa(Kappa.K1, Kappa.K3) == Kappa.K1


def test_max_kappa_strongest():
    assert max_kappa(Kappa.K1, Kappa.K3) == Kappa.K3


def test_min_kappa_requires_arg():
    with pytest.raises(ValueError):
        min_kappa()


def test_max_kappa_requires_arg():
    with pytest.raises(ValueError):
        max_kappa()


# --- series (transitivity) ---

def test_series_min():
    assert series(Kappa.K3, Kappa.K1) == Kappa.K1


def test_series_symmetric():
    assert series(Kappa.K1, Kappa.K3) == series(Kappa.K3, Kappa.K1)


# --- parallel (conjunction) ---

def test_parallel_conjunction():
    assert parallel(Kappa.K2, Kappa.K3, Kappa.K3) == Kappa.K2


def test_parallel_axiom_absorption():
    """min(K_INF, K2) = K2 — an axiomatic premise must not dominate."""
    assert parallel(Kappa.K_INF, Kappa.K2) == Kappa.K2


def test_parallel_all_inf():
    assert parallel(Kappa.K_INF, Kappa.K_INF) == Kappa.K_INF


# --- corroboration (independent derivations) ---

def test_corroborate_max():
    assert corroborate(Kappa.K1, Kappa.K3) == Kappa.K3


def test_corroborate_inf_dominates():
    assert corroborate(Kappa.K1, Kappa.K_INF) == Kappa.K_INF


# --- hand-checked examples from the plan ---

def test_plan_examples():
    # series min(κ3, κ1) = κ1
    assert series(Kappa.K3, Kappa.K1) == Kappa.K1
    # conjunction min(κ2, κ3, κ3) = κ2
    assert parallel(Kappa.K2, Kappa.K3, Kappa.K3) == Kappa.K2
    # corroboration max(κ1, κ3) = κ3
    assert corroborate(Kappa.K1, Kappa.K3) == Kappa.K3
    # axiom absorption min(κ∞, κ2) = κ2
    assert parallel(Kappa.K_INF, Kappa.K2) == Kappa.K2
