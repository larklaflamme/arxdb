"""Tests for elenchus.py — the ELENCHUS adapter (hard-veto / soft-flag / pass)."""

from __future__ import annotations

from arxdb.verification.elenchus import evaluate
from arxdb.verification.schema import EdgeType, Node, Verdict


def _node(claim: str, domain: str = "math") -> Node:
    return Node(claim=claim, domain=domain)


def _flag_names(result) -> set[str]:
    return {f.name for f in result.flags}


# --- category error (HARD_VETO) ---

def test_category_error_hard_veto():
    """A deduction whose conclusion domain is absent from its premises."""
    r = evaluate(
        premises=[_node("A implies B", "math")],
        conclusion=_node("C implies D", "physics"),
        rule="modus ponens",
        edge_type=EdgeType.DEDUCTION,
    )
    assert r.verdict == Verdict.HARD_VETO
    assert "category_error" in _flag_names(r)


def test_category_error_exempt_for_reduction():
    """A reduction legitimately crosses domains."""
    r = evaluate(
        premises=[_node("A implies B", "math")],
        conclusion=_node("C implies D", "physics"),
        rule="isomorphism",
        edge_type=EdgeType.REDUCTION,
    )
    assert "category_error" not in _flag_names(r)


def test_category_error_exempt_for_analogy():
    r = evaluate(
        premises=[_node("A implies B", "math")],
        conclusion=_node("C implies D", "physics"),
        rule="structural analogy",
        edge_type=EdgeType.ANALOGY,
    )
    assert "category_error" not in _flag_names(r)


def test_category_error_skips_empty_premises():
    """A definition (no premises) has nothing to mismatch."""
    r = evaluate(
        premises=[],
        conclusion=_node("A prime is an integer with exactly two divisors"),
        rule="definition",
        edge_type=EdgeType.DEFINITION,
    )
    assert "category_error" not in _flag_names(r)


# --- self-model leak (HARD_VETO) ---

def test_self_model_leak_hard_veto():
    """Consciousness language imported into a math claim."""
    r = evaluate(
        premises=[_node("A implies B", "math")],
        conclusion=_node("RH holds because consciousness is fundamental", "math"),
        rule="modus ponens",
        edge_type=EdgeType.DEDUCTION,
    )
    assert r.verdict == Verdict.HARD_VETO
    assert "self_model_leak" in _flag_names(r)


def test_self_model_leak_exempt_for_analogy():
    r = evaluate(
        premises=[_node("A implies B", "math")],
        conclusion=_node("RH holds because consciousness is fundamental", "math"),
        rule="structural analogy",
        edge_type=EdgeType.ANALOGY,
    )
    assert "self_model_leak" not in _flag_names(r)


def test_self_model_leak_ignores_non_hard_domain():
    """Consciousness language in a consciousness domain is fine."""
    r = evaluate(
        premises=[_node("integrated information is high", "consciousness")],
        conclusion=_node("consciousness is integrated information", "consciousness"),
        rule="modus ponens",
        edge_type=EdgeType.DEDUCTION,
    )
    assert "self_model_leak" not in _flag_names(r)


# --- non-sequitur (HARD_VETO) ---

def test_non_sequitur_hard_veto():
    """A deduction whose conclusion introduces concepts absent from premises."""
    r = evaluate(
        premises=[_node("A implies B", "math")],
        conclusion=_node("quantum entanglement violates locality", "math"),
        rule="modus ponens",
        edge_type=EdgeType.DEDUCTION,
    )
    assert r.verdict == Verdict.HARD_VETO
    assert "non_sequitur" in _flag_names(r)


def test_non_sequitur_passes_when_concepts_overlap():
    """A clean modus-ponens chain: conclusion concepts all appear in premises."""
    r = evaluate(
        premises=[_node("A implies B", "math"), _node("B implies C", "math")],
        conclusion=_node("A implies C", "math"),
        rule="modus ponens",
        edge_type=EdgeType.DEDUCTION,
    )
    assert "non_sequitur" not in _flag_names(r)


def test_non_sequitur_skips_empty_premises():
    r = evaluate(
        premises=[],
        conclusion=_node("A prime is an integer with exactly two divisors"),
        rule="definition",
        edge_type=EdgeType.DEFINITION,
    )
    assert "non_sequitur" not in _flag_names(r)


# --- empty rule (SOFT_FLAG) ---

def test_empty_rule_soft_flag():
    """A deduction with no named rule is a soft flag, not a hard veto."""
    r = evaluate(
        premises=[_node("A implies B", "math")],
        conclusion=_node("A implies C", "math"),
        rule="",
        edge_type=EdgeType.DEDUCTION,
    )
    assert r.verdict == Verdict.SOFT_FLAG
    assert "empty_rule" in _flag_names(r)


# --- clean pass ---

def test_clean_edge_passes():
    """A well-formed deduction with a named rule and overlapping concepts."""
    r = evaluate(
        premises=[_node("A implies B", "math"), _node("B implies C", "math")],
        conclusion=_node("A implies C", "math"),
        rule="modus ponens",
        edge_type=EdgeType.DEDUCTION,
    )
    assert r.verdict == Verdict.PASS
    assert r.flags == ()


# --- verdict precedence ---

def test_hard_veto_dominates_soft_flag():
    """When both a hard veto and a soft flag fire, the verdict is HARD_VETO."""
    r = evaluate(
        premises=[_node("A implies B", "math")],
        conclusion=_node("quantum entanglement violates locality", "physics"),
        rule="",  # empty rule → soft flag; domain mismatch → hard veto
        edge_type=EdgeType.DEDUCTION,
    )
    assert r.verdict == Verdict.HARD_VETO
    names = _flag_names(r)
    assert "category_error" in names
    assert "empty_rule" in names
