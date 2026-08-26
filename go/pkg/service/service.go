// Package service implements the ArxDB StorageService gRPC server.
//
// It is a thin adapter: each RPC maps to a method on the storage engine
// (pkg/storage), translating between protobuf messages and the engine's
// native types. The daemon (cmd/arxdbd) owns the *storage.Storage instance
// and the signing keypair; this service holds a reference to it.
//
// Scope (Phase 6, Scope A): storage-only. No verification semantics, no
// AND-OR resolution, no kappa — just the dumb, fast, content-addressed graph.
package service

import (
	"context"
	"fmt"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"github.com/larklaflamme/arxdb/go/pkg/hashing"
	"github.com/larklaflamme/arxdb/go/pkg/storage"
	"github.com/larklaflamme/arxdb/go/proto/arxdbpb"
)

// Service adapts a *storage.Storage to the StorageService gRPC interface.
type Service struct {
	arxdbpb.UnimplementedStorageServiceServer
	store *storage.Storage
}

// New wraps an open storage engine.
func New(store *storage.Storage) *Service {
	return &Service{store: store}
}

// --- helpers ---

// toHash validates and converts a 34-byte slice to a hashing.Hash.
func toHash(b []byte) (hashing.Hash, error) {
	var h hashing.Hash
	if len(b) != hashing.HashSize {
		return h, fmt.Errorf("hash must be %d bytes, got %d", hashing.HashSize, len(b))
	}
	copy(h[:], b)
	return h, nil
}

func hashBytes(h hashing.Hash) []byte { return h[:] }

func logEntryToProto(e *storage.LogEntry) *arxdbpb.LogEntry {
	if e == nil {
		return nil
	}
	return &arxdbpb.LogEntry{
		Seq:          e.Seq,
		TimestampNs:  e.TimestampNs,
		SignerPubkey: e.SignerPubkey,
		EntryHash:    e.EntryHash[:],
		PrevLogHash:  e.PrevLogHash[:],
		Signature:    e.Signature,
		Payload:      e.Payload,
	}
}

// --- object store ---

func (s *Service) PutObject(ctx context.Context, req *arxdbpb.PutObjectRequest) (*arxdbpb.PutObjectResponse, error) {
	resp := &arxdbpb.PutObjectResponse{Hashes: make([][]byte, 0, len(req.Data))}
	for _, data := range req.Data {
		h, err := s.store.Objects().Put(data)
		if err != nil {
			return nil, status.Errorf(codes.Internal, "put object: %v", err)
		}
		resp.Hashes = append(resp.Hashes, h[:])
	}
	return resp, nil
}

func (s *Service) GetObject(ctx context.Context, req *arxdbpb.GetObjectRequest) (*arxdbpb.GetObjectResponse, error) {
	resp := &arxdbpb.GetObjectResponse{
		Data:  make([][]byte, 0, len(req.Hashes)),
		Found: make([]bool, 0, len(req.Hashes)),
	}
	for _, hb := range req.Hashes {
		h, err := toHash(hb)
		if err != nil {
			return nil, status.Errorf(codes.InvalidArgument, "%v", err)
		}
		data, err := s.store.Objects().Get(h)
		if err != nil {
			return nil, status.Errorf(codes.Internal, "get object: %v", err)
		}
		resp.Data = append(resp.Data, data)
		resp.Found = append(resp.Found, data != nil)
	}
	return resp, nil
}

func (s *Service) HasObject(ctx context.Context, req *arxdbpb.HasObjectRequest) (*arxdbpb.HasObjectResponse, error) {
	resp := &arxdbpb.HasObjectResponse{Found: make([]bool, 0, len(req.Hashes))}
	for _, hb := range req.Hashes {
		h, err := toHash(hb)
		if err != nil {
			return nil, status.Errorf(codes.InvalidArgument, "%v", err)
		}
		resp.Found = append(resp.Found, s.store.Objects().Has(h))
	}
	return resp, nil
}

