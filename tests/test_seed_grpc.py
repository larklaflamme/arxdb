"""test_seed_grpc.py — the seed corpus ingests through the gRPC backend.

The drop-in claim (PHASE6_PLAN.md §10) extended to the seed script: the same
`seed()` function that ingests the RH corpus into in-process SQLite must also
ingest it into a live Go/Pebble daemon over gRPC, producing the same 45 edges
with the same honest κ distribution.

This test starts a live `arxdbd` daemon (via grpc_helpers) and drives the seed
script's `seed()` against a `GrpcStorage` client, asserting the corpus lands
intact. It is the unit-level proof behind the docker-entrypoint.sh seed step.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from arxdb.storage.grpc_client import GrpcStorage
from arxdb.storage.keys import generate_keypair

from grpc_helpers import start_daemon, stop_daemon

# The seed script lives in scripts/ (not a package); import it directly.
_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from seed_phaser import seed  # noqa: E402


@pytest.fixture
def grpc(tmp_path):
    """A fresh daemon + GrpcStorage client, isolated per test."""
    data_dir = tmp_path / "daemon"
    proc, socket_path = start_daemon(data_dir)
    store = GrpcStorage(str(socket_path))
    yield store
    store.close()
    stop_daemon(proc)


def test_seed_ingests_forty_five_edges_over_grpc(grpc):
    """The full RH corpus lands in Pebble via gRPC with honest κ."""
    _, pub = generate_keypair()
    rows = seed(grpc, pub)

    assert len(rows) == 45
    # Every edge committed (no REJECTED), and its κ matched the corpus's
    # declared expectation.
    assert all(r.status == "MATCH" for r in rows)
    assert all(r.actual_kappa is not None for r in rows)

    # The honest κ distribution: 18 cited/established (K1), 27 model/conjecture (K0).
    k1 = sum(1 for r in rows if r.actual_kappa.value == "K1")
    k0 = sum(1 for r in rows if r.actual_kappa.value == "K0")
    assert k1 == 18
    assert k0 == 27

    # The graph index sees all 45 edges and their 26 nodes.
    assert len(grpc.graph.all_edges()) == 45
    assert len(grpc.graph.all_nodes()) == 26


def test_seed_is_idempotent_over_grpc(grpc):
    """Re-seeding a warm daemon skips every edge (no duplicates)."""
    _, pub = generate_keypair()
    first = seed(grpc, pub)
    second = seed(grpc, pub)

    assert all(r.status == "MATCH" for r in first)
    assert all(r.status == "SKIP" for r in second)
    # Still exactly 45 edges — no duplicates from the second pass.
    assert len(grpc.graph.all_edges()) == 45
