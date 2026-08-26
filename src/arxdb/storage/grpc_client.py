"""gRPC storage client — the Go-backed Storage implementation.

`GrpcStorage` presents the *same* Storage interface as the in-process SQLite
backend (`storage.Storage`), but delegates every operation to the Go daemon
(`cmd/arxdbd`) over gRPC. The verification and query layers are untouched:
they keep calling `storage.commit_edge_tx(...)`, `storage.objects.get(...)`,
`storage.graph.incoming_edges(...)`, etc., and get the same types back.

The daemon owns the storage engine and the signing keypair; this client holds
only a gRPC channel. `verify_entry` is implemented locally (it is a pure
function of the entry's fields) to avoid a round-trip.

Public API (Phase 6):
    GrpcStorage(socket_path: str)
        objects: GrpcObjectStore
        graph: GrpcGraphIndex
        log: GrpcAppendLog
        commit_edge_tx(premises, conclusion, edge_data, proof) -> (Hash, LogEntry)
        close() -> None
"""

from __future__ import annotations

import grpc

from .grpc_gen import arxdb_pb2, arxdb_pb2_grpc
from .hashing import Hash, hash_bytes
from .keys import verify
from .serialization import canonical_encode
from .append_log import LogEntry
from .merkle import MerkleInclusionProof


def _signature_message(
    seq: int,
    timestamp_ns: int,
    signer_pubkey: bytes,
    entry_hash: Hash,
    prev_log_hash: Hash,
) -> bytes:
    """The exact bytes signed for an entry (mirrors append_log._signature_message)."""
    return canonical_encode(
        [seq, timestamp_ns, signer_pubkey, entry_hash, prev_log_hash]
    )


def _log_entry_from_proto(e: arxdb_pb2.LogEntry) -> LogEntry:
    return LogEntry(
        seq=e.seq,
        timestamp_ns=e.timestamp_ns,
        signer_pubkey=e.signer_pubkey,
        entry_hash=Hash(e.entry_hash),
        prev_log_hash=Hash(e.prev_log_hash),
        signature=e.signature,
        payload=e.payload,
    )


class GrpcObjectStore:
    """Content-addressed object store, delegating to the Go daemon."""

    def __init__(self, stub: arxdb_pb2_grpc.StorageServiceStub) -> None:
        self._stub = stub

    def put(self, data: bytes) -> Hash:
        resp = self._stub.PutObject(arxdb_pb2.PutObjectRequest(data=[data]))
        return Hash(resp.hashes[0])

    def put_batch(self, items: list[bytes]) -> list[Hash]:
        resp = self._stub.PutObject(arxdb_pb2.PutObjectRequest(data=list(items)))
        return [Hash(h) for h in resp.hashes]

    def get(self, h: Hash) -> bytes | None:
        resp = self._stub.GetObject(arxdb_pb2.GetObjectRequest(hashes=[bytes(h)]))
        return resp.data[0] if resp.found[0] else None

    def get_batch(self, hashes: list[Hash]) -> list[bytes | None]:
        resp = self._stub.GetObject(
            arxdb_pb2.GetObjectRequest(hashes=[bytes(h) for h in hashes])
        )
        return [d if f else None for d, f in zip(resp.data, resp.found)]

    def has(self, h: Hash) -> bool:
        resp = self._stub.HasObject(arxdb_pb2.HasObjectRequest(hashes=[bytes(h)]))
        return resp.found[0]

    def has_batch(self, hashes: list[Hash]) -> list[bool]:
        resp = self._stub.HasObject(
            arxdb_pb2.HasObjectRequest(hashes=[bytes(h) for h in hashes])
        )
        return list(resp.found)


