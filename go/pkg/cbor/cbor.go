// Package cbor implements canonical CBOR encoding/decoding (RFC 8949).
//
// Canonical encoding is the foundation of content-addressing: two structurally
// equal objects must produce byte-identical encodings. We use fxamacker/cbor/v2
// with CanonicalEncOptions (definite-length, sorted keys, shortest float form),
// which produces byte-identical output to the Python reference
// (cbor2.dumps(obj, canonical=True)).
package cbor

import (
	"github.com/fxamacker/cbor/v2"
)

var canonicalEncMode cbor.EncMode

func init() {
	var err error
	canonicalEncMode, err = cbor.CanonicalEncOptions().EncMode()
	if err != nil {
		panic(err)
	}
}

// Encode returns the canonical CBOR encoding of obj.
func Encode(obj any) ([]byte, error) {
	return canonicalEncMode.Marshal(obj)
}

// Decode decodes canonical CBOR into a Go value.
func Decode(data []byte) (any, error) {
	var v any
	err := cbor.Unmarshal(data, &v)
	return v, err
}

// DecodeInto decodes canonical CBOR into a typed target v (e.g. *[]any).
func DecodeInto(data []byte, v any) error {
	return cbor.Unmarshal(data, v)
}
