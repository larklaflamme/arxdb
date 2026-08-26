#!/usr/bin/env python3
"""seed_phaser.py — import the phaser-thread corpus through verify_and_commit.

Phase 4's second deliverable. It ingests `src/arxdb/seed/corpus.py` *through*
the public `verify_and_commit` pipeline (never bypassing it), is idempotent
(re-running skips already-present edges), and prints a verification report
showing expected κ vs actual κ per edge.

Usage:
    python scripts/seed_phaser.py [--root PATH]

The signer keypair is persisted to `<root>/seed_keypair.bin` so that the
signer identity — and therefore every edge's content address — is stable
across runs (idempotency depends on it: the signer_pubkey is part of the
edge hash).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from arxdb.query.path import path_discovery
from arxdb.query.reachability import reachable
from arxdb.query.resolve import resolve_edge
from arxdb.seed.corpus import CORPUS_EDGES, CORPUS_NODES
from arxdb.storage.hashing import hash_bytes
from arxdb.storage.keys import generate_keypair
from arxdb.storage.storage import Storage
from arxdb.verification.commit import verify_and_commit
from arxdb.verification.schema import Edge, EdgeType, Kappa, Node
from arxdb.verification.verifier import verify

_KEYPAIR_FILE = "seed_keypair.bin"
_KEYPAIR_SIZE = 64  # 32-byte private seed + 32-byte public key


@dataclass(frozen=True)
class SeedRow:
    """One row of the seed report."""

    key: str
    edge_type: EdgeType
    rule: str
    expected_kappa: Kappa
    actual_kappa: Kappa | None  # None when the edge was rejected
    status: str  # MATCH | MISMATCH | REJECTED | SKIP


def _node_map() -> dict[str, Node]:
    """Map corpus keys (N1..N8) to `Node` objects."""
    return {
        n.key: Node(claim=n.claim, domain=n.domain, polarity=n.polarity)
        for n in CORPUS_NODES
    }


def seed(storage: Storage, signer_pubkey: bytes) -> list[SeedRow]:
    """Ingest the corpus through `verify_and_commit`; return report rows.

    Idempotent: an edge whose content address is already present is skipped
    (with a SKIP row) rather than re-committed. The pre-check runs `verify`
    once to learn the verdict/κ (needed to compute the edge's content
    address); `verify_and_commit` re-runs it deterministically on commit.
    """
    node_map = _node_map()
    rows: list[SeedRow] = []

    for e in CORPUS_EDGES:
        premises = [node_map[k] for k in e.premise_keys]
        conclusion = node_map[e.conclusion_key]

        # Pre-check: verify to learn verdict/κ, then build the edge record to
        # compute its content address for the idempotency check.
        v = verify(premises, conclusion, e.rule, e.edge_type, e.proof_bytes)
        if v.rejected:
            rows.append(
                SeedRow(e.key, e.edge_type, e.rule, e.expected_kappa, None, "REJECTED")
            )
            continue

        premise_hashes = [p.node_id() for p in premises]
        conclusion_hash = conclusion.node_id()
        proof_hash = hash_bytes(e.proof_bytes) if e.proof_bytes is not None else None
        edge_record = Edge(
            type=e.edge_type,
            premises=tuple(premise_hashes),
            conclusion=conclusion_hash,
            rule=e.rule,
            proof_hash=proof_hash,
            verdict=v.verdict,
            kappa=v.kappa,
            signer_pubkey=signer_pubkey,
        )
        edge_hash = edge_record.edge_hash()

        if resolve_edge(edge_hash, storage) is not None:
            rows.append(
                SeedRow(e.key, e.edge_type, e.rule, e.expected_kappa, v.kappa, "SKIP")
            )
            continue

        cr = verify_and_commit(
            storage,
            signer_pubkey,
            premises,
            conclusion,
            e.rule,
            e.edge_type,
            e.proof_bytes,
        )
        actual = cr.verification.kappa if not cr.rejected else None
        status = "MATCH" if actual == e.expected_kappa else "MISMATCH"
        rows.append(SeedRow(e.key, e.edge_type, e.rule, e.expected_kappa, actual, status))

    return rows


def _load_or_create_keypair(root: Path) -> tuple[bytes, bytes]:
    """Load the persisted seed keypair, or generate and persist a fresh one."""
    path = root / _KEYPAIR_FILE
    if path.exists():
        data = path.read_bytes()
        if len(data) == _KEYPAIR_SIZE:
            return data[:32], data[32:]
        # Corrupt/truncated: regenerate rather than fail silently.
    priv, pub = generate_keypair()
    path.write_bytes(priv + pub)
    return priv, pub


def _print_report(rows: list[SeedRow]) -> None:
    """Print the expected-vs-actual κ report."""
    print("====================== ARXDB SEED REPORT: PHASER THREAD ======================")
    print(f"{'EDGE':<5} {'TYPE':<11} {'RULE':<28} {'EXPECTED':<9} {'ACTUAL':<7} STATUS")
    print("-" * 78)
    for r in rows:
        actual = r.actual_kappa.value if r.actual_kappa is not None else "-"
        print(
            f"{r.key:<5} {r.edge_type.value:<11} {r.rule:<28} "
            f"{r.expected_kappa.value:<9} {actual:<7} {r.status}"
        )
    print("=" * 78)


def _print_exit_criteria(storage: Storage) -> None:
    """Run the exit-criteria queries and print their outcomes."""
    node_map = _node_map()
    n5 = node_map["N5"].node_id()
    n7 = node_map["N7"].node_id()

    print("\n--- Exit criteria ---")
    qa = reachable(n5, storage)
    print(
        f"Query A (phaser != Berry-Keating, N5): established={qa.established}, "
        f"kappa={qa.kappa.value if qa.kappa else None}, depth={qa.depth}"
    )
    ci = reachable(n7, storage, min_kappa=Kappa.K1)
    print(
        f"Conjecture isolation (RH at kappa>=K1, N7): established={ci.established}, "
        f"kappa={ci.kappa.value if ci.kappa else None}"
    )
    qb = path_discovery(n7, storage, min_kappa=Kappa.K1)
    print(
        f"Query B (path to RH at kappa>=K1, N7): reachable={qb.reachable} "
        f"at kappa={qb.kappa.value if qb.kappa else None}"
    )
    if not qb.reachable:
        print(f"  missing-edge frontier ({len(qb.missing_edges)} gaps):")
        for m in qb.missing_edges:
            blocking = ", ".join(b.hex()[:8] for b in m.blocking_nodes) or "(leaf)"
            print(
                f"    conclusion {m.conclusion.hex()[:8]} "
                f"rule={m.rule!r} blocking={blocking}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the phaser-thread corpus.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("data/arxdb-seed"),
        help="Storage root directory (default: data/arxdb-seed).",
    )
    args = parser.parse_args(argv)

    root: Path = args.root
    root.mkdir(parents=True, exist_ok=True)
    priv, pub = _load_or_create_keypair(root)
    storage = Storage(root, priv, pub)

    try:
        rows = seed(storage, pub)
        _print_report(rows)
        _print_exit_criteria(storage)
    finally:
        storage.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
