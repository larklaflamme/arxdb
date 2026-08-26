package storage

import (
	"encoding/binary"

	"github.com/cockroachdb/pebble"
	"github.com/larklaflamme/arxdb/go/pkg/hashing"
)

// GraphIndex stores structural node<->edge adjacency over Pebble.
//
// It stores *structural* connectivity only: which nodes exist, which edges
// connect which premises to which conclusion. No semantic traversal, no kappa,
// no proof correctness — that lives in the verification layer.
//
// Key layout (single-byte prefixes, fixed-width hash fields):
//
//	'n' + node(34)                    -> empty            (node exists)
//	'e' + edge(34)                    -> conclusion(34)   (edge -> conclusion)
//	'p' + edge(34) + pos(8)           -> premise(34)     (edge, position -> premise)
//	'c' + conclusion(34) + edge(34)   -> empty            (incoming index)
//	'o' + premise(34) + edge(34)      -> empty            (outgoing index)
type GraphIndex struct {
	db *pebble.DB
}

// NewGraphIndex wraps an open Pebble DB.
func NewGraphIndex(db *pebble.DB) *GraphIndex {
	return &GraphIndex{db: db}
}

// --- key constructors ---

func nodeKey(node hashing.Hash) []byte {
	k := make([]byte, 1+hashing.HashSize)
	k[0] = 'n'
	copy(k[1:], node[:])
	return k
}

func edgeKey(edge hashing.Hash) []byte {
	k := make([]byte, 1+hashing.HashSize)
	k[0] = 'e'
	copy(k[1:], edge[:])
	return k
}

func premiseKey(edge hashing.Hash, pos int) []byte {
	k := make([]byte, 1+hashing.HashSize+8)
	k[0] = 'p'
	copy(k[1:], edge[:])
	binary.BigEndian.PutUint64(k[1+hashing.HashSize:], uint64(pos))
	return k
}

func premisePrefix(edge hashing.Hash) []byte {
	k := make([]byte, 1+hashing.HashSize)
	k[0] = 'p'
	copy(k[1:], edge[:])
	return k
}

func incomingKey(conclusion, edge hashing.Hash) []byte {
	k := make([]byte, 1+2*hashing.HashSize)
	k[0] = 'c'
	copy(k[1:], conclusion[:])
	copy(k[1+hashing.HashSize:], edge[:])
	return k
}

func incomingPrefix(node hashing.Hash) []byte {
	k := make([]byte, 1+hashing.HashSize)
	k[0] = 'c'
	copy(k[1:], node[:])
	return k
}

func outgoingKey(premise, edge hashing.Hash) []byte {
	k := make([]byte, 1+2*hashing.HashSize)
	k[0] = 'o'
	copy(k[1:], premise[:])
	copy(k[1+hashing.HashSize:], edge[:])
	return k
}

func outgoingPrefix(node hashing.Hash) []byte {
	k := make([]byte, 1+hashing.HashSize)
	k[0] = 'o'
	copy(k[1:], node[:])
	return k
}

// --- writes (take a batch; the owner commits) ---

// RegisterNode records that node exists (idempotent).
func (g *GraphIndex) RegisterNode(b *pebble.Batch, node hashing.Hash) error {
	return b.Set(nodeKey(node), nil, nil)
}

// RegisterEdge records the edge and its endpoints (idempotent).
func (g *GraphIndex) RegisterEdge(b *pebble.Batch, edge hashing.Hash, premises []hashing.Hash, conclusion hashing.Hash) error {
	// Register endpoints so the graph stays self-consistent.
	if err := b.Set(nodeKey(conclusion), nil, nil); err != nil {
		return err
	}
	for _, p := range premises {
		if err := b.Set(nodeKey(p), nil, nil); err != nil {
			return err
		}
	}
	if err := b.Set(edgeKey(edge), conclusion[:], nil); err != nil {
		return err
	}
	for pos, p := range premises {
		if err := b.Set(premiseKey(edge, pos), p[:], nil); err != nil {
			return err
		}
	}
	// Secondary indexes for incoming/outgoing traversal.
	if err := b.Set(incomingKey(conclusion, edge), nil, nil); err != nil {
		return err
	}
	for _, p := range premises {
		if err := b.Set(outgoingKey(p, edge), nil, nil); err != nil {
			return err
		}
	}
	return nil
}

// --- reads ---

// IncomingEdges returns the edges whose conclusion is node, sorted by edge hash.
func (g *GraphIndex) IncomingEdges(node hashing.Hash) ([]hashing.Hash, error) {
	prefix := incomingPrefix(node)
	iter, err := g.db.NewIter(&pebble.IterOptions{LowerBound: prefix, UpperBound: prefixUpperBound(prefix)})
	if err != nil {
		return nil, err
	}
	defer iter.Close()
	var out []hashing.Hash
	for iter.First(); iter.Valid(); iter.Next() {
		key := iter.Key()
		// key = 'c' + node(34) + edge(34)
		var edge hashing.Hash
		copy(edge[:], key[1+hashing.HashSize:])
		out = append(out, edge)
	}
	return out, iter.Error()
}

