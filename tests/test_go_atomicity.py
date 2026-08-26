"""test_go_atomicity.py — cross-process failure recovery (PHASE6_PLAN.md §10).

Failure mode 2 (the trap §1 is designed to avoid): if `CommitEdge` were
implemented as *multiple* RPCs instead of one, a crash between them would
corrupt the graph. The guard is that `CommitEdge` is a single RPC that performs
the whole atomic commit server-side, inside one Pebble indexed batch.

This test runs the Go fault-injection test (`TestCommitEdgeTxFaultInjection`),
which injects a failure *after* the graph edge and log entry are written to the
batch but *before* the batch is committed, and asserts zero partial state: the
graph has no edge, the log is empty. (The object blob is orphaned — idempotent
and harmless, matching the Python contract.)

The fault is injected via a package-level test hook (`testHookCommitEdgeTx`) in
`go/pkg/storage/storage.go`, which is nil in production.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GO_DIR = REPO_ROOT / "go"


def _find_go() -> str | None:
    go = shutil.which("go")
    if go:
        return go
    goroot = os.environ.get("GOROOT")
    if goroot:
        candidate = Path(goroot) / "bin" / "go"
        if candidate.exists():
            return str(candidate)
    return None


@pytest.mark.skipif(
    _find_go() is None,
    reason="Go toolchain not installed (see SETUP.md §3)",
)
def test_go_commit_edge_tx_fault_injection() -> None:
    """A failed CommitEdgeTx leaves zero partial state in the Go engine."""
    assert GO_DIR.exists(), f"go module missing: {GO_DIR}"

    result = subprocess.run(
        ["go", "test", "./pkg/storage/", "-run", "TestCommitEdgeTxFaultInjection", "-v"],
        cwd=GO_DIR,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        pytest.fail(
            "Go fault-injection test failed:\n" + result.stdout + result.stderr
        )
