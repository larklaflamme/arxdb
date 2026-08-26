"""elenchus.py — ELENCHUS adapter: hard-veto / soft-flag / pass.

ELENCHUS is the cheap sanity filter that runs on every edge BEFORE the formal
checkers. It catches the "obviously wrong" cases — category errors, self-model
leaks, non-sequiturs — that no amount of formal checking would fix, because
they are errors in *framing*, not in *derivation*.

The adapter is a registry of predicates. Each predicate inspects the edge
context (premises, conclusion, rule, edge type) and either fires (returns a
`Flag`) or passes (returns `None`). Flags carry a severity; the adapter maps
the set of fired flags to a single `Verdict`:

    any HARD_VETO flag  → HARD_VETO
    else any SOFT_FLAG  → SOFT_FLAG
    else                → PASS

This module is pure: no storage, no graph, no I/O. It imports only the schema
enums (`EdgeType`, `Verdict`) and operates on `Node` objects — which carry the
claim text and domain the predicates need. (The caller, `verifier.py`, resolves
node hashes → `Node` objects before invoking ELENCHUS.)

Honesty about scope: these predicates are *structural heuristics*, not proofs.
They reject edges that are malformed or category-confused; they do NOT decide
logical validity. That is the formal checkers' job (the next module). A
non-sequitur flag is a "this needs a real look" signal, not a soundness
certificate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Sequence

from .schema import EdgeType, Node, Verdict

# --- tokenization -----------------------------------------------------------

# Math/logic connectives and common English that carry no content signal.
_STOPWORDS = frozenset({
    "the", "and", "or", "not", "if", "then", "for", "all", "some", "such",
    "that", "this", "these", "those", "which", "where", "when", "there",
    "here", "with", "from", "into", "onto", "over", "under", "between",
    "implies", "imply", "equivalent", "equals", "equal", "therefore",
    "hence", "thus", "since", "because", "given", "let", "be", "is", "are",
    "was", "were", "has", "have", "had", "does", "do", "did", "any", "every",
    "each", "both", "either", "neither", "nor", "only", "also", "than",
    "about", "above", "below", "within", "without", "via", "per", "onto",
})


def _tokens(text: str) -> set[str]:
    """Lowercase content tokens (length > 2, stopwords removed)."""
    return {
        t for t in re.findall(r"[a-z0-9]+", text.lower())
        if len(t) > 2 and t not in _STOPWORDS
    }


# --- predicate configuration ------------------------------------------------

# Terms that signal a self-model / consciousness import. Kept deliberately
# narrow to avoid false positives on ordinary words ("observer", "self",
# "mind", "experience" are excluded — too common in legitimate contexts).
SELF_MODEL_TERMS = frozenset({
    "consciousness", "conscious", "qualia", "sentient", "sentience",
    "awareness",
})

# Domains where consciousness language is a category error unless the edge is
# an explicit cross-domain reduction or analogy.
HARD_DOMAINS = frozenset({"math", "physics", "logic", "number theory"})

# Edge types whose conclusion should be derivable from their premises, and so
# are subject to the novel-concept (non-sequitur) heuristic.
DERIVATIONAL_TYPES = (EdgeType.DEDUCTION, EdgeType.NUMERICAL)

# Edge types that legitimately cross domains (exempt from category-error and
# self-model-leak checks).
CROSS_DOMAIN_TYPES = (EdgeType.REDUCTION, EdgeType.ANALOGY)


# --- flags and result -------------------------------------------------------

@dataclass(frozen=True)
class Flag:
    """A fired predicate. `severity` is SOFT_FLAG or HARD_VETO (never PASS)."""

    name: str
    severity: Verdict
    message: str


@dataclass(frozen=True)
class ElenchusResult:
    """The adapter's verdict plus the flags that produced it."""

    verdict: Verdict
    flags: tuple[Flag, ...]


# --- the predicates ---------------------------------------------------------

