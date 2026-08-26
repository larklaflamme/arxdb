package storage

import (
	"os"
	"path/filepath"

	"github.com/cockroachdb/pebble"
	"github.com/larklaflamme/arxdb/go/pkg/hashing"
)

// Storage is the unified facade: ObjectStore + GraphIndex + AppendLog.
//
// The single most important method is CommitEdgeTx, which commits a reasoning
// edge *atomically* across the graph and log. Atomicity is real (not
// rollback-on-exception) because GraphIndex and AppendLog share one Pebble DB,
// and the graph mutation + log append happen inside a single indexed batch
// (the cross-process analogue of Python's BEGIN IMMEDIATE ... COMMIT). The
// ObjectStore write is idempotent, so an orphaned blob is harmless.
type Storage struct {
	root    string
	objects *ObjectStore
	db      *pebble.DB
	graph   *GraphIndex
	log     *AppendLog
}

// Open opens (creating if needed) a storage engine rooted at root.
func Open(root string, privKey, pubKey []byte) (*Storage, error) {
	if err := os.MkdirAll(root, 0o755); err != nil {
		return nil, err
	}
	objects, err := NewObjectStore(filepath.Join(root, "objects"))
	if err != nil {
		return nil, err
	}
	db, err := pebble.Open(filepath.Join(root, "pebble"), &pebble.Options{})
	if err != nil {
		return nil, err
	}
	return &Storage{
		root:    root,
		objects: objects,
		db:      db,
		graph:   NewGraphIndex(db),
		log:     NewAppendLog(db, privKey, pubKey),
	}, nil
}

// Close closes the underlying Pebble DB.
func (s *Storage) Close() error {
	return s.db.Close()
}

// Objects exposes the object store.
func (s *Storage) Objects() *ObjectStore { return s.objects }

// Graph exposes the graph index.
func (s *Storage) Graph() *GraphIndex { return s.graph }

// Log exposes the append log.
func (s *Storage) Log() *AppendLog { return s.log }

// CommitEdgeTx atomically commits a reasoning edge across all three
// sub-interfaces.
//
// Ordering (per the atomicity contract):
//  1. ObjectStore writes (idempotent, no rollback needed).
//  2. GraphIndex + AppendLog in one indexed batch (atomic).
func (s *Storage) CommitEdgeTx(
	premises []hashing.Hash,
	conclusion hashing.Hash,
	edgeData []byte,
	proof []byte,
) (hashing.Hash, *LogEntry, error) {
	edgeHash := hashing.HashBytes(edgeData)

	// 1. ObjectStore: content-addressed and idempotent, so an orphaned blob is
	//    harmless rather than corruption.
	if _, err := s.objects.Put(edgeData); err != nil {
		return edgeHash, nil, err
	}
	if proof != nil {
		if _, err := s.objects.Put(proof); err != nil {
			return edgeHash, nil, err
		}
	}

	// 2. Graph + log in a single indexed batch (atomic).
	b := s.db.NewIndexedBatch()
	defer b.Close()
	if err := s.graph.RegisterEdge(b, edgeHash, premises, conclusion); err != nil {
		return edgeHash, nil, err
	}
	entry, err := s.log.appendInBatch(b, edgeData)
	if err != nil {
		return edgeHash, nil, err
	}
	if err := b.Commit(nil); err != nil {
		return edgeHash, nil, err
	}
	return edgeHash, entry, nil
}
