"""Tests for serialization.py — canonical CBOR encode/decode."""

from __future__ import annotations

from arxdb.storage.serialization import canonical_decode, canonical_encode


def test_roundtrip_bytes():
    x = b"hello"
    assert canonical_decode(canonical_encode(x)) == x


def test_roundtrip_nested():
    x = {"a": [1, 2, 3], "b": {"c": b"bytes", "d": None}}
    assert canonical_decode(canonical_encode(x)) == x


def test_canonical_key_order():
    """Dict key order must not affect the encoding."""
    a = {"x": 1, "y": 2}
    b = {"y": 2, "x": 1}
    assert canonical_encode(a) == canonical_encode(b)


def test_structural_equality():
    """Structurally equal objects encode identically."""
    assert canonical_encode([1, 2, 3]) == canonical_encode([1, 2, 3])
    assert canonical_encode([1, 2, 3]) != canonical_encode([1, 2, 4])
