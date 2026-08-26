"""kappa.py — the κ-strength scale and its propagation algebra.

κ is a discrete strength label on reasoning edges. The scale is totally
ordered:

    K0 < K1 < K2 < K3 < K_INF

where K_INF is the top element (axiomatic ground, earned only via the curated
roster — see resolved Q1). The propagation algebra is *defined* here (Phase 2)
but *applied* during graph traversal (Phase 3, query). This module is pure:
no storage, no graph, no I/O — just the algebra.

The three operations (per PHASE2_PLAN.md):

    series(a, b)        — transitivity:  κ(A→C) = min(κ(A→B), κ(B→C))
    parallel(*ks)       — conjunction:   κ(C)   = min(κ(A), κ(B), κ_rule)
    corroborate(*ks)    — independent derivations: κ(C) = max(κ_path₁, κ_path₂)

The key soundness property is **axiom absorption**: min(K_INF, x) = x. A single
κ∞ premise must *not* dominate a conjunction — otherwise one axiomatic premise
would mask a weak sibling and corrupt downstream min-propagation. This is why
κ∞ is earned (roster) and why min is the conjunction rule.
"""

from __future__ import annotations

from .schema import Kappa

# Total order on the κ scale. K_INF is the top element.
_RANK: dict[Kappa, float] = {
    Kappa.K0: 0.0,
    Kappa.K1: 1.0,
    Kappa.K2: 2.0,
    Kappa.K3: 3.0,
    Kappa.K_INF: float("inf"),
}


def rank(k: Kappa) -> float:
    """The numeric rank of a κ label (K_INF → +∞)."""
    return _RANK[k]


def min_kappa(*ks: Kappa) -> Kappa:
    """The weakest κ among the given labels (the min in the total order)."""
    if not ks:
        raise ValueError("min_kappa requires at least one κ")
    return min(ks, key=rank)


def max_kappa(*ks: Kappa) -> Kappa:
    """The strongest κ among the given labels (the max in the total order)."""
    if not ks:
        raise ValueError("max_kappa requires at least one κ")
    return max(ks, key=rank)


def series(a: Kappa, b: Kappa) -> Kappa:
    """Transitivity: κ(A→C) = min(κ(A→B), κ(B→C)).

    A chain is only as strong as its weakest link.
    """
    return min_kappa(a, b)


def parallel(*ks: Kappa) -> Kappa:
    """Conjunction: κ(C) = min(κ(A), κ(B), κ_rule).

    A conclusion resting on several premises is only as strong as the weakest
    premise (and the rule that joins them). This is the axiom-absorption rule:
    min(K_INF, x) = x.
    """
    return min_kappa(*ks)


def corroborate(*ks: Kappa) -> Kappa:
    """Independent derivations: κ(C) = max(κ_path₁, κ_path₂).

    Multiple *independent* derivations of the same conclusion corroborate: the
    strongest path wins. (Independence is a Phase 3 concern — this algebra only
    defines the max.)
    """
    return max_kappa(*ks)
