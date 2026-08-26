"""02 — Research provenance: the kappa scale maps onto real research artifacts.

Run from the repo root with the arxdb env active:

    python examples/02-research-provenance/research.py

Shows how ArxDB classifies reasoning by strength (kappa), and how path
discovery names the "wall" — the exact missing step that would upgrade a
conjecture to a theorem.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from arxdb.query import path_discovery, reachable
from arxdb.storage.keys import generate_keypair
from arxdb.storage.storage import Storage
from arxdb.verification.commit import verify_and_commit
from arxdb.verification.schema import EdgeType, Kappa, Node


def main() -> None:
    priv, pub = generate_keypair()
    with TemporaryDirectory() as tmp:
        store = Storage(Path(tmp), priv, pub)

        # --- the kappa scale, one edge per level ---
        axiom = Node(claim="for all x, x = x", domain="math")
        assumption = Node(claim="x > 0", domain="math")
        derived = Node(claim="x + 1 > 0", domain="math")
        identity = Node(claim="x**2 - 1 = (x - 1)*(x + 1)", domain="math")
        rh_status = Node(claim="the Riemann hypothesis is unproven", domain="math")
        rh = Node(claim="the nontrivial zeros of zeta lie on the critical line",
                  domain="math")

        edges = [
            ("kappa_inf (axiom)", verify_and_commit(
                store, pub, [], axiom, "reflexivity", EdgeType.DEFINITION)),
            ("kappa1 (assumption)", verify_and_commit(
                store, pub, [], assumption, "assume", EdgeType.DEFINITION)),
            ("kappa3 (Z3 deduction)", verify_and_commit(
                store, pub, [assumption], derived, "add 1", EdgeType.DEDUCTION)),
            ("kappa2 (CAS identity)", verify_and_commit(
                store, pub, [], identity, "factor", EdgeType.NUMERICAL)),
            ("kappa1 (citation)", verify_and_commit(
                store, pub, [], rh_status, "cite", EdgeType.CITATION)),
            ("kappa1 (citation)", verify_and_commit(
                store, pub, [rh_status], rh, "cite", EdgeType.CITATION)),
        ]
        for label, r in edges:
            print(f"{label:24s} -> verdict={r.verification.verdict.value:10s} "
                  f"kappa={r.verification.kappa.value}")

        # --- reachability at different strength thresholds ---
        print()
        for k in (Kappa.K0, Kappa.K1, Kappa.K2, Kappa.K3):
            q = reachable(rh.node_id(), store, min_kappa=k)
            print(f"reachable(RH, min_kappa={k.value:7s}) -> "
                  f"established={q.established}")

        # --- path discovery: name the wall ---
        print()
        p = path_discovery(rh.node_id(), store, min_kappa=Kappa.K2)
        print(f"path_discovery(RH, min_kappa=K2): reachable={p.reachable}")
        for me in p.missing_edges:
            print(f"  missing: conclusion={me.conclusion.hex()[:12]}... "
                  f"blocking={len(me.blocking_nodes)} rule={me.rule!r}")

        store.close()


if __name__ == "__main__":
    main()
