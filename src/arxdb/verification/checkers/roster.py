"""roster.py — the curated axiom roster (the κ∞ gate).

Resolved Q1: κ∞ is *earned*, not defaulted. A definition/axiom earns κ∞ only if
its claim matches the curated roster of accepted system ground; otherwise it is
κ1 (ELENCHUS-vetted only). This prevents unverified LLM-generated assertions
from masquerading as axiomatic truth and corrupting downstream min-propagation.

Matching is exact (after whitespace normalisation) — deliberately conservative:
a near-miss does not earn κ∞. The roster is small and hand-audited; it will grow
with the Phase 4 seed corpus, but every entry is a conscious addition.
"""

from __future__ import annotations

from typing import Sequence

from ..schema import Kappa, Node
from .base import CheckerResult

# The curated system ground. Keep small and hand-audited.
ROSTER: frozenset[str] = frozenset({
    "0 is a natural number",
    "the successor of a natural number is a natural number",
    "a prime is an integer greater than 1 with exactly two positive divisors",
    "the empty set has no elements",
    "for all x, x = x",
})


def _normalize(claim: str) -> str:
    return " ".join(claim.split())


def check_roster(node: Node) -> Kappa:
    """κ∞ if the claim is in the roster, else κ1."""
    return Kappa.K_INF if _normalize(node.claim) in ROSTER else Kappa.K1


class RosterChecker:
    """The κ∞ gate for definition/axiom edges.

    Always `passed=True` (the edge has already survived ELENCHUS); the κ
    distinguishes axiomatic ground (κ∞) from merely-vetted (κ1).
    """

    def check(
        self,
        premises: Sequence[Node],
        conclusion: Node,
        rule: str,
        proof_bytes: bytes | None,
        timeout_seconds: float = 5.0,
    ) -> CheckerResult:
        k = check_roster(conclusion)
        if k == Kappa.K_INF:
            return CheckerResult(True, Kappa.K_INF, {"roster": "matched"})
        return CheckerResult(True, Kappa.K1, {"roster": "unlisted"})
