#!/usr/bin/env python3
"""arxdb_serve.py — run the ArxDB public HTTP API (Phase 7).

Usage:
    python scripts/arxdb_serve.py [--root PATH] [--host HOST] [--port PORT]
                                  [--backend sqlite|grpc] [--socket PATH]

Loads (or creates) the server keypair and roster under `--root`, builds the
Storage via the factory, and serves the JSON API. See PUBLIC_API.md for the
endpoint reference.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from arxdb.api.server import ArxDBApp, serve
from arxdb.attestation.roster import Roster
from arxdb.storage.factory import create_storage
from arxdb.storage.keys import generate_keypair

_KEYPAIR_FILE = "server_keypair.bin"
_ROSTER_FILE = "roster.bin"
_SERVER_AGENT = "arxdb-server"


def _load_or_create_keypair(root: Path) -> tuple[bytes, bytes]:
    path = root / _KEYPAIR_FILE
    if path.exists():
        data = path.read_bytes()
        if len(data) == 64:
            return data[:32], data[32:]
    priv, pub = generate_keypair()
    path.write_bytes(priv + pub)
    return priv, pub


def _load_or_create_roster(root: Path, pub: bytes) -> Roster:
    """Load the shared roster, ensuring this server's agent is bound.

    The roster is a shared trust anchor: the seed script binds "Skye" (corpus
    edges) and this server binds "arxdb-server" (API-committed edges). Load the
    existing roster and *merge* (never overwrite) so both identities survive
    regardless of whether the seed or the server ran first.
    """
    path = root / _ROSTER_FILE
    roster = Roster.from_bytes(path.read_bytes()) if path.exists() else Roster()
    if _SERVER_AGENT not in roster.entries:
        roster = Roster(entries={**roster.entries, _SERVER_AGENT: pub})
        path.write_bytes(roster.roster_bytes())
    return roster


def main() -> None:
    p = argparse.ArgumentParser(description="ArxDB public HTTP API")
    p.add_argument("--root", default="data", help="data directory (default: data)")
    p.add_argument("--host", default="127.0.0.1", help="bind host (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=8080, help="bind port (default: 8080)")
    p.add_argument("--backend", choices=["sqlite", "grpc"], default="sqlite")
    p.add_argument("--socket", default="/tmp/arxdb.sock", help="gRPC socket (grpc backend)")
    args = p.parse_args()

    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    priv, pub = _load_or_create_keypair(root)
    roster = _load_or_create_roster(root, pub)
    storage = create_storage(
        root, priv, pub, backend=args.backend, socket_path=args.socket
    )
    app = ArxDBApp(storage, roster, pub)
    serve(app, args.host, args.port)


if __name__ == "__main__":
    main()
