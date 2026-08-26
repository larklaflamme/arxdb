"""07 — Go gRPC backend: the drop-in swap.

Run from the repo root with the arxdb env active:

    python examples/07-go-grpc-backend/grpc_demo.py

The same facade operations run against the Go storage engine (Pebble) over
gRPC instead of the in-process SQLite backend. The only thing that changes is
`backend="grpc"` — the verification, query, and attestation layers are
identical.

This script builds and starts the `arxdbd` daemon, drives it through the
`GrpcStorage` client, then stops it.
"""

import os
import shutil
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from arxdb.query import reachable
from arxdb.storage.factory import create_storage
from arxdb.storage.keys import generate_keypair
from arxdb.verification.commit import verify_and_commit
from arxdb.verification.schema import EdgeType, Node

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GO_DIR = REPO_ROOT / "go"
DAEMON_BIN = Path("/tmp/arxdbd")


def _find_go() -> str:
    go = shutil.which("go")
    if go:
        return go
    goroot = os.environ.get("GOROOT")
    if goroot:
        candidate = Path(goroot) / "bin" / "go"
        if candidate.exists():
            return str(candidate)
    raise RuntimeError("Go toolchain not installed (see SETUP.md §3)")


def build_daemon() -> Path:
    go = _find_go()
    subprocess.run(
        [go, "build", "-o", str(DAEMON_BIN), "./cmd/arxdbd"],
        cwd=GO_DIR, check=True,
    )
    return DAEMON_BIN


def main() -> None:
    build_daemon()

    with TemporaryDirectory() as tmp:
        data_dir = Path(tmp) / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        socket_path = Path("/tmp/arxdb-demo.sock")
        if socket_path.exists():
            socket_path.unlink()

        log_file = open(data_dir / "daemon.log", "wb")
        proc = subprocess.Popen(
            [str(DAEMON_BIN), "--data-dir", str(data_dir),
             "--socket", str(socket_path)],
            stdout=log_file, stderr=subprocess.STDOUT,
        )

        # Wait for the socket.
        deadline = time.time() + 10.0
        while time.time() < deadline and not socket_path.exists():
            time.sleep(0.05)
        if not socket_path.exists():
            raise RuntimeError("daemon did not start; see daemon.log")

        try:
            # The drop-in swap: backend="grpc". root/priv/pub are ignored —
            # the daemon owns the engine and keypair.
            store = create_storage(
                Path(tmp), b"", b"", backend="grpc", socket_path=str(socket_path),
            )

            priv, pub = generate_keypair()
            a = Node(claim="x > 0", domain="math")
            b = Node(claim="x + 1 > 0", domain="math")

            # Ground A as a definition, then derive B from it.
            verify_and_commit(store, pub, [], a, "assume", EdgeType.DEFINITION)
            r = verify_and_commit(
                store, pub, [a], b, "add 1", EdgeType.DEDUCTION,
            )
            print(f"[grpc] verdict={r.verification.verdict.value} "
                  f"kappa={r.verification.kappa.value}")

            q = reachable(b.node_id(), store)
            print(f"[grpc] B established={q.established}")

        finally:
            proc.terminate()
            proc.wait(timeout=5.0)
            log_file.close()


if __name__ == "__main__":
    main()
