// Package parity verifies that the Go implementation produces byte-identical
// output to the Python reference for the three cryptographic primitives
// (canonical CBOR, BLAKE3 multihash, Ed25519) plus the Merkle root.
//
// The discipline (PHASE6_PLAN.md §4) is: freeze a test-vector corpus and
// assert byte-equality — do not trust the libraries. The corpus is generated
// by scripts/gen_parity_vectors.py (the Python reference) and committed as
// tests/parity_vectors.json.
//
// The corpus path is taken from the ARXDB_PARITY_CORPUS environment variable
// (set by tests/test_go_parity.py, which is the entry point).
package parity

import (
	"crypto/ed25519"
	"encoding/hex"
	"encoding/json"
	"os"
	"strconv"
	"testing"

	"github.com/larklaflamme/arxdb/go/pkg/cbor"
	"github.com/larklaflamme/arxdb/go/pkg/hashing"
	"github.com/larklaflamme/arxdb/go/pkg/keys"
	"github.com/larklaflamme/arxdb/go/pkg/merkle"
)

type corpus struct {
	Meta struct {
		SeedHex      string `json:"seed_hex"`
		PublicKeyHex string `json:"public_key_hex"`
	} `json:"meta"`
	CBOR    []cborVector    `json:"cbor"`
	Blake3  []blake3Vector  `json:"blake3"`
	Ed25519 []ed25519Vector `json:"ed25519"`
	Merkle  []merkleVector  `json:"merkle"`
}

type cborVector struct {
	Name     string `json:"name"`
	Input    any    `json:"input"`
	Expected string `json:"expected"`
}

type blake3Vector struct {
	Name     string `json:"name"`
	InputHex string `json:"input_hex"`
	Expected string `json:"expected"`
}

type ed25519Vector struct {
	Name       string `json:"name"`
	MessageHex string `json:"message_hex"`
	Expected   string `json:"expected"`
}

type merkleVector struct {
	Name      string   `json:"name"`
	LeafHexes []string `json:"leaf_hexes"`
	Expected  string   `json:"expected"`
}

// fromTagged reconstructs a Go value from the tagged JSON form produced by
// scripts/gen_parity_vectors.py. Tags:
//
//	{"$b": "hex"}     -> []byte
//	{"$i": "decimal"} -> int64
//	{"$f": number}    -> float64
//	plain object      -> map[string]any (string keys only, matches data model)
//	plain array       -> []any
//	string/bool/null  -> as-is
func fromTagged(v any) (any, error) {
	switch t := v.(type) {
	case map[string]any:
		if b, ok := t["$b"]; ok {
			s, _ := b.(string)
			return hex.DecodeString(s)
		}
		if i, ok := t["$i"]; ok {
			s, _ := i.(string)
			return strconv.ParseInt(s, 10, 64)
		}
		if f, ok := t["$f"]; ok {
			return f, nil // already float64 from JSON
		}
		m := make(map[string]any, len(t))
		for k, val := range t {
			rv, err := fromTagged(val)
			if err != nil {
				return nil, err
			}
			m[k] = rv
		}
		return m, nil
	case []any:
		out := make([]any, len(t))
		for i, val := range t {
			rv, err := fromTagged(val)
			if err != nil {
				return nil, err
			}
			out[i] = rv
		}
		return out, nil
	default:
		return v, nil
	}
}

func loadCorpus(t *testing.T) corpus {
	t.Helper()
	p := os.Getenv("ARXDB_PARITY_CORPUS")
	if p == "" {
		t.Fatal("ARXDB_PARITY_CORPUS not set; run via tests/test_go_parity.py")
	}
	raw, err := os.ReadFile(p)
	if err != nil {
		t.Fatalf("read corpus: %v", err)
	}
	var c corpus
	if err := json.Unmarshal(raw, &c); err != nil {
		t.Fatalf("parse corpus: %v", err)
	}
	return c
}

func TestParity(t *testing.T) {
	c := loadCorpus(t)

	// Public key derivation from the fixed seed.
	seed, err := hex.DecodeString(c.Meta.SeedHex)
	if err != nil {
		t.Fatalf("decode seed: %v", err)
	}
	priv := ed25519.NewKeyFromSeed(seed)
	pub := priv.Public().(ed25519.PublicKey)
	if got := hex.EncodeToString(pub); got != c.Meta.PublicKeyHex {
		t.Errorf("public key: got %s want %s", got, c.Meta.PublicKeyHex)
	}

	// Canonical CBOR.
	for _, v := range c.CBOR {
		val, err := fromTagged(v.Input)
		if err != nil {
			t.Errorf("CBOR %s: reconstruct input: %v", v.Name, err)
			continue
		}
		got, err := cbor.Encode(val)
		if err != nil {
			t.Errorf("CBOR %s: encode: %v", v.Name, err)
			continue
		}
		if hex.EncodeToString(got) != v.Expected {
			t.Errorf("CBOR %s:\n  got  %s\n  want %s", v.Name, hex.EncodeToString(got), v.Expected)
		}
	}

	// BLAKE3 multihash.
	for _, v := range c.Blake3 {
		data, err := hex.DecodeString(v.InputHex)
		if err != nil {
			t.Errorf("BLAKE3 %s: decode input: %v", v.Name, err)
			continue
		}
		got := hashing.HashBytes(data)
		if got.Hex() != v.Expected {
			t.Errorf("BLAKE3 %s:\n  got  %s\n  want %s", v.Name, got.Hex(), v.Expected)
		}
	}

	// Ed25519 signatures.
	for _, v := range c.Ed25519 {
		msg, err := hex.DecodeString(v.MessageHex)
		if err != nil {
			t.Errorf("Ed25519 %s: decode message: %v", v.Name, err)
			continue
		}
		sig, err := keys.Sign(seed, msg)
		if err != nil {
			t.Errorf("Ed25519 %s: sign: %v", v.Name, err)
			continue
		}
		if hex.EncodeToString(sig) != v.Expected {
			t.Errorf("Ed25519 %s:\n  got  %s\n  want %s", v.Name, hex.EncodeToString(sig), v.Expected)
		}
	}

	// Merkle roots.
	for _, v := range c.Merkle {
		leaves := make([]hashing.Hash, len(v.LeafHexes))
		for i, h := range v.LeafHexes {
			raw, err := hex.DecodeString(h)
			if err != nil {
				t.Errorf("Merkle %s: decode leaf %d: %v", v.Name, i, err)
				continue
			}
			if len(raw) != hashing.HashSize {
				t.Errorf("Merkle %s: leaf %d has %d bytes, want %d", v.Name, i, len(raw), hashing.HashSize)
				continue
			}
			copy(leaves[i][:], raw)
		}
		got := merkle.RootHash(leaves)
		if got.Hex() != v.Expected {
			t.Errorf("Merkle %s:\n  got  %s\n  want %s", v.Name, got.Hex(), v.Expected)
		}
	}
}