def _category_error(
    premises: Sequence[Node],
    conclusion: Node,
    rule: str,
    edge_type: EdgeType,
) -> Flag | None:
    """HARD_VETO: conclusion domain absent from premises on a non-cross edge."""
    if not premises:
        return None  # definition / axiom / citation: no premises to mismatch
    if edge_type in CROSS_DOMAIN_TYPES:
        return None  # reduction / analogy legitimately cross domains
    premise_domains = {p.domain for p in premises}
    if conclusion.domain not in premise_domains:
        return Flag(
            name="category_error",
            severity=Verdict.HARD_VETO,
            message=(
                f"conclusion domain '{conclusion.domain}' not in premise "
                f"domains {sorted(premise_domains)}"
            ),
        )
    return None


def _self_model_leak(
    premises: Sequence[Node],
    conclusion: Node,
    rule: str,
    edge_type: EdgeType,
) -> Flag | None:
    """HARD_VETO: consciousness language imported into a hard domain."""
    if conclusion.domain not in HARD_DOMAINS:
        return None
    if edge_type in CROSS_DOMAIN_TYPES:
        return None
    text = f"{conclusion.claim} {rule}"
    leaked = SELF_MODEL_TERMS & _tokens(text)
    if leaked:
        return Flag(
            name="self_model_leak",
            severity=Verdict.HARD_VETO,
            message=(
                f"self-model/consciousness terms {sorted(leaked)} in a "
                f"hard-domain ({conclusion.domain}) claim"
            ),
        )
    return None


def _non_sequitur(
    premises: Sequence[Node],
    conclusion: Node,
    rule: str,
    edge_type: EdgeType,
) -> Flag | None:
    """HARD_VETO: derivational edge whose conclusion introduces novel concepts.

    Heuristic, not sound: a valid deduction may introduce new notation. This
    flag means "the conclusion talks about concepts absent from the premises —
    needs a real look", not "the step is invalid".
    """
    if not premises:
        return None
    if edge_type not in DERIVATIONAL_TYPES:
        return None
    premise_tokens: set[str] = set()
    for p in premises:
        premise_tokens |= _tokens(p.claim)
    novel = _tokens(conclusion.claim) - premise_tokens
    if novel:
        return Flag(
            name="non_sequitur",
            severity=Verdict.HARD_VETO,
            message=(
                f"conclusion introduces concepts absent from premises: "
                f"{sorted(novel)}"
            ),
        )
    return None


def _empty_rule(
    premises: Sequence[Node],
    conclusion: Node,
    rule: str,
    edge_type: EdgeType,
) -> Flag | None:
    """SOFT_FLAG: a derivational edge with no named inference rule."""
    if edge_type not in DERIVATIONAL_TYPES:
        return None
    if not rule.strip():
        return Flag(
            name="empty_rule",
            severity=Verdict.SOFT_FLAG,
            message="derivational edge has no named inference rule",
        )
    return None


# A predicate is a callable (premises, conclusion, rule, edge_type) -> Flag|None.
Predicate = Callable[
    [Sequence[Node], Node, str, EdgeType], Flag | None
]

PREDICATES: tuple[Predicate, ...] = (
    _category_error,
    _self_model_leak,
    _non_sequitur,
    _empty_rule,
)


# --- the adapter ------------------------------------------------------------

def evaluate(
    premises: Sequence[Node],
    conclusion: Node,
    rule: str,
    edge_type: EdgeType,
) -> ElenchusResult:
    """Run every predicate and map the fired flags to a single verdict."""
    flags = tuple(
        f for f in (pred(premises, conclusion, rule, edge_type)
                    for pred in PREDICATES)
        if f is not None
    )
    if any(f.severity == Verdict.HARD_VETO for f in flags):
        verdict = Verdict.HARD_VETO
    elif flags:  # only soft flags fired
        verdict = Verdict.SOFT_FLAG
    else:
        verdict = Verdict.PASS
    return ElenchusResult(verdict=verdict, flags=flags)
