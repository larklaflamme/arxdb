"""Tests for object_store.py — content-addressed put/get."""

from __future__ import annotations

from arxdb.storage.hashing import hash_bytes
from arxdb.storage.object_store import ObjectStore


def test_put_get_roundtrip(tmp_root):
    store = ObjectStore(tmp_root / "objects")
    h = store.put(b"hello")
    assert store.get(h) == b"hello"


def test_put_idempotent(tmp_root):
    store = ObjectStore(tmp_root / "objects")
    h1 = store.put(b"hello")
    h2 = store.put(b"hello")
    assert h1 == h2


def test_get_missing(tmp_root):
    store = ObjectStore(tmp_root / "objects")
    assert store.get(hash_bytes(b"absent")) is None


def test_has(tmp_root):
    store = ObjectStore(tmp_root / "objects")
    h = store.put(b"hello")
    assert store.has(h)
    assert not store.has(hash_bytes(b"absent"))


def test_batch(tmp_root):
    store = ObjectStore(tmp_root / "objects")
    items = [b"a", b"b", b"c"]
    hashes = store.put_batch(items)
    assert store.get_batch(hashes) == items


def test_empty_batch(tmp_root):
    store = ObjectStore(tmp_root / "objects")
    assert store.put_batch([]) == []
    assert store.get_batch([]) == []


def test_persistence(tmp_root):
    store = ObjectStore(tmp_root / "objects")
    h = store.put(b"persistent")
    # reopen a fresh store over the same root
    store2 = ObjectStore(tmp_root / "objects")
    assert store2.get(h) == b"persistent"


def test_immutable(tmp_root):
    store = ObjectStore(tmp_root / "objects")
    h1 = store.put(b"original")
    h2 = store.put(b"different")
    assert h1 != h2
    assert store.get(h1) == b"original"
    assert store.get(h2) == b"different"


def test_sharding(tmp_root):
    store = ObjectStore(tmp_root / "objects")
    h = store.put(b"hello")
    hexstr = h.hex()
    expected = tmp_root / "objects" / hexstr[:2] / hexstr[2:]
    assert expected.exists()
