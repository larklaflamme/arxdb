"""04 — Collaborative reasoning: multiple named agents, each signing their own edges.

Run from the repo root with the arxdb env active:

    python examples/04-collaborative-reasoning/collaborative.py

Three agents (Alice, Bob, Carol) build on a shared reasoning graph. Each edge
records who proposed it (signer_pubkey), and the roster resolves that key to a
name — so provenance is a *named* attribution, not an anonymous 32-byte blob.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from arxdb.attestation.attest import verify_edge_attestation
from arxdb.attestation.roster import Roster
from arxdb.storage.keys import generate_keypair
from arxdb.storage.storage import Storage
from arxdb.verification.commit import verify_and_commit
from arxdb.verification.schema import EdgeType, Node


def main() -> None:
    # Three agents, each with their own keypair.
    alice_priv, alice_pub = generate_keypair()
    bob_priv, bob_pub = generate_keypair()
    carol_priv, carol_pub = generate_keypair()
    roster = Roster(entries={
        "alice": alice_pub,
        "bob": bob_pub,
        "carol": carol_pub,
    })

    with TemporaryDirectory() as tmp:
        # One shared store. The store's own keypair (alice's, here) signs the
        # append log; each edge separately records who *proposed* it.
        store = Storage(Path(tmp), alice_priv, alice_pub)

        # Alice proposes an assumption.
        a = Node(claim="x > 0", domain="math")
        r_a = verify_and_commit(
            store, alice_pub, [], a, "assume", EdgeType.DEFINITION,
        )

        # Bob builds on Alice's assumption.
        b = Node(claim="x + 1 > 0", domain="math")
        r_b = verify_and_commit(
            store, bob_pub, [a], b, "add 1", EdgeType.DEDUCTION,
        )

        # Carol cites an external result.
        c = Node(claim="the Riemann hypothesis is unproven", domain="math")
        r_c = verify_and_commit(
            store, carol_pub, [], c, "cite", EdgeType.CITATION,
        )

        # Provenance: each edge resolves to its named author.
        for label, r in (("alice", r_a), ("bob", r_b), ("carol", r_c)):
            att = verify_edge_attestation(r.edge, store, roster)
            print(f"[{label}] signer={att.signer_agent_id} ok={att.ok}")

        store.close()


if __name__ == "__main__":
    main()
