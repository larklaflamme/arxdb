"""test_cross_language_audit.py — interoperability verification (PHASE6_PLAN.md §10).

The strongest proof that the process boundary is genuinely language-agnostic: an
edge is *signed by Go* (the daemon's Ed25519) and *verified by Python* (the
`cryptography` library). If the two runtimes disagreed on the signature format
or the canonical CBOR message, this test would fail.

The flow:
  1. A Python client commits an edge through the Go daemon (the daemon signs the
     log entry with its own keypair).
  2. Python retrieves the entry and verifies the Go-produced signature with
     Python's Ed25519 — the cross-language check.
  3. `verify_edge_attestation` (provenance + integrity + proof binding) and
     `verify_history` (whole-log integrity from a trusted root) both pass.

This is the plan's §12 "strengthen" scenario made concrete: Skye (Python) signs
an edge, the Go backend stores it, and a second Python client retrieves and
verifies it.
"""

from __future__ import annotations

import pytest

from arxdb.attestation.attest import verify_edge_attestation, verify_history
from arxdb.attestation.roster import Roster
from arxdb.storage.grpc_client import GrpcStorage
from arxdb.storage.hashing import hash_bytes
from arxdb.storage.keys import generate_keypair, verify as verify_signature
from arxdb.storage.serialization import canonical_encode
from arxdb.verification.commit import verify_and_commit
from arxdb.verification.schema import Edge, EdgeType, Kappa, Node, Verdict

from grpc_helpers import start_daemon, stop_daemon


@pytest.fixture
def grpc_store(tmp_path):
    data_dir = tmp_path / "daemon"
    proc, socket_path = start_daemon(data_dir)
    store = GrpcStorage(str(socket_path))
    yield store
    store.close()
    stop_daemon(proc)


def _signature_message(seq, timestamp_ns, signer_pubkey, entry_hash, prev_log_hash):
    """The exact bytes the daemon signs (mirrors append_log._signature_message)."""
    return canonical_encode(
        [seq, timestamp_ns, signer_pubkey, entry_hash, prev_log_hash]
    )


def test_cross_language_signature_and_attestation(grpc_store):
    """Go signs, Python verifies; the edge attests and the history verifies."""
    store = grpc_store
    priv, pub = generate_keypair()
    roster = Roster(entries={"Skye": pub})

    premise = Node(claim="x > 0", domain="math")
    conclusion = Node(claim="x + 1 > 0", domain="math")
    proof = b"the proof blob (content-addressed, bound to this edge)"

    # CITATION (not DEDUCTION) so the test does not depend on the Lean
    # checker, which is not installed (see SETUP.md §6).
    result = verify_and_commit(
        store,
        signer_pubkey=pub,
        premises=[premise],
        conclusion=conclusion,
        rule="test rule",
        edge_type=EdgeType.CITATION,
        proof_bytes=proof,
    )
    assert not result.rejected
    edge = result.edge
    edge_hash = result.edge_hash
    log_entry = result.log_entry

    # --- cross-language signature check ---
    # The log entry was signed by the Go daemon (its own keypair). Reconstruct
    # the signed message in Python and verify the signature with Python's
    # Ed25519. If Go and Python disagreed on the message bytes or the signature
    # format, this would fail.
    message = _signature_message(
        log_entry.seq,
        log_entry.timestamp_ns,
        log_entry.signer_pubkey,
        log_entry.entry_hash,
        log_entry.prev_log_hash,
    )
    assert verify_signature(log_entry.signer_pubkey, message, log_entry.signature)

    # --- retrievable + verifiable ---
    assert store.objects.get(edge_hash) == edge.edge_bytes()
    assert store.log.verify_entry(log_entry)

    # --- verify_edge_attestation: provenance + integrity + binding ---
    res = verify_edge_attestation(edge, store, roster)
    assert res.signer_agent_id == "Skye"
    assert res.signature_valid is True
    assert res.proof_bound is True
    assert res.proof_intact is True
    assert res.ok is True

    # --- verify_history: whole-log integrity from the trusted root ---
    trusted_root = store.log.root_hash()
    assert verify_history(store, trusted_root) is True


def test_cross_language_wrong_root_fails_history(grpc_store):
    """A wrong trusted root fails verify_history (tamper detection)."""
    store = grpc_store
    _, pub = generate_keypair()
    premise = Node(claim="p", domain="test")
    conclusion = Node(claim="c", domain="test")
    verify_and_commit(
        store, pub, [premise], conclusion, "r", EdgeType.CITATION
    )
    wrong_root = hash_bytes(b"not the real root")
    assert verify_history(store, wrong_root) is False


def test_cross_language_ghost_edge_fails_attestation(grpc_store):
    """An edge whose proof was never stored fails binding (tamper detection)."""
    store = grpc_store
    _, pub = generate_keypair()
    roster = Roster(entries={"Skye": pub})
    ghost = Edge(
        type=EdgeType.CITATION,
        premises=(),
        conclusion=hash_bytes(b"c"),
        rule="ghost",
        proof_hash=hash_bytes(b"nonexistent proof"),
        verdict=Verdict.PASS,
        kappa=Kappa.K1,
        signer_pubkey=pub,
    )
    res = verify_edge_attestation(ghost, store, roster)
    assert res.proof_bound is False
    assert res.proof_intact is False
    assert res.ok is False
