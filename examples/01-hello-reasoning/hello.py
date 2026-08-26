"""01 — Hello, reasoning: the minimal end-to-end ArxDB walkthrough.

Run from the repo root with the arxdb env active:

    python examples/01-hello-reasoning/hello.py

This is the smallest possible program that exercises the whole pipeline:
keypair -> storage -> verify-and-commit -> query -> resolve.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from arxdb.query import reachable, resolve_node
from arxdb.storage.keys import generate_keypair
from arxdb.storage.storage import Storage
from arxdb.verification.commit import verify_and_commit
from arxdb.verification.schema import EdgeType, Node


def main() -> None:
    # Every agent holds an Ed25519 keypair. The private key signs the append
    # log; the public key is embedded in every edge as "who proposed this".
    priv, pub = generate_keypair()

    with TemporaryDirectory() as tmp:
        store = Storage(Path(tmp), priv, pub)

        # 1. An axiom: a zero-premise DEFINITION. "for all x, x = x" is in the
        #    curated roster, so it earns kappa_inf (axiomatic ground).
        axiom = Node(claim="for all x, x = x", domain="math")
        r_axiom = verify_and_commit(
            store, pub, [], axiom, "reflexivity", EdgeType.DEFINITION,
        )
        print(f"[axiom]     verdict={r_axiom.verification.verdict.value:10s} "
              f"kappa={r_axiom.verification.kappa.value}")

        # 2. A deduction, machine-checked by Z3. No proof blob => the Z3
        #    checker runs (a proof blob would dispatch to Lean instead).
        a = Node(claim="x > 0", domain="math")
        b = Node(claim="x + 1 > 0", domain="math")
        r_ded = verify_and_commit(
            store, pub, [a], b, "add 1 to both sides", EdgeType.DEDUCTION,
        )
        print(f"[deduction] verdict={r_ded.verification.verdict.value:10s} "
              f"kappa={r_ded.verification.kappa.value}")

        # 3. A citation: a claim taken on authority. No checker runs; kappa1.
        c = Node(claim="the Riemann hypothesis is unproven", domain="math")
        r_cite = verify_and_commit(
            store, pub, [], c, "cite", EdgeType.CITATION,
        )
        print(f"[citation]  verdict={r_cite.verification.verdict.value:10s} "
              f"kappa={r_cite.verification.kappa.value}")

        # 4. Query: is the axiom's conclusion established, and at what strength?
        q = reachable(axiom.node_id(), store)
        print(f"[reachable] axiom established={q.established} "
              f"kappa={q.kappa.value if q.kappa else None} depth={q.depth}")

        # 5. Resolve a content address back to its human-readable record.
        node = resolve_node(axiom.node_id(), store)
        print(f"[resolve]   {node.claim!r} (domain={node.domain})")

        store.close()


if __name__ == "__main__":
    main()
