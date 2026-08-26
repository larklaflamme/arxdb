"""cas_check.py — the CAS checker (sympy/mpmath).

Verifies numerical and algebraic identities. The conclusion's claim must be an
equation "lhs = rhs" parseable by sympy. On success the two sides are
symbolically equal (κ2); on failure the sides differ, or the claim is not a
parseable equation (a clean failure — never a silent pass).

The checker is deliberately narrow: it handles *identities*, not arbitrary
theorems. Parsing uses sympy's `parse_expr` (not `eval`), so claim text is
treated as an expression, not as Python code.
"""

from __future__ import annotations

from typing import Sequence

from sympy import simplify
from sympy.parsing.sympy_parser import parse_expr

from ..schema import Kappa, Node
from .base import CheckerResult, CheckerTimeout, run_bounded


class CasChecker:
    def check(
        self,
        premises: Sequence[Node],
        conclusion: Node,
        rule: str,
        proof_bytes: bytes | None,
        timeout_seconds: float = 5.0,
    ) -> CheckerResult:
        def _run() -> CheckerResult:
            claim = conclusion.claim
            if "=" not in claim:
                return CheckerResult(False, Kappa.K0, {}, "claim is not an equation")
            lhs_s, rhs_s = claim.split("=", 1)
            try:
                lhs = parse_expr(lhs_s, transformations="all")
                rhs = parse_expr(rhs_s, transformations="all")
            except Exception as e:  # SympifyError / TokenError / ...
                return CheckerResult(False, Kappa.K0, {}, f"parse error: {e}")
            if simplify(lhs - rhs) == 0:
                return CheckerResult(
                    True, Kappa.K2, {"lhs": str(lhs), "rhs": str(rhs)}
                )
            return CheckerResult(False, Kappa.K0, {}, "sides are not equal")

        try:
            return run_bounded(_run, timeout_seconds)
        except CheckerTimeout as e:
            return CheckerResult(False, Kappa.K0, {}, str(e))
