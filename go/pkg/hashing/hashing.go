// Package hashing implements the BLAKE3 multihash used by ArxDB.
//
// A Hash is a 34-byte multihash: 0x1e (BLAKE3 code) || 0x20 (32-byte length)
// || 32-byte BLAKE3 digest. The multihash prefix makes the hash algorithm
// self-describing, so a future algorithm migration does not break stored
// objects.
//
// This must produce byte-identical output to the Python reference
// (src/arxdb/storage/hashing.py) for the same input.
package hashing

import (
	"encoding/hex"
	"fmt"

	"github.com/zeebo/blake3"
)

// Multihash constants.
const (
	BLAKE3Code = 0x1E
	BLAKE3Len  = 0x20
	HashSize   = 34 // 1 (code) + 1 (len) + 32 (digest)
)

// Hash is a 34-byte BLAKE3 multihash.
type Hash [HashSize]byte

// HashBytes returns the 34-byte BLAKE3 multihash of data.
func HashBytes(data []byte) Hash {
	digest := blake3.Sum256(data)
	var h Hash
	h[0] = BLAKE3Code
	h[1] = BLAKE3Len
	copy(h[2:], digest[:])
	return h
}

// HashHex returns the hex string of the multihash of data.
func HashHex(data []byte) string {
	h := HashBytes(data)
	return hex.EncodeToString(h[:])
}

// FromHex reconstructs a Hash from its hex string.
func FromHex(hexstr string) (Hash, error) {
	var h Hash
	raw, err := hex.DecodeString(hexstr)
	if err != nil {
		return h, err
	}
	if len(raw) != HashSize {
		return h, fmt.Errorf("Hash must be %d bytes, got %d", HashSize, len(raw))
	}
	copy(h[:], raw)
	return h, nil
}

// IsValidHash reports whether b is a well-formed 34-byte BLAKE3 multihash.
func IsValidHash(b []byte) bool {
	return len(b) == HashSize && b[0] == BLAKE3Code && b[1] == BLAKE3Len
}

// Hex returns the hex string of the hash.
func (h Hash) Hex() string {
	return hex.EncodeToString(h[:])
}

// Bytes returns the hash as a byte slice.
func (h Hash) Bytes() []byte {
	return h[:]
}
