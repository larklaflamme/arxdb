"""Tests for attest.py — the three guarantees + tamper detection."""

from __future__ import annotations

from dataclasses import replace

from arxdb.attestation.attest import (
    anchor,
    commit_roster,
    verify_edge_attestation,
    verify_history,
)
from arxdb.attestation.roster import Roster
from arxdb.storage.hashing import hash_bytes
from arxdb.storage.storage import Storage
from arxdb.verification.commit import verify_and_commit
from arxdb.verification.schema import Edge, EdgeType, Kappa, Node, Verdict


def _setup(tmp_root, keypair):
    priv, pub = keypair
    storage = Storage(tmp_root, priv, pub)
    roster = Roster(entries={"Skye": pub})
    return storage, roster, pub


def _commit_citation(storage, pub, rule="test rule", proof=None):
    premise = Node(claim="premise claim", domain="test")
    conclusion = Node(claim="conclusion claim", domain="test")
    result = verify_and_commit(
        storage,
        signer_pubkey=pub,
        premises=[premise],
        conclusion=conclusion,
        rule=rule,
        edge_type=EdgeType.CITATION,
        proof_bytes=proof,
    )
    assert not result.rejected
    return result.edge, result.edge_hash


# --- provenance + integrity + binding on a genuine edge ---

def test_genuine_edge_attests(tmp_root, keypair):
    storage, roster, pub = _setup(tmp_root, keypair)
    edge, _ = _commit_citation(storage, pub)
    res = verify_edge_attestation(edge, storage, roster)
    assert res.signer_agent_id == "Skye"
    assert res.signature_valid is True
    assert res.ok is True


def test_unknown_signer_fails_provenance(tmp_root, keypair):
    storage, roster, pub = _setup(tmp_root, keypair)
    edge, _ = _commit_citation(storage, pub)
    empty_roster = Roster(entries={})
    res = verify_edge_attestation(edge, storage, empty_roster)
    assert res.signer_agent_id is None
    assert res.ok is False


# --- integrity: tampering ---

def test_tampered_edge_fails_integrity(tmp_root, keypair):
    storage, roster, pub = _setup(tmp_root, keypair)
    edge, _ = _commit_citation(storage, pub, rule="original")
    # Alter the edge -> different content address -> no matching log entry.
    tampered = replace(edge, rule="tampered")
    res = verify_edge_attestation(tampered, storage, roster)
    assert res.signature_valid is False
    assert res.ok is False


def test_tampered_log_payload_fails_integrity(tmp_root, keypair):
    storage, roster, pub = _setup(tmp_root, keypair)
    edge, _ = _commit_citation(storage, pub, rule="original")
    # Tamper the stored payload without updating entry_hash: the signature
    # check (payload hash) must fail.
    storage._conn.execute(
        "UPDATE log SET payload = ? WHERE seq = 0", (b"tampered payload",)
    )
    res = verify_edge_attestation(edge, storage, roster)
    assert res.signature_valid is False
    assert res.ok is False


# --- binding: proof ---

def test_proof_bound_and_intact(tmp_root, keypair):
    storage, roster, pub = _setup(tmp_root, keypair)
    edge, _ = _commit_citation(storage, pub, proof=b"the proof")
    res = verify_edge_attestation(edge, storage, roster)
    assert res.proof_bound is True
    assert res.proof_intact is True
    assert res.ok is True


def test_no_proof_vacuously_bound(tmp_root, keypair):
    storage, roster, pub = _setup(tmp_root, keypair)
    edge, _ = _commit_citation(storage, pub)  # no proof
    res = verify_edge_attestation(edge, storage, roster)
    assert res.proof_bound is True
    assert res.proof_intact is True
    assert res.ok is True


def test_missing_proof_fails_binding(tmp_root, keypair):
    storage, roster, pub = _setup(tmp_root, keypair)
    # An edge whose proof_hash points at a blob that was never stored.
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
    res = verify_edge_attestation(ghost, storage, roster)
    assert res.proof_bound is False
    assert res.proof_intact is False
    assert res.ok is False


