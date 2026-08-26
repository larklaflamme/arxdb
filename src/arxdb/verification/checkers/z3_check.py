"""z3_check.py — the Z3 SMT checker.

Verifies logical implications: does the conjunction of the premises entail the
conclusion? The checker asserts `And(premises) ∧ Not(conclusion)` and asks z3
for satisfiability:
    - `unsat`   → the implication is valid (κ3)
    - `sat`     → a counter-model exists (clean failure, model reported)
    - `unknown` → z3 could not decide (clean failure; e.g. nonlinear arithmetic)

Claim convention: a claim's text is a Python expression over the declared
variables (`x`, `y`, `z` as Reals; `n`, `m` as Ints) using z3's overloaded
operators (`>`, `<`, `+`, `*`, `And`, `Or`, `Not`, ...). Parsing uses a
*restricted* `eval` with no builtins and a namespace containing only z3 objects
— claim text is an expression, not arbitrary code.
"""

from __future__ import annotations

from typing import Sequence

import z3

from ..schema import Kappa, Node
from .base import CheckerResult, CheckerTimeout, run_bounded

# Declared variables (documented convention).
_VARS: dict[str, z3.ExprRef] = {
    "x": z3.Real("x"),
    "y": z3.Real("y"),
    "z": z3.Real("z"),
    "n": z3.Int("n"),
    "m": z3.Int("m"),
}

_NAMESPACE: dict = dict(_VARS)
_NAMESPACE.update({
    "And": z3.And,
    "Or": z3.Or,
    "Not": z3.Not,
    "Implies": z3.Implies,
    "ForAll": z3.ForAll,
    "Exists": z3.Exists,
})


def _parse(claim: str) -> z3.BoolRef:
    expr = eval(claim, {"__builtins__": {}}, _NAMESPACE)
    if not isinstance(expr, z3.BoolRef):
        raise ValueError(f"claim is not a boolean expression: {claim!r}")
    return expr


class Z3Checker:
    def check(
        self,
        premises: Sequence[Node],
        conclusion: Node,
        rule: str,
        proof_bytes: bytes | None,
        timeout_seconds: float = 5.0,
    ) -> CheckerResult:
        def _run() -> CheckerResult:
            try:
                premise_exprs = [_parse(p.claim) for p in premises]
                concl_expr = _parse(conclusion.claim)
            except (ValueError, SyntaxError, NameError, TypeError) as e:
                return CheckerResult(False, Kappa.K0, {}, f"parse error: {e}")

            s = z3.Solver()
            s.set(timeout=int(timeout_seconds * 1000))  # z3's own budget (ms)
            s.add(z3.And(*premise_exprs))
            s.add(z3.Not(concl_expr))
            result = s.check()

            if result == z3.unsat:
                return CheckerResult(True, Kappa.K3, {"method": "z3", "result": "unsat"})
            if result == z3.sat:
                return CheckerResult(
                    False, Kappa.K0,
                    {"countermodel": str(s.model())},
                    "counter-model found",
                )
            return CheckerResult(False, Kappa.K0, {}, "z3 returned unknown")

        try:
            return run_bounded(_run, timeout_seconds)
        except CheckerTimeout as e:
            return CheckerResult(False, Kappa.K0, {}, str(e))
