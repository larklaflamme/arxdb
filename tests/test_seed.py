"""Tests for Phase 4: the phaser-thread seed corpus and its import script.

These tests exercise the corpus *data* (structure, purity) and the seed
script's `seed()` function (which ingests through the public
`verify_and_commit` pipeline), plus the two exit-criteria queries the seed
report prints.
"""

from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

from arxdb.query import path_discovery, reachable
from arxdb.seed.corpus import CORPUS_EDGES, CORPUS_NODES
from arxdb.storage.storage import Storage
from arxdb.verification.schema import EdgeType, Kappa

# The seed script lives in scripts/ (not a package); import it directly.
_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from seed_phaser import _node_map, seed  # noqa: E402


def _storage(tmp_root, keypair) -> Storage:
    priv, pub = keypair
    return Storage(tmp_root, priv, pub)


# --- corpus structure -------------------------------------------------------


def test_corpus_has_nine_nodes_and_edges():
    assert len(CORPUS_NODES) == 9
    assert len(CORPUS_EDGES) == 9
    assert [n.key for n in CORPUS_NODES] == [
        "N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8", "N9",
    ]
    assert [e.key for e in CORPUS_EDGES] == [
        "E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9",
    ]


def test_e9_is_hilbert_polya_citation():
    e9 = CORPUS_EDGES[-1]
    assert e9.key == "E9"
    assert e9.edge_type == EdgeType.CITATION
    assert e9.premise_keys == ("N9",)
    assert e9.conclusion_key == "N7"
    assert e9.expected_kappa == Kappa.K1


def test_corpus_is_pure_data():
    """corpus.py imports only dataclass + schema enums (no storage/verifier)."""
    import arxdb.seed.corpus as corpus_mod

    tree = ast.parse(inspect.getsource(corpus_mod))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")
    assert modules <= {"__future__", "dataclasses", "arxdb.verification.schema"}


# --- seed ingestion ---------------------------------------------------------


def test_seed_all_edges_match(tmp_root, keypair):
    s = _storage(tmp_root, keypair)
    _, pub = keypair
    rows = seed(s, pub)
    assert len(rows) == 9
    assert all(r.status == "MATCH" for r in rows)
    assert all(r.actual_kappa == r.expected_kappa for r in rows)


def test_seed_idempotent(tmp_root, keypair):
    s = _storage(tmp_root, keypair)
    _, pub = keypair
    seed(s, pub)
    rows2 = seed(s, pub)
    assert len(rows2) == 9
    assert all(r.status == "SKIP" for r in rows2)


# --- exit-criteria queries --------------------------------------------------


def test_query_a_phaser_differs_from_berry_keating(tmp_root, keypair):
    s = _storage(tmp_root, keypair)
    _, pub = keypair
    seed(s, pub)
    n5 = _node_map()["N5"].node_id()
    qa = reachable(n5, s)
    assert qa.established is True
    assert qa.kappa == Kappa.K1
    assert qa.depth == 1


def test_conjecture_isolation_rh_not_established_at_k1(tmp_root, keypair):
    s = _storage(tmp_root, keypair)
    _, pub = keypair
    seed(s, pub)
    n7 = _node_map()["N7"].node_id()
    ci = reachable(n7, s, min_kappa=Kappa.K1)
    assert ci.established is False
    # RH *is* derived, but only at K0 (the analogy) — below the threshold.
    assert ci.kappa == Kappa.K0


def test_query_b_names_the_wall(tmp_root, keypair):
    """path_discovery(N7, min_kappa=K1) reports unreachable and names N9."""
    s = _storage(tmp_root, keypair)
    _, pub = keypair
    seed(s, pub)
    nm = _node_map()
    n7 = nm["N7"].node_id()
    n9 = nm["N9"].node_id()

    qb = path_discovery(n7, s, min_kappa=Kappa.K1)
    assert qb.reachable is False
    # The actual derivation exists at K0 (the analogy), below the threshold.
    assert qb.kappa == Kappa.K0

    # N9 (the Hilbert-Polya operator) must appear in the frontier.
    mentioned: set = set()
    for me in qb.missing_edges:
        mentioned.add(me.conclusion)
        mentioned.update(me.blocking_nodes)
    assert n9 in mentioned