// --- graph index ---

func (s *Service) RegisterNode(ctx context.Context, req *arxdbpb.RegisterNodeRequest) (*arxdbpb.RegisterNodeResponse, error) {
	node, err := toHash(req.NodeHash)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "%v", err)
	}
	if err := s.store.Graph().RegisterNodeTx(node); err != nil {
		return nil, status.Errorf(codes.Internal, "register node: %v", err)
	}
	return &arxdbpb.RegisterNodeResponse{}, nil
}

func (s *Service) RegisterEdge(ctx context.Context, req *arxdbpb.RegisterEdgeRequest) (*arxdbpb.RegisterEdgeResponse, error) {
	edge, err := toHash(req.EdgeHash)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "%v", err)
	}
	conclusion, err := toHash(req.Conclusion)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "%v", err)
	}
	premises := make([]hashing.Hash, 0, len(req.Premises))
	for _, pb := range req.Premises {
		p, err := toHash(pb)
		if err != nil {
			return nil, status.Errorf(codes.InvalidArgument, "%v", err)
		}
		premises = append(premises, p)
	}
	if err := s.store.Graph().RegisterEdgeTx(edge, premises, conclusion); err != nil {
		return nil, status.Errorf(codes.Internal, "register edge: %v", err)
	}
	return &arxdbpb.RegisterEdgeResponse{}, nil
}

func (s *Service) GetConnectivity(ctx context.Context, req *arxdbpb.GetConnectivityRequest) (*arxdbpb.GetConnectivityResponse, error) {
	edge, err := toHash(req.EdgeHash)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "%v", err)
	}
	premises, conclusion, found, err := s.store.Graph().GetConnectivity(edge)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "get connectivity: %v", err)
	}
	resp := &arxdbpb.GetConnectivityResponse{Found: found}
	if found {
		resp.Conclusion = conclusion[:]
		resp.Premises = make([][]byte, 0, len(premises))
		for _, p := range premises {
			resp.Premises = append(resp.Premises, p[:])
		}
	}
	return resp, nil
}

func (s *Service) IncomingEdges(ctx context.Context, req *arxdbpb.IncomingEdgesRequest) (*arxdbpb.IncomingEdgesResponse, error) {
	node, err := toHash(req.NodeHash)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "%v", err)
	}
	edges, err := s.store.Graph().IncomingEdges(node)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "incoming edges: %v", err)
	}
	resp := &arxdbpb.IncomingEdgesResponse{EdgeHashes: make([][]byte, 0, len(edges))}
	for _, e := range edges {
		resp.EdgeHashes = append(resp.EdgeHashes, e[:])
	}
	return resp, nil
}

func (s *Service) OutgoingEdges(ctx context.Context, req *arxdbpb.OutgoingEdgesRequest) (*arxdbpb.OutgoingEdgesResponse, error) {
	node, err := toHash(req.NodeHash)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "%v", err)
	}
	edges, err := s.store.Graph().OutgoingEdges(node)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "outgoing edges: %v", err)
	}
	resp := &arxdbpb.OutgoingEdgesResponse{EdgeHashes: make([][]byte, 0, len(edges))}
	for _, e := range edges {
		resp.EdgeHashes = append(resp.EdgeHashes, e[:])
	}
	return resp, nil
}

func (s *Service) AllNodes(ctx context.Context, req *arxdbpb.AllNodesRequest) (*arxdbpb.AllNodesResponse, error) {
	nodes, err := s.store.Graph().AllNodes()
	if err != nil {
		return nil, status.Errorf(codes.Internal, "all nodes: %v", err)
	}
	resp := &arxdbpb.AllNodesResponse{NodeHashes: make([][]byte, 0, len(nodes))}
	for _, n := range nodes {
		resp.NodeHashes = append(resp.NodeHashes, n[:])
	}
	return resp, nil
}

