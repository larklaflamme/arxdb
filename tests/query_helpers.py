"""Shared helpers for Phase 3 query tests: build graphs directly.

The query layer is what these tests exercise, so edges are constructed and
committed directly (bypassing the verifier) to give precise control over κ,
type, and structure. Node payloads are persisted so `resolve_node`/`resolve_edge`
can decode them.
"""

from __future__ import annotations

from arxdb.storage.hashing import Hash
from arxdb.storage.storage import Storage
from arxdb.verification.schema import Edge, EdgeType, Kappa, Node, Verdict

# A fixed dummy signer pubkey; irrelevant to the query layer.
_SIGNER = b"\x00" * 32


def node(claim: str, domain: str = "math", polarity: bool = True) -> Node:
    """A convenience Node constructor."""
    return Node(claim=claim, domain=domain, polarity=polarity)


def commit_edge(
    storage: Storage,
    edge_type: EdgeType,
    premises: list[Node],
    conclusion: Node,
    kappa: Kappa,
    rule: str = "r",
    verdict: Verdict = Verdict.PASS,
) -> tuple[Hash, Edge]:
    """Build and commit an edge directly. Returns (edge_hash, edge).

    Persists every node payload (so the query layer can resolve them) and
    commits the edge bytes via the storage facade.
    """
    for p in premises:
        storage.objects.put(p.node_bytes())
    storage.objects.put(conclusion.node_bytes())

    edge = Edge(
        type=edge_type,
        premises=tuple(p.node_id() for p in premises),
        conclusion=conclusion.node_id(),
        rule=rule,
        proof_hash=None,
        verdict=verdict,
        kappa=kappa,
        signer_pubkey=_SIGNER,
    )
    edge_hash, _ = storage.commit_edge_tx(
        premises=[p.node_id() for p in premises],
        conclusion=conclusion.node_id(),
        edge_data=edge.edge_bytes(),
    )
    return edge_hash, edge


def commit_refutation(
    storage: Storage,
    target_edge_hash: Hash,
    kappa: Kappa = Kappa.K1,
) -> tuple[Hash, Edge]:
    """Build and commit a zero-premise REFUTATION edge attacking an edge.

    A refutation's conclusion is the *target edge's hash* (not a node hash),
    per the attack-graph definition. Returns (edge_hash, edge).
    """
    edge = Edge(
        type=EdgeType.REFUTATION,
        premises=(),
        conclusion=target_edge_hash,
        rule="refute",
        proof_hash=None,
        verdict=Verdict.PASS,
        kappa=kappa,
        signer_pubkey=_SIGNER,
    )
    edge_hash, _ = storage.commit_edge_tx(
        premises=[],
        conclusion=target_edge_hash,
        edge_data=edge.edge_bytes(),
    )
    return edge_hash, edge
