"""checkers/ — pluggable formal checkers behind a bounded protocol.

    base       — CheckerResult, BaseChecker protocol, run_bounded guardrail
    roster     — the curated axiom roster (the κ∞ gate)
    cas_check  — sympy/mpmath CAS checker (numerical/algebraic identities)
    z3_check   — z3 SMT checker (logical implications)
    lean_check — Lean 4 subprocess checker (formal proofs)
"""

from .base import BaseChecker, CheckerResult, CheckerTimeout, run_bounded
from .cas_check import CasChecker
from .lean_check import LeanChecker
from .roster import ROSTER, RosterChecker, check_roster
from .z3_check import Z3Checker

__all__ = [
    "BaseChecker",
    "CheckerResult",
    "CheckerTimeout",
    "run_bounded",
    "CasChecker",
    "LeanChecker",
    "RosterChecker",
    "Z3Checker",
    "ROSTER",
    "check_roster",
]
