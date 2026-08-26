"""Tests for merkle.py — Merkle tree and inclusion proofs."""

from __future__ import annotations

from arxdb.storage.hashing import hash_bytes
from arxdb.storage.merkle import (
    MerkleInclusionProof,
    inclusion_proof,
    root_hash,
    verify_inclusion,
)


def _hashes(n: int) -> list[bytes]:
    return [hash_bytes(f"leaf-{i}".encode()) for i in range(n)]


def test_empty_sentinel():
    """Empty tree root == BLAKE3(0x02 ‖ "")."""
    assert root_hash([]) == hash_bytes(b"\x02")


def test_single_leaf():
    """Single-leaf root == BLAKE3(0x00 ‖ leaf)."""
    leaf = _hashes(1)[0]
    assert root_hash([leaf]) == hash_bytes(b"\x00" + bytes(leaf))


def test_two_leaves():
    """Two-leaf root == BLAKE3(0x01 ‖ leaf_node(0) ‖ leaf_node(1))."""
    a, b = _hashes(2)
    left = hash_bytes(b"\x00" + bytes(a))
    right = hash_bytes(b"\x00" + bytes(b))
    assert root_hash([a, b]) == hash_bytes(b"\x01" + bytes(left) + bytes(right))


def test_odd_count():
    """Odd leaf count duplicates the last node."""
    leaves = _hashes(3)
    assert root_hash(leaves) == root_hash(leaves + [leaves[-1]])


def test_root_deterministic():
    leaves = _hashes(5)
    assert root_hash(leaves) == root_hash(leaves)


def test_root_changes_on_append():
    leaves = _hashes(3)
    assert root_hash(leaves) != root_hash(leaves + [hash_bytes(b"new")])


def test_inclusion_proof_valid():
    leaves = _hashes(8)
    root = root_hash(leaves)
    for i in range(len(leaves)):
        assert verify_inclusion(inclusion_proof(leaves, i), root)


def test_tamper_detected():
    leaves = _hashes(8)
    root = root_hash(leaves)
    proof = inclusion_proof(leaves, 3)
    tampered = MerkleInclusionProof(
        leaf_hash=hash_bytes(b"forged"), index=proof.index, path=proof.path
    )
    assert not verify_inclusion(tampered, root)


def test_second_preimage_resisted():
    """An internal node hash cannot be verified as an authentic leaf."""
    leaves = _hashes(2)
    root = root_hash(leaves)
    # Forge: claim the root itself is a single leaf with an empty path.
    forged = MerkleInclusionProof(leaf_hash=root, index=0, path=[])
    assert not verify_inclusion(forged, root)
