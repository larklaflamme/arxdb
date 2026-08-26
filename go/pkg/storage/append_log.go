package storage

import (
	"encoding/binary"
	"fmt"
	"math"
	"time"

	"github.com/cockroachdb/pebble"
	"github.com/larklaflamme/arxdb/go/pkg/cbor"
	"github.com/larklaflamme/arxdb/go/pkg/hashing"
	"github.com/larklaflamme/arxdb/go/pkg/keys"
	"github.com/larklaflamme/arxdb/go/pkg/merkle"
)

// GenesisPrevHash is the all-zero sentinel committed to by entry 0 (not a
// valid multihash, but exactly 34 bytes so it round-trips through the Hash
// length check). Matches Python's GENESIS_PREV_HASH.
var GenesisPrevHash = hashing.Hash{} // 34 zero bytes

// LogEntry is a single signed append-log entry.
type LogEntry struct {
	Seq          int64
	TimestampNs  int64
	SignerPubkey []byte
	EntryHash    hashing.Hash
	PrevLogHash  hashing.Hash
	Signature    []byte
	Payload      []byte
}

// AppendLog is a signed, append-only log over Pebble.
//
// Key layout:
//
//	'l' + seq(8)  -> canonical CBOR of the full entry (7-element array)
//	'h' + seq(8)  -> entry_hash(34)   (denormalized for cheap Merkle/prev-hash)
//	'm' + "log_len" -> seq(8)         (the count of entries)
type AppendLog struct {
	db      *pebble.DB
	privKey []byte
	pubKey  []byte
}

// NewAppendLog wraps an open Pebble DB with the signing keypair.
func NewAppendLog(db *pebble.DB, privKey, pubKey []byte) *AppendLog {
	return &AppendLog{db: db, privKey: privKey, pubKey: pubKey}
}

// --- key constructors ---

func entryKey(seq int64) []byte {
	k := make([]byte, 1+8)
	k[0] = 'l'
	binary.BigEndian.PutUint64(k[1:], uint64(seq))
	return k
}

func entryHashKey(seq int64) []byte {
	k := make([]byte, 1+8)
	k[0] = 'h'
	binary.BigEndian.PutUint64(k[1:], uint64(seq))
	return k
}

var logLenKey = []byte{'m', 'l', 'o', 'g', '_', 'l', 'e', 'n'}

// signatureMessage returns the exact bytes signed for an entry: canonical CBOR
// of [seq, timestamp_ns, signer_pubkey, entry_hash, prev_log_hash]. This must
// match Python's _signature_message byte-for-byte.
func signatureMessage(seq, ts int64, pubKey []byte, entryHash, prevHash hashing.Hash) ([]byte, error) {
	return cbor.Encode([]any{seq, ts, pubKey, entryHash[:], prevHash[:]})
}

// encodeEntry serializes a LogEntry as canonical CBOR of a 7-element array.
func encodeEntry(e *LogEntry) ([]byte, error) {
	return cbor.Encode([]any{
		e.Seq, e.TimestampNs, e.SignerPubkey,
		e.EntryHash[:], e.PrevLogHash[:], e.Signature, e.Payload,
	})
}

// decodeEntry reconstructs a LogEntry from its canonical CBOR form.
func decodeEntry(data []byte) (*LogEntry, error) {
	var arr []any
	if err := cbor.DecodeInto(data, &arr); err != nil {
		return nil, err
	}
	if len(arr) != 7 {
		return nil, fmt.Errorf("log entry: expected 7 fields, got %d", len(arr))
	}
	seq, err := toInt64(arr[0])
	if err != nil {
		return nil, fmt.Errorf("log entry: field 0: %w", err)
	}
	ts, err := toInt64(arr[1])
	if err != nil {
		return nil, fmt.Errorf("log entry: field 1: %w", err)
	}
	pub, ok := arr[2].([]byte)
	if !ok {
		return nil, fmt.Errorf("log entry: field 2 not bytes")
	}
	eh, err := toHash(arr[3])
	if err != nil {
		return nil, err
	}
	ph, err := toHash(arr[4])
	if err != nil {
		return nil, err
	}
	sig, ok := arr[5].([]byte)
	if !ok {
		return nil, fmt.Errorf("log entry: field 5 not bytes")
	}
	payload, ok := arr[6].([]byte)
	if !ok {
		return nil, fmt.Errorf("log entry: field 6 not bytes")
	}
	return &LogEntry{
		Seq: seq, TimestampNs: ts, SignerPubkey: pub,
		EntryHash: eh, PrevLogHash: ph, Signature: sig, Payload: payload,
	}, nil
}

// toInt64 converts a decoded CBOR integer to int64. The fxamacker/cbor
// library decodes positive CBOR integers into uint64 when the target is
// interface{}, so both int64 and uint64 must be accepted.
func toInt64(v any) (int64, error) {
	switch x := v.(type) {
	case int64:
		return x, nil
	case uint64:
		if x > math.MaxInt64 {
			return 0, fmt.Errorf("integer overflow: %d", x)
		}
		return int64(x), nil
	default:
		return 0, fmt.Errorf("not an integer: %T", v)
	}
}

// toHash converts a decoded CBOR byte string to a hashing.Hash.
func toHash(v any) (hashing.Hash, error) {
	var h hashing.Hash
	b, ok := v.([]byte)
	if !ok {
		return h, fmt.Errorf("expected bytes, got %T", v)
	}
	if len(b) != hashing.HashSize {
		return h, fmt.Errorf("hash must be %d bytes, got %d", hashing.HashSize, len(b))
	}
	copy(h[:], b)
	return h, nil
}

