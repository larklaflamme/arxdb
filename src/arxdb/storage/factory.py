"""Storage factory — backend selection (SQLite in-process vs Go over gRPC).

The single mechanism by which the drop-in claim is tested: the same test suite
runs against either backend, and the only thing that changes is the `backend=`
argument.

    from arxdb.storage.factory import create_storage

    # In-process SQLite (Phase 1 prototype)
    store = create_storage(root, priv, pub, backend="sqlite")

    # Go daemon over gRPC (Phase 6)
    store = create_storage(root, priv, pub, backend="grpc", socket_path="/tmp/arxdb.sock")

For the gRPC backend, `root`/`priv`/`pub` are ignored (the daemon owns the
storage engine and keypair); only `socket_path` matters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from .storage import Storage
from .grpc_client import GrpcStorage

Backend = Literal["sqlite", "grpc"]

DEFAULT_SOCKET = "/tmp/arxdb.sock"


def create_storage(
    root_dir: Path,
    priv_key: bytes,
    pub_key: bytes,
    backend: Backend = "sqlite",
    socket_path: str | None = None,
) -> Storage | GrpcStorage:
    """Create a Storage implementation for the given backend.

    `backend="sqlite"` returns the in-process SQLite `Storage` (Phase 1).
    `backend="grpc"` returns a `GrpcStorage` client delegating to a running
    `arxdbd` daemon over a UNIX socket (Phase 6).
    """
    if backend == "sqlite":
        return Storage(root_dir, priv_key, pub_key)
    if backend == "grpc":
        return GrpcStorage(socket_path or DEFAULT_SOCKET)
    raise ValueError(f"unknown backend: {backend!r}")