# --- verify_history ---

def test_verify_history_untampered(tmp_root, keypair):
    storage, roster, pub = _setup(tmp_root, keypair)
    _commit_citation(storage, pub, rule="a")
    _commit_citation(storage, pub, rule="b")
    trusted_root = storage.log.root_hash()
    assert verify_history(storage, trusted_root) is True


def test_verify_history_detects_payload_tamper(tmp_root, keypair):
    storage, roster, pub = _setup(tmp_root, keypair)
    _commit_citation(storage, pub, rule="a")
    _commit_citation(storage, pub, rule="b")
    trusted_root = storage.log.root_hash()
    assert verify_history(storage, trusted_root) is True
    storage._conn.execute(
        "UPDATE log SET payload = ? WHERE seq = 0", (b"tampered",)
    )
    assert verify_history(storage, trusted_root) is False


def test_verify_history_detects_broken_chain(tmp_root, keypair):
    storage, roster, pub = _setup(tmp_root, keypair)
    _commit_citation(storage, pub, rule="a")
    _commit_citation(storage, pub, rule="b")
    trusted_root = storage.log.root_hash()
    assert verify_history(storage, trusted_root) is True
    # Break the chain: entry 1 no longer links to entry 0.
    storage._conn.execute(
        "UPDATE log SET prev_log_hash = ? WHERE seq = 1", (b"\x00" * 34,)
    )
    assert verify_history(storage, trusted_root) is False


def test_verify_history_wrong_root(tmp_root, keypair):
    storage, roster, pub = _setup(tmp_root, keypair)
    _commit_citation(storage, pub, rule="a")
    wrong_root = hash_bytes(b"not the real root")
    assert verify_history(storage, wrong_root) is False


# --- anchor ---

def test_anchor_record(tmp_root, keypair):
    storage, roster, pub = _setup(tmp_root, keypair)
    _commit_citation(storage, pub, rule="a")
    rec = anchor(storage, roster)
    assert rec.root_hash == storage.log.root_hash()
    assert rec.entry_count == len(storage.log)
    assert rec.roster_hash == roster.roster_hash()
    # The anchor is itself content-addressable (committable to a chain).
    assert rec.anchor_hash() == hash_bytes(rec.anchor_bytes())


# --- commit_roster (genesis ceremony) ---

def test_commit_roster_genesis_entry(tmp_root, keypair):
    storage, roster, pub = _setup(tmp_root, keypair)
    entry = commit_roster(storage, roster)
    assert entry is not None
    assert entry.seq == 0
    assert entry.entry_hash == roster.roster_hash()
    assert len(storage.log) == 1


def test_commit_roster_idempotent(tmp_root, keypair):
    storage, roster, pub = _setup(tmp_root, keypair)
    e1 = commit_roster(storage, roster)
    e2 = commit_roster(storage, roster)
    assert e1 is not None and e2 is not None
    assert e1.seq == e2.seq == 0
    assert len(storage.log) == 1  # not re-appended


def test_commit_roster_returns_none_for_nonempty_nonroster(tmp_root, keypair):
    storage, roster, pub = _setup(tmp_root, keypair)
    _commit_citation(storage, pub)  # log now has a non-roster entry 0
    assert commit_roster(storage, roster) is None


def test_anchor_covers_roster(tmp_root, keypair):
    storage, roster, pub = _setup(tmp_root, keypair)
    commit_roster(storage, roster)
    _commit_citation(storage, pub, rule="a")
    rec = anchor(storage, roster)
    # root_hash covers roster (entry 0) + 1 edge = 2 entries.
    assert rec.entry_count == 2
    assert rec.roster_hash == roster.roster_hash()
    assert verify_history(storage, rec.root_hash) is True