// --- internal batch helpers (read-your-writes via indexed batch) ---

// lenInBatch returns the current entry count as seen by the batch.
func (a *AppendLog) lenInBatch(b *pebble.Batch) (int64, error) {
	val, closer, err := b.Get(logLenKey)
	if err == pebble.ErrNotFound {
		return 0, nil
	}
	if err != nil {
		return 0, err
	}
	defer closer.Close()
	return int64(binary.BigEndian.Uint64(val)), nil
}

// prevHashInBatch returns the previous entry's hash, or the genesis sentinel.
func (a *AppendLog) prevHashInBatch(b *pebble.Batch, seq int64) (hashing.Hash, error) {
	if seq == 0 {
		return GenesisPrevHash, nil
	}
	val, closer, err := b.Get(entryHashKey(seq - 1))
	if err != nil {
		return hashing.Hash{}, err
	}
	defer closer.Close()
	var h hashing.Hash
	copy(h[:], val)
	return h, nil
}

// appendInBatch writes a new entry to the batch (does not commit).
func (a *AppendLog) appendInBatch(b *pebble.Batch, entry []byte) (*LogEntry, error) {
	seq, err := a.lenInBatch(b)
	if err != nil {
		return nil, err
	}
	ts := time.Now().UnixNano()
	entryHash := hashing.HashBytes(entry)
	prevHash, err := a.prevHashInBatch(b, seq)
	if err != nil {
		return nil, err
	}
	msg, err := signatureMessage(seq, ts, a.pubKey, entryHash, prevHash)
	if err != nil {
		return nil, err
	}
	sig, err := keys.Sign(a.privKey, msg)
	if err != nil {
		return nil, err
	}
	le := &LogEntry{
		Seq: seq, TimestampNs: ts, SignerPubkey: a.pubKey,
		EntryHash: entryHash, PrevLogHash: prevHash, Signature: sig, Payload: entry,
	}
	enc, err := encodeEntry(le)
	if err != nil {
		return nil, err
	}
	if err := b.Set(entryKey(seq), enc, nil); err != nil {
		return nil, err
	}
	if err := b.Set(entryHashKey(seq), entryHash[:], nil); err != nil {
		return nil, err
	}
	var lenBuf [8]byte
	binary.BigEndian.PutUint64(lenBuf[:], uint64(seq+1))
	if err := b.Set(logLenKey, lenBuf[:], nil); err != nil {
		return nil, err
	}
	return le, nil
}

// --- public API ---

// Append appends an entry in its own transaction and returns the LogEntry.
func (a *AppendLog) Append(entry []byte) (*LogEntry, error) {
	b := a.db.NewIndexedBatch()
	defer b.Close()
	le, err := a.appendInBatch(b, entry)
	if err != nil {
		return nil, err
	}
	if err := b.Commit(nil); err != nil {
		return nil, err
	}
	return le, nil
}

// Get returns the entry at seq, or nil if absent.
func (a *AppendLog) Get(seq int64) (*LogEntry, error) {
	val, closer, err := a.db.Get(entryKey(seq))
	if err == pebble.ErrNotFound {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	defer closer.Close()
	return decodeEntry(val)
}

// Len returns the number of entries.
func (a *AppendLog) Len() (int64, error) {
	val, closer, err := a.db.Get(logLenKey)
	if err == pebble.ErrNotFound {
		return 0, nil
	}
	if err != nil {
		return 0, err
	}
	defer closer.Close()
	return int64(binary.BigEndian.Uint64(val)), nil
}

// entryHashes returns all entry hashes in seq order.
func (a *AppendLog) entryHashes() ([]hashing.Hash, error) {
	n, err := a.Len()
	if err != nil {
		return nil, err
	}
	out := make([]hashing.Hash, 0, n)
	for seq := int64(0); seq < n; seq++ {
		val, closer, err := a.db.Get(entryHashKey(seq))
		if err != nil {
			return nil, err
		}
		var h hashing.Hash
		copy(h[:], val)
		closer.Close()
		out = append(out, h)
	}
	return out, nil
}

// RootHash returns the Merkle root over all entry hashes.
func (a *AppendLog) RootHash() (hashing.Hash, error) {
	hashes, err := a.entryHashes()
	if err != nil {
		return hashing.Hash{}, err
	}
	return merkle.RootHash(hashes), nil
}

// GetInclusionProof returns the Merkle inclusion proof for the entry at seq.
func (a *AppendLog) GetInclusionProof(seq int64) (merkle.InclusionProof, error) {
	hashes, err := a.entryHashes()
	if err != nil {
		return merkle.InclusionProof{}, err
	}
	if seq < 0 || seq >= int64(len(hashes)) {
		return merkle.InclusionProof{}, fmt.Errorf("seq %d out of range [0, %d)", seq, len(hashes))
	}
	return merkle.BuildInclusionProof(hashes, int(seq))
}

// VerifyEntry verifies an entry's signature and payload integrity.
func (a *AppendLog) VerifyEntry(e *LogEntry) bool {
	if hashing.HashBytes(e.Payload) != e.EntryHash {
		return false
	}
	msg, err := signatureMessage(e.Seq, e.TimestampNs, e.SignerPubkey, e.EntryHash, e.PrevLogHash)
	if err != nil {
		return false
	}
	return keys.Verify(e.SignerPubkey, msg, e.Signature)
}