// OutgoingEdges returns the edges where node is a premise, sorted by edge hash.
func (g *GraphIndex) OutgoingEdges(node hashing.Hash) ([]hashing.Hash, error) {
	prefix := outgoingPrefix(node)
	iter, err := g.db.NewIter(&pebble.IterOptions{LowerBound: prefix, UpperBound: prefixUpperBound(prefix)})
	if err != nil {
		return nil, err
	}
	defer iter.Close()
	var out []hashing.Hash
	for iter.First(); iter.Valid(); iter.Next() {
		key := iter.Key()
		var edge hashing.Hash
		copy(edge[:], key[1+hashing.HashSize:])
		out = append(out, edge)
	}
	return out, iter.Error()
}

// GetConnectivity returns (premises, conclusion, ok) for an edge.
func (g *GraphIndex) GetConnectivity(edge hashing.Hash) ([]hashing.Hash, hashing.Hash, bool, error) {
	var conclusion hashing.Hash
	val, closer, err := g.db.Get(edgeKey(edge))
	if err == pebble.ErrNotFound {
		return nil, conclusion, false, nil
	}
	if err != nil {
		return nil, conclusion, false, err
	}
	copy(conclusion[:], val)
	closer.Close()

	// Iterate premises in position order.
	prefix := premisePrefix(edge)
	iter, err := g.db.NewIter(&pebble.IterOptions{LowerBound: prefix, UpperBound: prefixUpperBound(prefix)})
	if err != nil {
		return nil, conclusion, false, err
	}
	defer iter.Close()
	var premises []hashing.Hash
	for iter.First(); iter.Valid(); iter.Next() {
		val := iter.Value()
		var p hashing.Hash
		copy(p[:], val)
		premises = append(premises, p)
	}
	if err := iter.Error(); err != nil {
		return nil, conclusion, false, err
	}
	return premises, conclusion, true, nil
}

// prefixUpperBound returns the smallest key greater than all keys with the
// given prefix (the prefix with its last byte incremented).
func prefixUpperBound(prefix []byte) []byte {
	ub := make([]byte, len(prefix))
	copy(ub, prefix)
	for i := len(ub) - 1; i >= 0; i-- {
		if ub[i] < 0xff {
			ub[i]++
			return ub[:i+1]
		}
	}
	return nil // prefix is all 0xff; no upper bound
}

// AllNodes returns every registered node hash, in Pebble iteration order
// (sorted by the 'n'-prefixed key, i.e. by node hash). Structural enumeration
// only — no semantic traversal.
func (g *GraphIndex) AllNodes() ([]hashing.Hash, error) {
	prefix := []byte{'n'}
	iter, err := g.db.NewIter(&pebble.IterOptions{LowerBound: prefix, UpperBound: prefixUpperBound(prefix)})
	if err != nil {
		return nil, err
	}
	defer iter.Close()
	var out []hashing.Hash
	for iter.First(); iter.Valid(); iter.Next() {
		key := iter.Key()
		var node hashing.Hash
		copy(node[:], key[1:])
		out = append(out, node)
	}
	return out, iter.Error()
}

// AllEdges returns every indexed edge hash, in Pebble iteration order (sorted
// by the 'e'-prefixed key, i.e. by edge hash). Structural enumeration only.
func (g *GraphIndex) AllEdges() ([]hashing.Hash, error) {
	prefix := []byte{'e'}
	iter, err := g.db.NewIter(&pebble.IterOptions{LowerBound: prefix, UpperBound: prefixUpperBound(prefix)})
	if err != nil {
		return nil, err
	}
	defer iter.Close()
	var out []hashing.Hash
	for iter.First(); iter.Valid(); iter.Next() {
		key := iter.Key()
		var edge hashing.Hash
		copy(edge[:], key[1:])
		out = append(out, edge)
	}
	return out, iter.Error()
}

// RegisterNodeTx registers a node in its own committed batch (standalone form
// for the gRPC service, where there is no surrounding transaction).
func (g *GraphIndex) RegisterNodeTx(node hashing.Hash) error {
	b := g.db.NewIndexedBatch()
	defer b.Close()
	if err := g.RegisterNode(b, node); err != nil {
		return err
	}
	return b.Commit(nil)
}

// RegisterEdgeTx registers an edge in its own committed batch (standalone form
// for the gRPC service).
func (g *GraphIndex) RegisterEdgeTx(edge hashing.Hash, premises []hashing.Hash, conclusion hashing.Hash) error {
	b := g.db.NewIndexedBatch()
	defer b.Close()
	if err := g.RegisterEdge(b, edge, premises, conclusion); err != nil {
		return err
	}
	return b.Commit(nil)
}
