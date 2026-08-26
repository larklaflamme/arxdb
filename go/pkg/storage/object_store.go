// Package storage implements the ArxDB storage engine on Pebble.
//
// ObjectStore is content-addressed put/get over a sharded filesystem, matching
// the Python reference (src/arxdb/storage/object_store.py) byte-for-byte in
// its on-disk layout: blobs live under objects/xx/... where xx is the first
// two hex chars of the hash (2-char shard). Writes are atomic via temp-file +
// os.Rename.
package storage

import (
	"os"
	"path/filepath"

	"github.com/larklaflamme/arxdb/go/pkg/hashing"
)

// ObjectStore is a content-addressed, sharded filesystem blob store.
type ObjectStore struct {
	root string
}

// NewObjectStore opens (creating if needed) an object store rooted at root.
func NewObjectStore(root string) (*ObjectStore, error) {
	if err := os.MkdirAll(root, 0o755); err != nil {
		return nil, err
	}
	return &ObjectStore{root: root}, nil
}

// shardPath returns the on-disk path for a hash: objects/xx/<full-hex>.
func (o *ObjectStore) shardPath(h hashing.Hash) string {
	hexstr := h.Hex()
	return filepath.Join(o.root, hexstr[:2], hexstr)
}

// Put stores data and returns its content hash. Idempotent: re-putting an
// existing blob is a no-op.
func (o *ObjectStore) Put(data []byte) (hashing.Hash, error) {
	h := hashing.HashBytes(data)
	path := o.shardPath(h)
	if _, err := os.Stat(path); err == nil {
		return h, nil // already present
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return h, err
	}
	// Atomic write: temp file + rename.
	tmp, err := os.CreateTemp(filepath.Dir(path), ".tmp-*")
	if err != nil {
		return h, err
	}
	tmpName := tmp.Name()
	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		os.Remove(tmpName)
		return h, err
	}
	if err := tmp.Close(); err != nil {
		os.Remove(tmpName)
		return h, err
	}
	if err := os.Rename(tmpName, path); err != nil {
		os.Remove(tmpName)
		return h, err
	}
	return h, nil
}

// Get returns the blob for h, or nil if absent.
func (o *ObjectStore) Get(h hashing.Hash) ([]byte, error) {
	data, err := os.ReadFile(o.shardPath(h))
	if os.IsNotExist(err) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return data, nil
}

// Has reports whether the blob for h is present.
func (o *ObjectStore) Has(h hashing.Hash) bool {
	_, err := os.Stat(o.shardPath(h))
	return err == nil
}
