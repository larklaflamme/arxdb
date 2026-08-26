"""05 — Refutation: attack and defend edges; the grounded active subgraph.

Run from the repo root with the arxdb env active:

    python examples/05-refutation/refutation.py

Revocation is a first-class edge type, not a deletion. A REFUTATION edge
attacks another edge, and the query layer computes the *active subgraph* — which
edges are IN (valid), OUT (defeated), or UNDECIDED (mutual cycles) — using
Dung's grounded extension (skeptical, deterministic).

A refutation's conclusion is the *target edge's hash* (not a node hash), so it
is built directly rather than through verify_and_commit (which computes a
conclusion from a Node).
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from arxdb.query import compute_active_subgraph, reachable
from arxdb.storage.keys import generate_keypair
from arxdb.storage.storage import Storage
from arxdb.verification.commit import verify_and_commit
from arxdb.verification.schema import Edge, EdgeType, Kappa, Node, Verdict


def commit_refutation(store: Storage, target_edge_hash, signer_pubkey: bytes):
    """Build and commit a zero-premise REFUTATION edge attacking an edge."""
    edge = Edge(
        type=EdgeType.REFUTATION,
        premises=(),
        conclusion=target_edge_hash,
        rule="refute",
        proof_hash=None,
        verdict=Verdict.PASS,
        kappa=Kappa.K1,
        signer_pubkey=signer_pubkey,
    )
    edge_hash, _ = store.commit_edge_tx(
        premises=[],
        conclusion=target_edge_hash,
        edge_data=edge.edge_bytes(),
    )
    return edge_hash, edge


def main() -> None:
    priv, pub = generate_keypair()
    with TemporaryDirectory() as tmp:
        store = Storage(Path(tmp), priv, pub)

        # A small chain: A (definition) -> B (deduction) -> C (deduction).
        a = Node(claim="x > 0", domain="math")
        b = Node(claim="x + 1 > 0", domain="math")
        c = Node(claim="x + 2 > 0", domain="math")

        r_a = verify_and_commit(store, pub, [], a, "assume", EdgeType.DEFINITION)
        r_b = verify_and_commit(store, pub, [a], b, "add 1", EdgeType.DEDUCTION)
        r_c = verify_and_commit(store, pub, [b], c, "add 1", EdgeType.DEDUCTION)

        # Before refutation: C is established.
        q0 = reachable(c.node_id(), store)
        print(f"[before]    C established={q0.established}")

        # Refute the B edge.
        ref_hash, _ = commit_refutation(store, r_b.edge_hash, pub)

        active = compute_active_subgraph(store)
        print(f"[active]    B in={r_b.edge_hash in active.in_edges} "
              f"out={r_b.edge_hash in active.out_edges}")

        # With B defeated, C loses its derived status.
        q1 = reachable(c.node_id(), store, active_edges=active.in_edges)
        print(f"[after]     C established={q1.established}")

        # Refute the refutation: B is reinstated.
        commit_refutation(store, ref_hash, pub)
        active2 = compute_active_subgraph(store)
        q2 = reachable(c.node_id(), store, active_edges=active2.in_edges)
        print(f"[reinstated] C established={q2.established}")

        store.close()


if __name__ == "__main__":
    main()
