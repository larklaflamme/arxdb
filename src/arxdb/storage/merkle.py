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

from .hashing import Hash


@dataclass(frozen=True)
class MerkleInclusionProof:
    """A Merkle inclusion proof for a single leaf."""

    leaf_hash: Hash
    index: int
    path: list[Hash]  # sibling hashes, bottom-up


def root_hash(leaf_hashes: list[Hash]) -> Hash:
    """Return the Merkle root of `leaf_hashes` (sentinel for empty)."""
    raise NotImplementedError


def inclusion_proof(leaf_hashes: list[Hash], index: int) -> MerkleInclusionProof:
    """Build the inclusion proof for the leaf at `index`."""
    raise NotImplementedError


def verify_inclusion(proof: MerkleInclusionProof, root: Hash) -> bool:
    """Verify that `proof.leaf_hash` is included in the tree with `root`."""
    raise NotImplementedError
