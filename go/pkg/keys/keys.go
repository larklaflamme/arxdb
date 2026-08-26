// Package keys implements Ed25519 keypairs, signing, and verification.
//
// Each agent holds an Ed25519 keypair. The append log is signed so that every
// entry is attributable to the agent that produced it.
//
// The private key is the 32-byte seed (Ed25519's canonical private form),
// matching the Python reference (cryptography's private_bytes_raw()).
package keys

import (
	"crypto/ed25519"
	"crypto/rand"
	"fmt"
)

// Key sizes.
const (
	PublicKeySize  = 32
	PrivateKeySize = 32 // the seed
	SignatureSize  = 64
)

// GenerateKeypair returns (private_seed, public_key) as raw Ed25519 bytes.
func GenerateKeypair() (priv []byte, pub []byte, err error) {
	pub, fullPriv, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		return nil, nil, err
	}
	// fullPriv is 64 bytes (seed || pub); return the 32-byte seed.
	return fullPriv[:PrivateKeySize], pub, nil
}

// Sign signs message with the 32-byte seed, returning the 64-byte signature.
func Sign(priv []byte, message []byte) ([]byte, error) {
	if len(priv) != PrivateKeySize {
		return nil, fmt.Errorf("private key must be %d bytes, got %d", PrivateKeySize, len(priv))
	}
	key := ed25519.NewKeyFromSeed(priv)
	return ed25519.Sign(key, message), nil
}

// Verify reports whether sig is a valid signature over message by pub.
func Verify(pub []byte, message []byte, sig []byte) bool {
	if len(pub) != PublicKeySize || len(sig) != SignatureSize {
		return false
	}
	return ed25519.Verify(ed25519.PublicKey(pub), message, sig)
}
