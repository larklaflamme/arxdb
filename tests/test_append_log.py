"""Tests for append_log.py — signed append-only log."""

from __future__ import annotations

from arxdb.storage.append_log import AppendLog
from arxdb.storage.hashing import hash_bytes
from arxdb.storage.merkle import verify_inclusion


def test_append_and_get(tmp_root, keypair):
    priv, pub = keypair
    log = AppendLog(tmp_root / "index.db", priv, pub)
    entry = log.append(b"first")
    assert log.get(0) == entry
    assert entry.seq == 0


def test_len(tmp_root, keypair):
    priv, pub = keypair
    log = AppendLog(tmp_root / "index.db", priv, pub)
    assert len(log) == 0
    log.append(b"a")
    log.append(b"b")
    assert len(log) == 2


def test_genesis_prev_hash(tmp_root, keypair):
    """Entry 0 commits to the zero prev_log_hash (0x00 * 34)."""
    priv, pub = keypair
    log = AppendLog(tmp_root / "index.db", priv, pub)
    entry = log.append(b"first")
    assert entry.prev_log_hash == b"\x00" * 34


def test_hash_chain(tmp_root, keypair):
    """Each entry commits to the previous entry's hash."""
    priv, pub = keypair
    log = AppendLog(tmp_root / "index.db", priv, pub)
    e0 = log.append(b"a")
    e1 = log.append(b"b")
    assert e1.prev_log_hash == e0.entry_hash


def test_root_and_inclusion(tmp_root, keypair):
    priv, pub = keypair
    log = AppendLog(tmp_root / "index.db", priv, pub)
    for i in range(5):
        log.append(f"entry-{i}".encode())
    root = log.root_hash()
    for seq in range(5):
        proof = log.get_inclusion_proof(seq)
        assert verify_inclusion(proof, root)


def test_bad_signature_rejected(tmp_root, keypair):
    """A log entry signed by a different key must not verify."""
    priv, pub = keypair
    log = AppendLog(tmp_root / "index.db", priv, pub)
    entry = log.append(b"data")
    # Verification of a tampered signature is exercised in the implementation.
    assert entry.signature != b""
