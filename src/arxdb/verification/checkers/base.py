"""base.py — the bounded formal-checker protocol.

Formal checkers (z3, sympy/mpmath, lean) can execute arbitrary code, consume
unbounded memory, or loop forever. This module defines the protocol every
checker implements and the guardrail machinery that bounds every invocation.

The contract every checker honours:
    - `check(...)` returns a `CheckerResult` — it never raises, never hangs.
    - `passed=False` with `error_msg` set is a *clean failure* (timeout, OOM,
      missing backend, parse error) — never a silent pass.
    - `passed=True` means the checker actually verified the claim, and `kappa`
      is the strength earned on that pass.

Boundary discipline: this module imports only the schema enums (`Kappa`, `Node`)
and the stdlib. No storage, no graph, no I/O beyond what a checker itself does.
"""

from __future__ import annotations

import signal
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, Sequence, TypeVar

from ..schema import Kappa, Node

T = TypeVar("T")


class CheckerTimeout(Exception):
    """Raised internally when a checker exceeds its time budget."""


@dataclass(frozen=True)
class CheckerResult:
    """The outcome of a single checker invocation.

    `passed=True` means the checker verified the claim; `kappa` is the strength
    earned. `passed=False` is a clean failure with `error_msg` explaining why
    (timeout, missing backend, parse error, counter-model, ...).
    """

    passed: bool
    kappa: Kappa
    details: dict[str, Any] = field(default_factory=dict)
    error_msg: str | None = None


class BaseChecker(Protocol):
    """The protocol every formal checker implements."""

    def check(
        self,
        premises: Sequence[Node],
        conclusion: Node,
        rule: str,
        proof_bytes: bytes | None,
        timeout_seconds: float = 5.0,
    ) -> CheckerResult: ...


def run_bounded(fn: Callable[[], T], timeout_seconds: float) -> T:
    """Run `fn` under a strict wall-clock timeout.

    Uses SIGALRM (Unix) for a *hard* timeout that actually interrupts runaway
    code — unlike a thread-based timeout, which cannot kill a stuck thread.
    On platforms without SIGALRM, `fn` runs unbounded (a documented limitation;
    the caller is still responsible for not passing pathological inputs).

    Raises `CheckerTimeout` if the budget is exceeded.
    """
    if timeout_seconds is None or timeout_seconds <= 0:
        return fn()

    if not hasattr(signal, "SIGALRM"):
        return fn()

    def _handler(signum, frame):
        raise CheckerTimeout(f"checker exceeded {timeout_seconds}s budget")

    previous = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        return fn()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
