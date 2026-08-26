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
    # Proof is content-addressed and retrievable by its own hash.
    assert s.objects.get(hash_bytes(b"proof-bytes")) == b"proof-bytes"


def test_atomic_on_failure(tmp_root, keypair, monkeypatch):
    """A graph-step failure must leave no edge and no log entry."""
    priv, pub = keypair
    s = Storage(tmp_root, priv, pub)
    a, c = _h(b"a"), _h(b"c")

    def boom(*args, **kwargs):
        raise RuntimeError("injected graph failure")

    monkeypatch.setattr(s.graph, "register_edge", boom)
    try:
        s.commit_edge_tx([a], c, b"edge-data")
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected commit_edge_tx to raise")
    # The object blob is orphaned (harmless), but graph + log are clean.
    assert s.objects.get(hash_bytes(b"edge-data")) is not None
    assert s.graph.get_connectivity(hash_bytes(b"edge-data")) is None
    assert len(s.log) == 0


def test_atomic_on_log_failure(tmp_root, keypair, monkeypatch):
    """A log-step failure must roll back the graph and leave no log entry."""
    priv, pub = keypair
    s = Storage(tmp_root, priv, pub)
    a, c = _h(b"a"), _h(b"c")

    def boom(*args, **kwargs):
        raise RuntimeError("injected log failure")

    monkeypatch.setattr(s.log, "append", boom)
    try:
        s.commit_edge_tx([a], c, b"edge-data")
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected commit_edge_tx to raise")
    # Graph rolled back, no log entry.
    assert s.graph.get_connectivity(hash_bytes(b"edge-data")) is None
    assert len(s.log) == 0


def test_crash_recovery(tmp_root, keypair):
    """100 commits, close, reopen → all objects, connections, log entries match."""
    priv, pub = keypair
    s = Storage(tmp_root, priv, pub)
    edge_hashes = []
    for i in range(100):
        a, c = _h(f"a{i}".encode()), _h(f"c{i}".encode())
        eh, _ = s.commit_edge_tx([a], c, f"edge-{i}".encode())
        edge_hashes.append(eh)
    root_before = s.log.root_hash()
    s.close()
    # Reopen from disk (simulated crash recovery).
    s2 = Storage(tmp_root, priv, pub)
    assert len(s2.log) == 100
    assert s2.log.root_hash() == root_before
    for i, eh in enumerate(edge_hashes):
        assert s2.objects.get(eh) == f"edge-{i}".encode()
        premises, conclusion = s2.graph.get_connectivity(eh)
        assert premises == [_h(f"a{i}".encode())]
        assert conclusion == _h(f"c{i}".encode())