func (s *Service) AllEdges(ctx context.Context, req *arxdbpb.AllEdgesRequest) (*arxdbpb.AllEdgesResponse, error) {
	edges, err := s.store.Graph().AllEdges()
	if err != nil {
		return nil, status.Errorf(codes.Internal, "all edges: %v", err)
	}
	resp := &arxdbpb.AllEdgesResponse{EdgeHashes: make([][]byte, 0, len(edges))}
	for _, e := range edges {
		resp.EdgeHashes = append(resp.EdgeHashes, e[:])
	}
	return resp, nil
}

// --- append log ---

func (s *Service) Append(ctx context.Context, req *arxdbpb.AppendRequest) (*arxdbpb.AppendResponse, error) {
	entry, err := s.store.Log().Append(req.Entry)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "append: %v", err)
	}
	return &arxdbpb.AppendResponse{Entry: logEntryToProto(entry)}, nil
}

func (s *Service) GetEntry(ctx context.Context, req *arxdbpb.GetEntryRequest) (*arxdbpb.GetEntryResponse, error) {
	entry, err := s.store.Log().Get(req.Seq)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "get entry: %v", err)
	}
	return &arxdbpb.GetEntryResponse{Entry: logEntryToProto(entry), Found: entry != nil}, nil
}

func (s *Service) RootHash(ctx context.Context, req *arxdbpb.RootHashRequest) (*arxdbpb.RootHashResponse, error) {
	root, err := s.store.Log().RootHash()
	if err != nil {
		return nil, status.Errorf(codes.Internal, "root hash: %v", err)
	}
	return &arxdbpb.RootHashResponse{RootHash: root[:]}, nil
}

func (s *Service) InclusionProof(ctx context.Context, req *arxdbpb.InclusionProofRequest) (*arxdbpb.InclusionProofResponse, error) {
	n, err := s.store.Log().Len()
	if err != nil {
		return nil, status.Errorf(codes.Internal, "len: %v", err)
	}
	if req.Seq < 0 || req.Seq >= n {
		return &arxdbpb.InclusionProofResponse{Found: false}, nil
	}
	proof, err := s.store.Log().GetInclusionProof(req.Seq)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "inclusion proof: %v", err)
	}
	resp := &arxdbpb.InclusionProofResponse{
		LeafHash: proof.LeafHash[:],
		Index:    int64(proof.Index),
		Path:     make([][]byte, 0, len(proof.Path)),
		Found:    true,
	}
	for _, p := range proof.Path {
		resp.Path = append(resp.Path, p[:])
	}
	return resp, nil
}

func (s *Service) Len(ctx context.Context, req *arxdbpb.LenRequest) (*arxdbpb.LenResponse, error) {
	n, err := s.store.Log().Len()
	if err != nil {
		return nil, status.Errorf(codes.Internal, "len: %v", err)
	}
	return &arxdbpb.LenResponse{Count: n}, nil
}

// --- atomic commit ---

func (s *Service) CommitEdge(ctx context.Context, req *arxdbpb.CommitEdgeRequest) (*arxdbpb.CommitEdgeResponse, error) {
	conclusion, err := toHash(req.Conclusion)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "%v", err)
	}
	premises := make([]hashing.Hash, 0, len(req.Premises))
	for _, pb := range req.Premises {
		p, err := toHash(pb)
		if err != nil {
			return nil, status.Errorf(codes.InvalidArgument, "%v", err)
		}
		premises = append(premises, p)
	}
	var proof []byte
	if req.Proof != nil {
		proof = req.Proof
	}
	edgeHash, entry, err := s.store.CommitEdgeTx(premises, conclusion, req.EdgeData, proof)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "commit edge: %v", err)
	}
	return &arxdbpb.CommitEdgeResponse{
		EdgeHash: edgeHash[:],
		Entry:    logEntryToProto(entry),
	}, nil
}
