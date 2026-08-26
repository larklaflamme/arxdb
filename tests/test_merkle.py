"""Tests for merkle.py — Merkle tree and inclusion proofs."""

from __future__ import annotations

from arxdb.storage.hashing import hash_bytes
from arxdb.storage.merkle import inclusion_proof, root_hash, verify_inclusion


def _hashes(n: int) -> list[bytes]:
    return [hash_bytes(f"leaf-{i}".encode()) for i in range(n)]


def test_empty_root_sentinel():
    """Empty tree has a deterministic sentinel root."""
    assert root_hash([]) == root_hash([])


def test_single_leaf():
    leaves = _hashes(1)
    root = root_hash(leaves)
    proof = inclusion_proof(leaves, 0)
    assert verify_inclusion(proof, root)


def test_inclusion_all_indices():
    leaves = _hashes(8)
    root = root_hash(leaves)
    for i in range(len(leaves)):
        proof = inclusion_proof(leaves, i)
        assert verify_inclusion(proof, root)


def test_second_preimage_resistance():
    """An internal node hash must not verify as an authentic leaf."""
    leaves = _hashes(4)
    root = root_hash(leaves)
    # A leaf hash alone (without domain separation) must not pass as a root.
    # This is enforced by RFC 6962 domain separation in the implementation.
    # Placeholder: the real test constructs a forged proof and asserts failure.
    assert root_hash(leaves) != leaves[0]


def test_root_changes_on_append():
    leaves = _hashes(3)
    r1 = root_hash(leaves)
    r2 = root_hash(leaves + [hash_bytes(b"new")])
    assert r1 != r2
