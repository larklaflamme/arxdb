"""Shared helpers for the Phase 6 gRPC test suites.

These helpers build and manage the `arxdbd` daemon (the Go storage engine over
gRPC) so that the Python test suites can exercise the drop-in `GrpcStorage`
client against a live process.

The daemon owns the storage engine and the signing keypair; the Python client
holds only a gRPC channel. A fresh daemon (fresh data-dir + fresh socket) is
the unit of test isolation — the analogue of the `tmp_root` fixture for the
in-process SQLite backend.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GO_DIR = REPO_ROOT / "go"
DAEMON_SRC = GO_DIR / "cmd" / "arxdbd"

# A short, stable location for the built daemon binary. UNIX socket paths are
# limited to ~108 bytes, so the socket itself is placed under /tmp with a short
# name (see _short_socket_path below).
DAEMON_BIN = Path("/tmp/arxdbd")


def _find_go() -> str | None:
    """Locate the go binary (PATH first, then GOROOT)."""
    go = shutil.which("go")
    if go:
        return go
    goroot = os.environ.get("GOROOT")
    if goroot:
        candidate = Path(goroot) / "bin" / "go"
        if candidate.exists():
            return str(candidate)
    return None


def build_daemon() -> Path:
    """Build the arxdbd daemon binary, returning its path.

    Idempotent: if the binary already exists and is newer than the source, it is
    reused. Raises if the Go toolchain is unavailable.
    """
    go = _find_go()
    if go is None:
        raise RuntimeError("Go toolchain not installed (see SETUP.md §3)")

    needs_build = not DAEMON_BIN.exists()
    if not needs_build:
        # Rebuild if any source under go/ is newer than the binary.
        src_mtime = max(
            p.stat().st_mtime for p in GO_DIR.rglob("*.go") if p.is_file()
        )
        needs_build = src_mtime > DAEMON_BIN.stat().st_mtime

    if needs_build:
        result = subprocess.run(
            [go, "build", "-o", str(DAEMON_BIN), "./cmd/arxdbd"],
            cwd=GO_DIR,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "failed to build arxdbd:\n" + result.stdout + result.stderr
            )
    return DAEMON_BIN


def _short_socket_path(data_dir: Path) -> Path:
    """A short UNIX socket path derived from the data-dir (fits the 108-byte limit)."""
    # Use a hash of the data-dir to keep the socket name short and unique.
    digest = abs(hash(str(data_dir))) % (10**10)
    return Path(f"/tmp/arxdb-{digest}.sock")


def start_daemon(data_dir: Path) -> tuple[subprocess.Popen, Path]:
    """Start a fresh arxdbd daemon rooted at `data_dir`.
    Returns (process, socket_path).

    The daemon generates (or reuses) its own keypair under `data_dir`, listens
    on a short UNIX socket, and logs to `data_dir/daemon.log`. Blocks until the
    socket is ready.
    """
    bin_path = build_daemon()
    data_dir.mkdir(parents=True, exist_ok=True)
    socket_path = _short_socket_path(data_dir)
    log_path = data_dir / "daemon.log"

    # Remove a stale socket from a previous run.
    if socket_path.exists():
        socket_path.unlink()

    log_file = open(log_path, "wb")
    proc = subprocess.Popen(
        [
            str(bin_path),
            "--data-dir", str(data_dir),
            "--socket", str(socket_path),
        ],
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    # Wait for the socket to appear (bounded).
    deadline = time.time() + 10.0
    while time.time() < deadline:
        if socket_path.exists():
            return proc, socket_path
        if proc.poll() is not None:
            log_file.close()
            raise RuntimeError(
                f"arxdbd exited early (code {proc.returncode}); log:\n"
                + log_path.read_text()
            )
        time.sleep(0.05)

    proc.terminate()
    log_file.close()
    raise RuntimeError(
        f"arxdbd did not create socket within 10s; log:\n{log_path.read_text()}"
    )


def stop_daemon(proc: subprocess.Popen) -> None:
    """Terminate a daemon started by `start_daemon`."""
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
