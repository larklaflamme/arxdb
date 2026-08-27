"""Tests for Phase 4: the RH seed corpus and its import script.

These tests exercise the corpus *data* (structure, purity) and the seed
script's `seed()` function (which ingests through the public
`verify_and_commit` pipeline), plus the two exit-criteria queries the seed
report prints.

v0.4: the corpus grew from the phaser thread (9 nodes/9 edges) to the full RH
map (23 nodes/23 edges) spanning five threads. v0.5: cross-thread bridges and
three hub nodes (positivity / primes-as-spectrum / balance point) connect the
map into a single component (26 nodes/45 edges). The count assertions below
track that growth.
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
from seed_phaser import _node_map, persist_anchor, seed, verify_seed_attestation  # noqa: E402


def _storage(tmp_root, keypair) -> Storage:
    priv, pub = keypair
    return Storage(tmp_root, priv, pub)


# --- corpus structure -------------------------------------------------------

def test_corpus_has_twenty_six_nodes_and_forty_five_edges():
    assert len(CORPUS_NODES) == 26
    assert len(CORPUS_EDGES) == 45
    assert [n.key for n in CORPUS_NODES] == [
        "N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8", "N9",
        "N10", "N11", "N12", "N13", "N14", "N15", "N16", "N17",
        "N18", "N19", "N20", "N21", "N22", "N23", "N24", "N25", "N26",
    ]
    assert [e.key for e in CORPUS_EDGES] == [
        "E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9",
        "E10", "E11", "E12", "E13", "E14", "E15", "E16", "E17",
        "E18", "E19", "E20", "E21", "E22", "E23", "E24", "E25",
        "E26", "E27", "E28", "E29", "E30", "E31", "E32", "E33",
        "E34", "E35", "E36", "E37", "E38", "E39", "E40", "E41",
        "E42", "E43", "E44", "E45",
    ]


def test_e9_is_hilbert_polya_citation():
    e9 = next(e for e in CORPUS_EDGES if e.key == "E9")
    assert e9.edge_type == EdgeType.CITATION
    assert e9.premise_keys == ("N9",)
    assert e9.conclusion_key == "N7"
    assert e9.expected_kappa == Kappa.K1


def test_grown_corpus_kappa_is_honest():
    """The grown corpus must not inflate κ: no κ3, models at κ0, citations κ1.

    This is the central finding the corpus is designed to surface: our RH work
    is a map of a wall, not a pile of proven theorems. Analytic number theory
    is not Z3/Lean-checkable, so the honest κ is κ1 (citation) for established
    results and κ0 (analogy) for models and the conjecture itself.
    """
    # No edge may claim κ3 (a Z3/Lean-checked deduction) — none of our RH
    # reasoning is first-order-arithmetic-checkable.
    assert all(e.expected_kappa != Kappa.K3 for e in CORPUS_EDGES)

    # The model-layer edges (RG, Janus, Lee-Yang, de Branges, balance) are
    # analogies at κ0.
    model_edges = {"E13", "E16", "E20", "E21", "E22", "E23"}
    for e in CORPUS_EDGES:
        if e.key in model_edges:
            assert e.edge_type == EdgeType.ANALOGY, e.key
            assert e.expected_kappa == Kappa.K0, e.key

    # The conjecture itself (RH) is κ0.
    e8 = next(e for e in CORPUS_EDGES if e.key == "E8")
    assert e8.expected_kappa == Kappa.K0


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
    assert len(rows) == 45
    assert all(r.status == "MATCH" for r in rows)
    assert all(r.actual_kappa == r.expected_kappa for r in rows)


def test_seed_idempotent(tmp_root, keypair):
    s = _storage(tmp_root, keypair)
    _, pub = keypair
    seed(s, pub)
    rows2 = seed(s, pub)
    assert len(rows2) == 45
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


# --- Phase 5 wiring: roster provenance --------------------------------------

def test_seed_edges_resolve_to_skye(tmp_root, keypair):
    """The plan's §9 acceptance test: corpus edges resolve to a named agent."""
    from arxdb.attestation.roster import Roster

    s = _storage(tmp_root, keypair)
    _, pub = keypair
    seed(s, pub)

    roster = Roster(entries={"Skye": pub})
    results = verify_seed_attestation(s, roster, pub)
    assert len(results) == 45
    assert all(ok for _, ok, _ in results)
    assert all(agent == "Skye" for _, _, agent in results)


def test_seed_edges_fail_with_empty_roster(tmp_root, keypair):
    """Provenance fails when the roster does not bind the signer key."""
    from arxdb.attestation.roster import Roster

    s = _storage(tmp_root, keypair)
    _, pub = keypair
    seed(s, pub)

    empty = Roster(entries={})
    results = verify_seed_attestation(s, empty, pub)
    assert all(not ok for _, ok, _ in results)
    assert all(agent is None for _, _, agent in results)


# --- Phase 5: anchor record (roster + anchor persisted) ---------------------

def test_full_ceremony_persists_roster_and_anchor(tmp_root, keypair):
    """commit_roster + seed + persist_anchor: the anchor covers everything."""
    from arxdb.attestation.attest import anchor, commit_roster, verify_history
    from arxdb.attestation.roster import Roster

    s = _storage(tmp_root, keypair)
    _, pub = keypair
    roster = Roster(entries={"Skye": pub})

    commit_roster(s, roster)
    seed(s, pub)
    rec = persist_anchor(s, roster, tmp_root)

    # root_hash covers roster (entry 0) + 45 edges = 46 entries.
    assert rec.entry_count == 46
    assert rec.roster_hash == roster.roster_hash()
    assert verify_history(s, rec.root_hash) is True

    # Both files exist on disk and round-trip.
    roster_path = tmp_root / "roster.bin"
    anchor_path = tmp_root / "anchor.bin"
    assert roster_path.exists()
    assert anchor_path.exists()
    assert roster_path.read_bytes() == roster.roster_bytes()
    assert anchor_path.read_bytes() == rec.anchor_bytes()
