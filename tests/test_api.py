"""test_api.py — the Phase 7 public API application logic.

Tests `ArxDBApp` directly (no HTTP transport): the pure application layer
behind the public API. The HTTP transport itself is exercised end-to-end by
`examples/08-public-api/client.py`.

Covers the two queries, the reproduce-the-proof story, attestation, the
anchor, and trustless history verification — the Phase 7 exit criteria.
"""

from __future__ import annotations

import base64

import pytest

from arxdb.api.server import ApiError, ArxDBApp
from arxdb.attestation.roster import Roster
from arxdb.storage.keys import generate_keypair
from arxdb.storage.storage import Storage


@pytest.fixture
def app(tmp_path):
    priv, pub = generate_keypair()
    storage = Storage(tmp_path, priv, pub)
    roster = Roster(entries={"test-agent": pub})
    return ArxDBApp(storage, roster, pub)


def _commit_definition(app):
    return app.commit(
        {
            "premises": [],
            "conclusion": {"claim": "x > 0", "domain": "math"},
            "rule": "assumption",
            "edge_type": "definition",
        }
    )


def _commit_deduction(app):
    return app.commit(
        {
            "premises": [{"claim": "x > 0", "domain": "math"}],
            "conclusion": {"claim": "x + 1 > 0", "domain": "math"},
            "rule": "monotonicity of addition",
            "edge_type": "deduction",
        }
    )


def test_health_shape(app):
    # health is handled by the transport; the app has no health method, but
    # the version is importable and stable.
    from arxdb.api.server import __version__

    assert __version__ == "0.1.0"


def test_commit_definition_grounds_claim(app):
    result = _commit_definition(app)
    assert result["rejected"] is False
    assert result["verification"]["kappa"] == "K1"  # unlisted definition
    assert result["edge_hash"] is not None


def test_commit_deduction_earns_k3(app):
    _commit_definition(app)
    result = _commit_deduction(app)
    assert result["rejected"] is False
    assert result["verification"]["kappa"] == "K3"  # Z3 verified


def test_reachable_after_grounding(app):
    _commit_definition(app)
    _commit_deduction(app)
    r = app.query_reachable({"claim": "x + 1 > 0", "domain": "math"})
    assert r["established"] is True
    assert r["kappa"] == "K1"  # min(K1 premise, K3 edge)
    assert r["depth"] == 1


def test_path_discovery_reachable(app):
    _commit_definition(app)
    _commit_deduction(app)
    r = app.query_path({"claim": "x + 1 > 0", "domain": "math"})
    assert r["reachable"] is True
    assert r["missing_edges"] == []


def test_reproduce_the_proof(app):
    _commit_definition(app)
    deduction = _commit_deduction(app)
    r = app.reproduce({"edge_hash": deduction["edge_hash"]})
    assert r["verdict_match"] is True
    assert r["kappa_match"] is True
    assert r["attestation"]["ok"] is True
    assert r["reproduced"] is True
    # the resolved claims are human-readable
    assert r["conclusion"]["claim"] == "x + 1 > 0"
    assert r["premises"][0]["claim"] == "x > 0"


def test_reproduce_unknown_edge_404(app):
    with pytest.raises(ApiError) as exc:
        app.reproduce({"edge_hash": "00" * 34})
    assert exc.value.status == 404


def test_attest_named_agent(app):
    _commit_definition(app)
    deduction = _commit_deduction(app)
    r = app.attest({"edge_hash": deduction["edge_hash"]})
    assert r["signer_agent_id"] == "test-agent"
    assert r["ok"] is True


def test_anchor_and_verify_history(app):
    _commit_definition(app)
    _commit_deduction(app)
    anchor = app.anchor_record()
    assert anchor["entry_count"] == 2
    r = app.verify_history_endpoint({"root_hash": anchor["root_hash"]})
    assert r["valid"] is True


def test_verify_history_wrong_root(app):
    _commit_definition(app)
    r = app.verify_history_endpoint({"root_hash": "00" * 34})
    assert r["valid"] is False


def test_commit_citation_binds_proof(app):
    proof = b"Euclid, Elements, Book I."
    result = app.commit(
        {
            "premises": [],
            "conclusion": {"claim": "the whole is greater than the part", "domain": "math"},
            "rule": "cite",
            "edge_type": "citation",
            "proof": base64.b64encode(proof).decode(),
        }
    )
    assert result["rejected"] is False
    assert result["edge"]["proof_hash"] is not None
    # reproduce retrieves and re-binds the proof
    r = app.reproduce({"edge_hash": result["edge_hash"]})
    assert r["proof"] == base64.b64encode(proof).decode()
    assert r["attestation"]["proof_intact"] is True
    assert r["reproduced"] is True


def test_commit_rejects_bad_deduction(app):
    # "1 + 1 = 2" is not a Z3 expression over the declared variables -> veto.
    result = app.commit(
        {
            "premises": [{"claim": "x > 0", "domain": "math"}],
            "conclusion": {"claim": "1 + 1 = 2", "domain": "math"},
            "rule": "arithmetic",
            "edge_type": "deduction",
        }
    )
    assert result["rejected"] is True
    assert result["edge"] is None


def test_query_graph_returns_nodes_and_edges(app):
    _commit_definition(app)
    _commit_deduction(app)

    g = app.query_graph()

    # Two distinct claims: "x > 0" and "x + 1 > 0".
    claims = {n["claim"] for n in g["nodes"]}
    assert claims == {"x > 0", "x + 1 > 0"}

    # One definition edge + one deduction edge.
    assert len(g["edges"]) == 2

    # Every edge's conclusion resolves to a node in the graph.
    node_ids = {n["node_id"] for n in g["nodes"]}
    for e in g["edges"]:
        assert e["conclusion"] in node_ids
        assert e["kappa"] in {"K1", "K3"}
