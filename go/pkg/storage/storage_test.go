package storage

import (
	"testing"

	"github.com/larklaflamme/arxdb/go/pkg/hashing"
	"github.com/larklaflamme/arxdb/go/pkg/keys"
	"github.com/larklaflamme/arxdb/go/pkg/merkle"
)

func testKeypair(t *testing.T) ([]byte, []byte) {
	t.Helper()
	priv, pub, err := keys.GenerateKeypair()
	if err != nil {
		t.Fatalf("GenerateKeypair: %v", err)
	}
	return priv, pub
}

func TestCommitEdgeTxRoundTrip(t *testing.T) {
	priv, pub := testKeypair(t)
	s, err := Open(t.TempDir(), priv, pub)
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	defer s.Close()

	premise := hashing.HashBytes([]byte("premise A"))
	conclusion := hashing.HashBytes([]byte("conclusion B"))
	edgeData := []byte("A -> B by rule R")
	proof := []byte("the proof")

	edgeHash, entry, err := s.CommitEdgeTx([]hashing.Hash{premise}, conclusion, edgeData, proof)
	if err != nil {
		t.Fatalf("CommitEdgeTx: %v", err)
	}

	// edgeHash must be the content hash of edgeData.
	if edgeHash != hashing.HashBytes(edgeData) {
		t.Fatalf("edgeHash mismatch")
	}

	// The entry must verify.
	if !s.Log().VerifyEntry(entry) {
		t.Fatalf("entry does not verify")
	}

	// The object store must have the edge and proof.
	if !s.Objects().Has(edgeHash) {
		t.Fatalf("object store missing edge blob")
	}
	if !s.Objects().Has(hashing.HashBytes(proof)) {
		t.Fatalf("object store missing proof blob")
	}

	// The graph must have the connectivity.
	premises, concl, ok, err := s.Graph().GetConnectivity(edgeHash)
	if err != nil || !ok {
		t.Fatalf("GetConnectivity: ok=%v err=%v", ok, err)
	}
	if concl != conclusion {
		t.Fatalf("conclusion mismatch")
	}
	if len(premises) != 1 || premises[0] != premise {
		t.Fatalf("premises mismatch: %v", premises)
	}

	// Incoming/outgoing edges.
	incoming, err := s.Graph().IncomingEdges(conclusion)
	if err != nil || len(incoming) != 1 || incoming[0] != edgeHash {
		t.Fatalf("IncomingEdges mismatch: %v err=%v", incoming, err)
	}
	outgoing, err := s.Graph().OutgoingEdges(premise)
	if err != nil || len(outgoing) != 1 || outgoing[0] != edgeHash {
		t.Fatalf("OutgoingEdges mismatch: %v err=%v", outgoing, err)
	}

	// Log length and root hash.
	n, err := s.Log().Len()
	if err != nil || n != 1 {
		t.Fatalf("Len: %v err=%v", n, err)
	}
	root, err := s.Log().RootHash()
	if err != nil {
		t.Fatalf("RootHash: %v", err)
	}
	// Root over a single entry hash must equal leafNode(entryHash).
	expected := hashing.HashBytes(append([]byte{0x00}, entry.EntryHash[:]...))
	if root != expected {
		t.Fatalf("root mismatch: got %s want %s", root.Hex(), expected.Hex())
	}

	// Inclusion proof verifies.
	proof2, err := s.Log().GetInclusionProof(0)
	if err != nil {
		t.Fatalf("GetInclusionProof: %v", err)
	}
	if !merkle.VerifyInclusion(proof2, root) {
		t.Fatalf("inclusion proof does not verify")
	}
}

func TestCommitEdgeTxHashChain(t *testing.T) {
	priv, pub := testKeypair(t)
	s, err := Open(t.TempDir(), priv, pub)
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	defer s.Close()

	var prevEntry *LogEntry
	for i := 0; i < 3; i++ {
		payload := []byte{byte('a' + i)}
		conclusion := hashing.HashBytes(payload)
		_, entry, err := s.CommitEdgeTx(nil, conclusion, payload, nil)
		if err != nil {
			t.Fatalf("CommitEdgeTx %d: %v", i, err)
		}
		if entry.Seq != int64(i) {
			t.Fatalf("seq mismatch: got %d want %d", entry.Seq, i)
		}
		if i == 0 {
			if entry.PrevLogHash != GenesisPrevHash {
				t.Fatalf("entry 0 prev hash should be genesis sentinel")
			}
		} else {
			if entry.PrevLogHash != prevEntry.EntryHash {
				t.Fatalf("entry %d prev hash mismatch", i)
			}
		}
		if !s.Log().VerifyEntry(entry) {
			t.Fatalf("entry %d does not verify", i)
		}
		prevEntry = entry
	}

	n, _ := s.Log().Len()
	if n != 3 {
		t.Fatalf("Len: got %d want 3", n)
	}
}

func TestCommitEdgeTxAtomicity(t *testing.T) {
	// The graph and log share one Pebble DB and commit in a single indexed
	// batch. The atomicity guarantee is: an uncommitted batch is invisible to
	// reads, and a discarded batch leaves zero partial state.
	priv, pub := testKeypair(t)
	s, err := Open(t.TempDir(), priv, pub)
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	defer s.Close()

	// Manually write a graph edge to an uncommitted batch.
	b := s.db.NewIndexedBatch()
	edge := hashing.HashBytes([]byte("uncommitted"))
	conclusion := hashing.HashBytes([]byte("c"))
	if err := s.graph.RegisterEdge(b, edge, nil, conclusion); err != nil {
		t.Fatalf("RegisterEdge: %v", err)
	}
	// Do NOT commit.

	// The graph (reading from the DB, not the batch) must not see it.
	_, _, ok, err := s.graph.GetConnectivity(edge)
	if err != nil {
		t.Fatalf("GetConnectivity: %v", err)
	}
	if ok {
		t.Fatalf("uncommitted edge is visible to reads")
	}

	// Discard the batch; still invisible.
	b.Close()
	_, _, ok, err = s.graph.GetConnectivity(edge)
	if err != nil {
		t.Fatalf("GetConnectivity after discard: %v", err)
	}
	if ok {
		t.Fatalf("discarded edge is visible to reads")
	}

	// The log is also untouched.
	n, _ := s.Log().Len()
	if n != 0 {
		t.Fatalf("log length changed by uncommitted batch: %d", n)
	}
}
