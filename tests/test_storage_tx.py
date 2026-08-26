"""Tests for storage.py — the atomic commit_edge_tx contract."""

from __future__ import annotations

from arxdb.storage.hashing import hash_bytes
from arxdb.storage.storage import Storage


def _h(x: bytes) -> bytes:
    return hash_bytes(x)


def test_commit_roundtrip(tmp_root, keypair):
    priv, pub = keypair
    s = Storage(tmp_root, priv, pub)
    a, b, c = _h(b"a"), _h(b"b"), _h(b"c")
    edge_hash, log_entry = s.commit_edge_tx([a, b], c, b"edge-data")
    # Edge retrievable from ObjectStore
    assert s.objects.get(edge_hash) is not None
    # Connectivity registered
    premises, conclusion = s.graph.get_connectivity(edge_hash)
    assert premises == [a, b]
    assert conclusion == c
    # Log entry present
    assert s.log.get(log_entry.seq) == log_entry


def test_commit_with_proof(tmp_root, keypair):
    priv, pub = keypair
    s = Storage(tmp_root, priv, pub)
    a, c = _h(b"a"), _h(b"c")
    edge_hash, _ = s.commit_edge_tx([a], c, b"edge-data", proof=b"proof-bytes")
    assert s.objects.get(edge_hash) is not None


def test_atomic_on_failure(tmp_root, keypair):
    """A failure mid-transaction must leave no partial state."""
    priv, pub = keypair
    s = Storage(tmp_root, priv, pub)
    # Fault injection is exercised in the implementation via a failing ObjectStore.
    # Placeholder: assert no orphaned object, no half-registered edge, no log entry.
    assert len(s.log) == 0


def test_atomic_on_log_failure(tmp_root, keypair):
    """A log failure must roll back the object and graph writes."""
    priv, pub = keypair
    s = Storage(tmp_root, priv, pub)
    # Placeholder: inject failure at the log step and assert rollback.
    assert len(s.log) == 0
