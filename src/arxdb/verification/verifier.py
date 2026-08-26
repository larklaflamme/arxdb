"""verifier.py — the κ-tiering pipeline.

The verifier is the orchestration layer that turns an edge proposal into a
(verdict, κ) pair. It composes the two layers built so far:

    1. ELENCHUS (always, every edge) — the cheap sanity filter that rejects
       malformed / category-confused edges before any formal work.
    2. A type-appropriate formal checker (dispatch by EdgeType) — the bounded
       check that actually verifies the claim and earns its κ.

The pipeline, per edge:

    1. Run ELENCHUS. A HARD_VETO rejects the edge outright (κ0, do not store).
    2. Dispatch to the checker for this edge type (if any).
       - A checker failure (passed=False) is a rejection: the claim is false,
         unverifiable, or the check timed out — never a silent pass.
       - A checker pass earns the checker's κ.
    3. Combine: verdict = ELENCHUS verdict (PASS or SOFT_FLAG) when the edge
       survives; κ = the checker's κ, or a fixed default for edge types with
       no dedicated checker.

Dispatch table (EdgeType → checker → κ on pass):

    definition  → roster  → κ∞ (roster match) or κ1 (unlisted)
    deduction   → z3      → κ3   (lean when proof_bytes supplied)
    numerical   → cas     → κ2
    reduction   → (none)  → κ1   (ELENCHUS-vetted only)
    refutation  → (none)  → κ1   (ELENCHUS-vetted only)
    analogy     → (none)  → κ0   (structural heuristic only)
    citation    → (none)  → κ1   (ELENCHUS-vetted only)

Honesty about scope: REDUCTION, REFUTATION, ANALOGY, and CITATION have no
dedicated checker in Phase 2. They are ELENCHUS-vetted only and carry a fixed
κ (the plan's lower bound). A dedicated reduction checker (isomorphism proof)
and refutation checker (counterexample witness / inconsistency proof) are
future work — the dispatch table is the single place they will plug in.

Boundary discipline: this module imports only the schema enums, the ELENCHUS
adapter, and the checkers. No sqlite3, no pathlib, no Storage internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .checkers.base import CheckerResult
from .checkers.cas_check import CasChecker
from .checkers.lean_check import LeanChecker
from .checkers.roster import RosterChecker
from .checkers.z3_check import Z3Checker
from .elenchus import ElenchusResult, evaluate
from .schema import EdgeType, Kappa, Node, Verdict


@dataclass(frozen=True)
class VerificationResult:
    """The verifier's outcome for a single edge proposal.

    `verdict` is the single reject/store signal: HARD_VETO means "do not
    store" (the edge is malformed, false, or unverifiable); PASS and SOFT_FLAG
    mean "store" (SOFT_FLAG carries a non-fatal flag worth a human look).

    `kappa` is the strength earned: the checker's κ on a pass, a fixed default
    for edge types with no checker, or K0 on rejection.

    `elenchus` and `checker` are carried for diagnostics — they preserve the
    *why* behind the verdict (which predicate fired, which checker ran, what
    the counter-model was).
    """

    verdict: Verdict
    kappa: Kappa
    elenchus: ElenchusResult
    checker: CheckerResult | None
    edge_type: EdgeType
    rule: str

    @property
    def rejected(self) -> bool:
        """True iff this edge must not be stored (HARD_VETO)."""
        return self.verdict == Verdict.HARD_VETO


# Fixed κ for edge types with no dedicated checker (ELENCHUS-vetted only).
_DEFAULT_KAPPA: dict[EdgeType, Kappa] = {
    EdgeType.REDUCTION: Kappa.K1,
    EdgeType.REFUTATION: Kappa.K1,
    EdgeType.ANALOGY: Kappa.K0,
    EdgeType.CITATION: Kappa.K1,
}


def _checker_for(edge_type: EdgeType, proof_bytes: bytes | None):
    """Return the checker instance for this edge type, or None if none applies.

    DEDUCTION dispatches to Lean when a formal proof is supplied (Lean needs
    `proof_bytes`), and to Z3 otherwise (Z3 works on claim text as logical
    expressions). This is a documented convention: a deduction's `proof_bytes`
    is Lean source; to use Z3, omit `proof_bytes`.
    """
    if edge_type == EdgeType.DEFINITION:
        return RosterChecker()
    if edge_type == EdgeType.DEDUCTION:
        return LeanChecker() if proof_bytes else Z3Checker()
    if edge_type == EdgeType.NUMERICAL:
        return CasChecker()
    return None


def verify(
    premises: Sequence[Node],
    conclusion: Node,
    rule: str,
    edge_type: EdgeType,
    proof_bytes: bytes | None = None,
    timeout_seconds: float = 5.0,
) -> VerificationResult:
    """Run the κ-tiering pipeline on an edge proposal.

    Returns a `VerificationResult` whose `verdict` is the reject/store signal
    and whose `kappa` is the strength earned. Never raises, never hangs: every
    checker is bounded, and a checker failure is a clean rejection.
    """
    elenchus = evaluate(premises, conclusion, rule, edge_type)

    # 1. ELENCHUS hard-veto: reject before any formal work.
    if elenchus.verdict == Verdict.HARD_VETO:
        return VerificationResult(
            verdict=Verdict.HARD_VETO,
            kappa=Kappa.K0,
            elenchus=elenchus,
            checker=None,
            edge_type=edge_type,
            rule=rule,
        )

    # 2. Type-appropriate check.
    checker = _checker_for(edge_type, proof_bytes)
    if checker is None:
        # No dedicated checker: ELENCHUS-vetted only, fixed κ.
        return VerificationResult(
            verdict=elenchus.verdict,
            kappa=_DEFAULT_KAPPA[edge_type],
            elenchus=elenchus,
            checker=None,
            edge_type=edge_type,
            rule=rule,
        )

    result = checker.check(
        premises, conclusion, rule, proof_bytes, timeout_seconds
    )

    # 3. A checker failure is a rejection (false / unverifiable / timeout).
    if not result.passed:
        return VerificationResult(
            verdict=Verdict.HARD_VETO,
            kappa=Kappa.K0,
            elenchus=elenchus,
            checker=result,
            edge_type=edge_type,
            rule=rule,
        )

    # 4. Checker passed: verdict is the ELENCHUS verdict (PASS or SOFT_FLAG),
    #    κ is the checker's earned strength.
    return VerificationResult(
        verdict=elenchus.verdict,
        kappa=result.kappa,
        elenchus=elenchus,
        checker=result,
        edge_type=edge_type,
        rule=rule,
    )