class GrpcGraphIndex:
    """Structural adjacency index, delegating to the Go daemon."""

    def __init__(self, stub: arxdb_pb2_grpc.StorageServiceStub) -> None:
        self._stub = stub

    def register_node(self, node_hash: Hash) -> None:
        self._stub.RegisterNode(
            arxdb_pb2.RegisterNodeRequest(node_hash=bytes(node_hash))
        )

    def register_edge(
        self, edge_hash: Hash, premises: list[Hash], conclusion: Hash
    ) -> None:
        self._stub.RegisterEdge(
            arxdb_pb2.RegisterEdgeRequest(
                edge_hash=bytes(edge_hash),
                premises=[bytes(p) for p in premises],
                conclusion=bytes(conclusion),
            )
        )

    def incoming_edges(self, node_hash: Hash) -> list[Hash]:
        resp = self._stub.IncomingEdges(
            arxdb_pb2.IncomingEdgesRequest(node_hash=bytes(node_hash))
        )
        return [Hash(e) for e in resp.edge_hashes]

    def outgoing_edges(self, node_hash: Hash) -> list[Hash]:
        resp = self._stub.OutgoingEdges(
            arxdb_pb2.OutgoingEdgesRequest(node_hash=bytes(node_hash))
        )
        return [Hash(e) for e in resp.edge_hashes]

    def get_connectivity(self, edge_hash: Hash) -> tuple[list[Hash], Hash] | None:
        resp = self._stub.GetConnectivity(
            arxdb_pb2.GetConnectivityRequest(edge_hash=bytes(edge_hash))
        )
        if not resp.found:
            return None
        return ([Hash(p) for p in resp.premises], Hash(resp.conclusion))

    def all_nodes(self) -> list[Hash]:
        resp = self._stub.AllNodes(arxdb_pb2.AllNodesRequest())
        return [Hash(n) for n in resp.node_hashes]

    def all_edges(self) -> list[Hash]:
        resp = self._stub.AllEdges(arxdb_pb2.AllEdgesRequest())
        return [Hash(e) for e in resp.edge_hashes]


class GrpcAppendLog:
    """Signed append-only log, delegating to the Go daemon."""

    def __init__(self, stub: arxdb_pb2_grpc.StorageServiceStub) -> None:
        self._stub = stub

    def append(self, entry: bytes) -> LogEntry:
        resp = self._stub.Append(arxdb_pb2.AppendRequest(entry=entry))
        return _log_entry_from_proto(resp.entry)

    def get(self, seq: int) -> LogEntry | None:
        resp = self._stub.GetEntry(arxdb_pb2.GetEntryRequest(seq=seq))
        return _log_entry_from_proto(resp.entry) if resp.found else None

    def __len__(self) -> int:
        resp = self._stub.Len(arxdb_pb2.LenRequest())
        return resp.count

    def root_hash(self) -> Hash:
        resp = self._stub.RootHash(arxdb_pb2.RootHashRequest())
        return Hash(resp.root_hash)

    def get_inclusion_proof(self, seq: int) -> MerkleInclusionProof:
        resp = self._stub.InclusionProof(arxdb_pb2.InclusionProofRequest(seq=seq))
        if not resp.found:
            raise IndexError(f"seq {seq} out of range")
        return MerkleInclusionProof(
            leaf_hash=Hash(resp.leaf_hash),
            index=resp.index,
            path=[Hash(p) for p in resp.path],
        )

    def verify_entry(self, entry: LogEntry) -> bool:
        """Verify an entry's signature and payload integrity (local, no RPC)."""
        if hash_bytes(entry.payload) != entry.entry_hash:
            return False
        message = _signature_message(
            entry.seq,
            entry.timestamp_ns,
            entry.signer_pubkey,
            entry.entry_hash,
            entry.prev_log_hash,
        )
        return verify(entry.signer_pubkey, message, entry.signature)


class GrpcStorage:
    """Unified storage facade delegating to the Go daemon over gRPC."""

    def __init__(self, socket_path: str) -> None:
        self._channel = grpc.insecure_channel(f"unix://{socket_path}")
        self._stub = arxdb_pb2_grpc.StorageServiceStub(self._channel)
        self.objects = GrpcObjectStore(self._stub)
        self.graph = GrpcGraphIndex(self._stub)
        self.log = GrpcAppendLog(self._stub)

    def close(self) -> None:
        self._channel.close()

    def commit_edge_tx(
        self,
        premises: list[Hash],
        conclusion: Hash,
        edge_data: bytes,
        proof: bytes | None = None,
    ) -> tuple[Hash, LogEntry]:
        req = arxdb_pb2.CommitEdgeRequest(
            premises=[bytes(p) for p in premises],
            conclusion=bytes(conclusion),
            edge_data=edge_data,
        )
        if proof is not None:
            req.proof = proof
        resp = self._stub.CommitEdge(req)
        return Hash(resp.edge_hash), _log_entry_from_proto(resp.entry)
