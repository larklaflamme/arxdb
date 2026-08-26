"""Tests for hashing.py — BLAKE3 multihash and the Hash type."""

from __future__ import annotations

from arxdb.storage.hashing import (
    HASH_SIZE,
    Hash,
    from_hex,
    hash_bytes,
    hash_hex,
    is_valid_hash,
)


def test_hash_size():
    """A Hash is exactly 34 bytes (multihash prefix + 32-byte digest)."""
    h = hash_bytes(b"hello")
    assert len(h) == HASH_SIZE


def test_multihash_prefix():
    """The first two bytes are the BLAKE3 code (0x1e) and length (0x20)."""
    h = hash_bytes(b"hello")
    assert h[0] == 0x1E
    assert h[1] == 0x20


def test_deterministic():
    """Same input → same hash."""
    assert hash_bytes(b"hello") == hash_bytes(b"hello")


def test_distinct_inputs():
    """Different input → different hash."""
    assert hash_bytes(b"hello") != hash_bytes(b"world")


def test_hex_roundtrip():
    """hex → from_hex is the identity."""
    h = hash_bytes(b"hello")
    assert from_hex(h.hex()) == h


def test_hash_hex_matches():
    """hash_hex returns the hex of hash_bytes."""
    assert hash_hex(b"hello") == hash_bytes(b"hello").hex()


def test_is_valid_hash():
    """is_valid_hash accepts well-formed hashes and rejects malformed ones."""
    assert is_valid_hash(hash_bytes(b"hello"))
    assert not is_valid_hash(b"")
    assert not is_valid_hash(b"\x00" * 34)
