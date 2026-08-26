"""lean_check.py — the Lean 4 checker (subprocess).

Runs a Lean 4 proof via subprocess. The proof is supplied as `proof_bytes`
(the Lean source text). A proof that type-checks (exit 0) passes at κ3; a proof
that fails to type-check is a clean failure; a timeout or missing `lean` binary
is a clean failure — never a hang, never a silent pass.

This is the only checker that executes *external* code, so it gets subprocess
isolation + a strict timeout.

On the memory cap: the plan calls for a memory cap, but an explicit
`resource.setrlimit` is *incompatible* with Lean 4's runtime — its allocator
reserves a large virtual address space at startup, so even a 4 GiB cap breaks
thread creation ("failed to create thread"). The actual safety is provided by
three mechanisms that do not fight the allocator:
    1. the strict subprocess timeout (prevents hangs);
    2. the OS OOM-killer (kills a runaway proof → non-zero returncode);
    3. non-zero-returncode handling (any OOM/kill is a clean failure, never a
       silent pass).
This is a documented, deliberate deviation from the plan's "memory cap" wording.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import Sequence

from ..schema import Kappa, Node
from .base import CheckerResult

LEAN_BINARY: str | None = shutil.which("lean") or os.environ.get("LEAN_BINARY")


class LeanChecker:
    def check(
        self,
        premises: Sequence[Node],
        conclusion: Node,
        rule: str,
        proof_bytes: bytes | None,
        timeout_seconds: float = 5.0,
    ) -> CheckerResult:
        if LEAN_BINARY is None:
            return CheckerResult(False, Kappa.K0, {}, "lean binary not found")
        if not proof_bytes:
            return CheckerResult(False, Kappa.K0, {}, "no proof supplied")

        with tempfile.NamedTemporaryFile(
            suffix=".lean", mode="wb", delete=False
        ) as f:
            f.write(proof_bytes)
            path = f.name

        try:
            try:
                proc = subprocess.run(
                    [LEAN_BINARY, path],
                    capture_output=True,
                    timeout=timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                return CheckerResult(
                    False, Kappa.K0, {}, f"lean timed out after {timeout_seconds}s"
                )
            except OSError as e:
                return CheckerResult(False, Kappa.K0, {}, f"lean failed to run: {e}")
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

        if proc.returncode == 0:
            return CheckerResult(True, Kappa.K3, {"lean": "type-checked"})
        return CheckerResult(
            False, Kappa.K0,
            {"stderr": proc.stderr.decode("utf-8", "replace")[:500]},
            "lean rejected the proof",
        )
