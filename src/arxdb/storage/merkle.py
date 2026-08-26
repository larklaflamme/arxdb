"""Merkle — Merkle tree, root hash, and inclusion proofs (RFC 6962).

Domain separation prevents the second-preimage attack: leaf nodes are hashed
with a `0x00` prefix, internal nodes with `0x01`, and the empty tree has a
fixed sentinel root hashed with `0x02`.

Public API (Phase 1):
    root_hash(leaf_hashes: list[Hash]) -> Hash
    inclusion_proof(leaf_hashes: list[Hash], index: int) -> MerkleInclusionProof
    verify_inclusion(proof: MerkleInclusionProof, root: Hash) -> bool
"""

from __future__ import annotations

from dataclasses import dataclass

from .hashing import Hash, hash_bytes


@dataclass(frozen=True)
class MerkleInclusionProof:
    """A Merkle inclusion proof for a single leaf."""

    leaf_hash: Hash
    index: int
    path: list[Hash]  # sibling hashes, bottom-up


def _leaf_node(leaf: Hash) -> Hash:
    """Domain-separated leaf node hash: BLAKE3(0x00 ‖ leaf)."""
    return hash_bytes(b"\x00" + bytes(leaf))


def _internal_node(left: Hash, right: Hash) -> Hash:
    """Domain-separated internal node hash: BLAKE3(0x01 ‖ left ‖ right)."""
    return hash_bytes(b"\x01" + bytes(left) + bytes(right))


def _empty_root() -> Hash:
    """Sentinel root for the empty tree: BLAKE3(0x02 ‖ "")."""
    return hash_bytes(b"\x02")


def root_hash(leaf_hashes: list[Hash]) -> Hash:
    """Return the Merkle root of `leaf_hashes` (sentinel for empty)."""
    if not leaf_hashes:
        return _empty_root()
    level = [_leaf_node(h) for h in leaf_hashes]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else left  # duplicate last
            nxt.append(_internal_node(left, right))
        level = nxt
    return level[0]


def inclusion_proof(leaf_hashes: list[Hash], index: int) -> MerkleInclusionProof:
    """Build the inclusion proof for the leaf at `index`."""
    if not leaf_hashes:
        raise IndexError("cannot build an inclusion proof for an empty tree")
    if index < 0 or index >= len(leaf_hashes):
        raise IndexError(f"leaf index {index} out of range [0, {len(leaf_hashes)})")

    level = [_leaf_node(h) for h in leaf_hashes]
    path: list[Hash] = []
    idx = index
    while len(level) > 1:
        if idx % 2 == 0:
            sibling_idx = idx + 1
            if sibling_idx >= len(level):
                sibling_idx = idx  # duplicate last
        else:
            sibling_idx = idx - 1
        path.append(level[sibling_idx])

        nxt = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else left
            nxt.append(_internal_node(left, right))
        level = nxt
        idx //= 2

    return MerkleInclusionProof(leaf_hash=leaf_hashes[index], index=index, path=path)


def verify_inclusion(proof: MerkleInclusionProof, root: Hash) -> bool:
    """Verify that `proof.leaf_hash` is included in the tree with `root`."""
    current = _leaf_node(proof.leaf_hash)
    idx = proof.index
    for sibling in proof.path:
        if idx % 2 == 0:
            current = _internal_node(current, sibling)
        else:
            current = _internal_node(sibling, current)
        idx //= 2
    return current == root
