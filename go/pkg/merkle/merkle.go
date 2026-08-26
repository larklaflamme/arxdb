// Package merkle implements the RFC 6962 Merkle tree with domain separation.
//
// Domain separation prevents the second-preimage attack: leaf nodes are hashed
// with a 0x00 prefix, internal nodes with 0x01, and the empty tree has a fixed
// sentinel root hashed with 0x02. This must produce byte-identical output to
// the Python reference (src/arxdb/storage/merkle.py).
package merkle

import (
	"fmt"

	"github.com/larklaflamme/arxdb/go/pkg/hashing"
)

// leafNode returns BLAKE3(0x00 || leaf).
func leafNode(leaf hashing.Hash) hashing.Hash {
	data := make([]byte, 0, 1+hashing.HashSize)
	data = append(data, 0x00)
	data = append(data, leaf[:]...)
	return hashing.HashBytes(data)
}

// internalNode returns BLAKE3(0x01 || left || right).
func internalNode(left, right hashing.Hash) hashing.Hash {
	data := make([]byte, 0, 1+2*hashing.HashSize)
	data = append(data, 0x01)
	data = append(data, left[:]...)
	data = append(data, right[:]...)
	return hashing.HashBytes(data)
}

// emptyRoot returns the sentinel root BLAKE3(0x02).
func emptyRoot() hashing.Hash {
	return hashing.HashBytes([]byte{0x02})
}

// RootHash returns the Merkle root of leafHashes (sentinel for empty).
func RootHash(leafHashes []hashing.Hash) hashing.Hash {
	if len(leafHashes) == 0 {
		return emptyRoot()
	}
	level := make([]hashing.Hash, len(leafHashes))
	for i, h := range leafHashes {
		level[i] = leafNode(h)
	}
	for len(level) > 1 {
		next := make([]hashing.Hash, 0, (len(level)+1)/2)
		for i := 0; i < len(level); i += 2 {
			left := level[i]
			right := left // duplicate last when odd
			if i+1 < len(level) {
				right = level[i+1]
			}
			next = append(next, internalNode(left, right))
		}
		level = next
	}
	return level[0]
}

// InclusionProof is a Merkle inclusion proof for a single leaf.
type InclusionProof struct {
	LeafHash hashing.Hash
	Index    int
	Path     []hashing.Hash // sibling hashes, bottom-up
}

// InclusionProof builds the inclusion proof for the leaf at index.
func BuildInclusionProof(leafHashes []hashing.Hash, index int) (InclusionProof, error) {
	if len(leafHashes) == 0 {
		return InclusionProof{}, fmt.Errorf("cannot build an inclusion proof for an empty tree")
	}
	if index < 0 || index >= len(leafHashes) {
		return InclusionProof{}, fmt.Errorf("leaf index %d out of range [0, %d)", index, len(leafHashes))
	}
	level := make([]hashing.Hash, len(leafHashes))
	for i, h := range leafHashes {
		level[i] = leafNode(h)
	}
	path := make([]hashing.Hash, 0)
	idx := index
	for len(level) > 1 {
		siblingIdx := idx + 1
		if idx%2 == 0 {
			if siblingIdx >= len(level) {
				siblingIdx = idx // duplicate last
			}
		} else {
			siblingIdx = idx - 1
		}
		path = append(path, level[siblingIdx])

		next := make([]hashing.Hash, 0, (len(level)+1)/2)
		for i := 0; i < len(level); i += 2 {
			left := level[i]
			right := left
			if i+1 < len(level) {
				right = level[i+1]
			}
			next = append(next, internalNode(left, right))
		}
		level = next
		idx /= 2
	}
	return InclusionProof{LeafHash: leafHashes[index], Index: index, Path: path}, nil
}

// VerifyInclusion reports whether proof.LeafHash is included in the tree with
// the given root.
func VerifyInclusion(proof InclusionProof, root hashing.Hash) bool {
	current := leafNode(proof.LeafHash)
	idx := proof.Index
	for _, sibling := range proof.Path {
		if idx%2 == 0 {
			current = internalNode(current, sibling)
		} else {
			current = internalNode(sibling, current)
		}
		idx /= 2
	}
	return current == root
}
