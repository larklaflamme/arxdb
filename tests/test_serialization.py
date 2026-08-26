"""Tests for serialization.py — canonical CBOR encode/decode."""

from __future__ import annotations

from arxdb.storage.hashing import hash_bytes
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


def test_set_order_independent():
    """Set element order must not affect the encoding."""
    assert canonical_encode({"x", "y", "z"}) == canonical_encode({"z", "x", "y"})


def test_set_roundtrip_as_list():
    """Sets encode as sorted lists and decode as lists."""
    s = {"x", "y", "z"}
    decoded = canonical_decode(canonical_encode(s))
    assert sorted(decoded) == sorted(s)


def test_tuple_encodes_as_array():
    """Tuples encode as definite-length arrays (identical to lists)."""
    assert canonical_encode((1, 2, 3)) == canonical_encode([1, 2, 3])


def test_hash_roundtrip():
    """Hash (bytes subclass) round-trips as a byte string."""
    h = hash_bytes(b"hello")
    assert canonical_decode(canonical_encode(h)) == h


def test_heterogeneous_set():
    """Sets with mixed element types sort deterministically without crashing."""
    assert canonical_encode({1, "a", b"b"}) == canonical_encode({"a", 1, b"b"})


def test_nested_set_in_dict():
    """Set sorting applies recursively inside containers."""
    assert canonical_encode({"s": {3, 1, 2}}) == canonical_encode({"s": {2, 3, 1}})
