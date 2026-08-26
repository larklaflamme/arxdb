"""Tests for append_log.py — signed append-only log."""

from __future__ import annotations

from dataclasses import replace

from arxdb.storage.append_log import AppendLog
from arxdb.storage.merkle import root_hash, verify_inclusion


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


def test_empty_state(tmp_root, keypair):
    """Empty log: len 0, get(0) is None, root is the deterministic sentinel."""
    priv, pub = keypair
    log = AppendLog(tmp_root / "index.db", priv, pub)
    assert len(log) == 0
    assert log.get(0) is None
    assert log.root_hash() == root_hash([])


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


def test_signature_valid(tmp_root, keypair):
    """A freshly appended entry verifies against its own signature."""
    priv, pub = keypair
    log = AppendLog(tmp_root / "index.db", priv, pub)
    entry = log.append(b"data")
    assert log.verify_entry(entry) is True


def test_bad_signature_rejected(tmp_root, keypair):
    """A tampered signature must fail verification."""
    priv, pub = keypair
    log = AppendLog(tmp_root / "index.db", priv, pub)
    entry = log.append(b"data")
    bad_sig = bytearray(entry.signature)
    bad_sig[0] ^= 0x01
    tampered = replace(entry, signature=bytes(bad_sig))
    assert log.verify_entry(tampered) is False


def test_tampered_payload_rejected(tmp_root, keypair):
    """A tampered payload must fail verification (entry_hash mismatch)."""
    priv, pub = keypair
    log = AppendLog(tmp_root / "index.db", priv, pub)
    entry = log.append(b"data")
    tampered = replace(entry, payload=b"DATA")
    assert log.verify_entry(tampered) is False


def test_root_changes(tmp_root, keypair):
    """root_hash() changes after each append."""
    priv, pub = keypair
    log = AppendLog(tmp_root / "index.db", priv, pub)
    r0 = log.root_hash()
    log.append(b"a")
    r1 = log.root_hash()
    assert r0 != r1
    log.append(b"b")
    r2 = log.root_hash()
    assert r1 != r2


def test_root_and_inclusion(tmp_root, keypair):
    priv, pub = keypair
    log = AppendLog(tmp_root / "index.db", priv, pub)
    for i in range(5):
        log.append(f"entry-{i}".encode())
    root = log.root_hash()
    for seq in range(5):
        proof = log.get_inclusion_proof(seq)
        assert verify_inclusion(proof, root)
