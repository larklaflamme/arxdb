#!/usr/bin/env python3
"""seed_phaser.py — import the phaser-thread corpus through verify_and_commit.

Phase 4's second deliverable. It ingests `src/arxdb/seed/corpus.py` *through*
the public `verify_and_commit` pipeline (never bypassing it), is idempotent
(re-running skips already-present edges), and prints a verification report
showing expected κ vs actual κ per edge.

Phase 5 wiring: after seeding, it builds the genesis roster binding "Skye" to
the seed signer key and runs `verify_edge_attestation` on every committed edge
— the plan's §9 acceptance test that the corpus edges resolve to a *named*
agent rather than an anonymous 32-byte key.

Usage:
    python scripts/seed_phaser.py [--root PATH] [--backend sqlite|grpc] [--socket PATH]

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

from arxdb.attestation.attest import (
    AnchorRecord,
    anchor,
    commit_roster,
    verify_edge_attestation,
)
from arxdb.attestation.roster import Roster
from arxdb.query.path import path_discovery
from arxdb.query.reachability import reachable
from arxdb.query.resolve import resolve_edge
from arxdb.seed.corpus import CORPUS_EDGES, CORPUS_NODES
from arxdb.storage.hashing import hash_bytes
from arxdb.storage.keys import generate_keypair
from arxdb.storage.factory import create_storage
from arxdb.storage.storage import Storage
from arxdb.verification.commit import verify_and_commit
from arxdb.verification.schema import Edge, EdgeType, Kappa, Node
from arxdb.verification.verifier import verify

_KEYPAIR_FILE = "seed_keypair.bin"
_SERVER_KEYPAIR_FILE = "server_keypair.bin"
_SERVER_AGENT = "arxdb-server"
_KEYPAIR_SIZE = 64  # 32-byte private seed + 32-byte public key
_ROSTER_FILE = "roster.bin"
_ANCHOR_FILE = "anchor.bin"


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
    """Map corpus keys (N1..N9) to `Node` objects."""
    return {
        n.key: Node(claim=n.claim, domain=n.domain, polarity=n.polarity)
        for n in CORPUS_NODES
    }


def _build_edge(e, node_map: dict[str, Node], signer_pubkey: bytes) -> Edge | None:
    """Build the `Edge` record for a corpus edge, or None if it would be rejected.

    Shared by `seed()` and `verify_seed_attestation()` so the edge construction
    (and therefore the content address) is identical in both paths.
    """
    premises = [node_map[k] for k in e.premise_keys]
    conclusion = node_map[e.conclusion_key]

    v = verify(premises, conclusion, e.rule, e.edge_type, e.proof_bytes)
    if v.rejected:
        return None

    premise_hashes = [p.node_id() for p in premises]
    conclusion_hash = conclusion.node_id()
    proof_hash = hash_bytes(e.proof_bytes) if e.proof_bytes is not None else None
    return Edge(
        type=e.edge_type,
        premises=tuple(premise_hashes),
        conclusion=conclusion_hash,
        rule=e.rule,
        proof_hash=proof_hash,
        verdict=v.verdict,
        kappa=v.kappa,
        signer_pubkey=signer_pubkey,
    )


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
        edge_record = _build_edge(e, node_map, signer_pubkey)
        if edge_record is None:
            rows.append(
                SeedRow(e.key, e.edge_type, e.rule, e.expected_kappa, None, "REJECTED")
            )
            continue

        edge_hash = edge_record.edge_hash()
        if resolve_edge(edge_hash, storage) is not None:
            rows.append(
                SeedRow(e.key, e.edge_type, e.rule, e.expected_kappa, edge_record.kappa, "SKIP")
            )
            continue

        premises = [node_map[k] for k in e.premise_keys]
        conclusion = node_map[e.conclusion_key]
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


def verify_seed_attestation(
    storage: Storage, roster: Roster, signer_pubkey: bytes
) -> list[tuple[str, bool, str | None]]:
    """Verify every corpus edge's attestation resolves to a named agent.

    Returns (edge_key, ok, signer_agent_id) per edge. This is the Phase 5
    acceptance test: provenance requires the signer_pubkey to resolve to
    "Skye" via the roster, not remain an anonymous 32-byte blob.
    """
    node_map = _node_map()
    results: list[tuple[str, bool, str | None]] = []
    for e in CORPUS_EDGES:
        edge_record = _build_edge(e, node_map, signer_pubkey)
        if edge_record is None:
            results.append((e.key, False, None))
            continue
        res = verify_edge_attestation(edge_record, storage, roster)
        results.append((e.key, res.ok, res.signer_agent_id))
    return results


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


def _load_or_create_server_keypair(root: Path) -> tuple[bytes, bytes]:
    """Load (or create) the API server's keypair so the roster can bind it.

    The seed and the server share one root and one roster. The server signs
    API-committed edges as "arxdb-server"; the seed signs corpus edges as
    "Skye". Both identities must be in the genesis roster so attestation
    resolves either signer. This loads the *same* `server_keypair.bin` the
    server uses, so the binding is stable regardless of run order.
    """
    path = root / _SERVER_KEYPAIR_FILE
    if path.exists():
        data = path.read_bytes()
        if len(data) == _KEYPAIR_SIZE:
            return data[:32], data[32:]
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


def _print_attestation(
    storage: Storage, roster: Roster, signer_pubkey: bytes
) -> None:
    """Run the Phase 5 acceptance test and print the provenance result."""
    results = verify_seed_attestation(storage, roster, signer_pubkey)
    all_ok = all(ok for _, ok, _ in results)
    print("\n--- Phase 5 acceptance: provenance (roster) ---")
    print(f"roster_hash={roster.roster_hash().hex()[:16]}...")
    for key, ok, agent in results:
        print(f"  {key}: ok={ok} signer={agent}")
    print(f"  => all corpus edges resolve to 'Skye': {all_ok}")


def persist_anchor(storage: Storage, roster: Roster, root: Path) -> AnchorRecord:
    """Build the anchor record and persist roster + anchor to disk.

    Writes `<root>/roster.bin` (the roster's canonical CBOR) and
    `<root>/anchor.bin` (the anchor record's canonical CBOR). The anchor's
    `root_hash` covers the roster (genesis entry) plus all committed edges, so
    the two files together are the complete external trust anchor.
    """
    rec = anchor(storage, roster)
    (root / _ROSTER_FILE).write_bytes(roster.roster_bytes())
    (root / _ANCHOR_FILE).write_bytes(rec.anchor_bytes())
    return rec


def _print_anchor(rec: AnchorRecord) -> None:
    """Print the persisted anchor record summary."""
    print("\n--- Phase 5 acceptance: anchor record ---")
    print(f"root_hash={rec.root_hash.hex()[:16]}...")
    print(f"entry_count={rec.entry_count}")
    print(f"roster_hash={rec.roster_hash.hex()[:16]}...")
    print(f"anchor_hash={rec.anchor_hash().hex()[:16]}...")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the phaser-thread corpus.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("data"),
        help="Filesystem root for keypair/roster/anchor files (and SQLite data when backend=sqlite).",
    )
    parser.add_argument(
        "--backend",
        choices=["sqlite", "grpc"],
        default="sqlite",
        help="Storage backend (default: sqlite). grpc delegates to a running arxdbd daemon.",
    )
    parser.add_argument(
        "--socket",
        default="/tmp/arxdb.sock",
        help="gRPC UNIX socket path (grpc backend only).",
    )
    args = parser.parse_args(argv)

    root: Path = args.root
    root.mkdir(parents=True, exist_ok=True)
    priv, pub = _load_or_create_keypair(root)
    _, server_pub = _load_or_create_server_keypair(root)
    storage = create_storage(root, priv, pub, backend=args.backend, socket_path=args.socket)
    # The genesis roster binds both signers: "Skye" (corpus edges) and
    # "arxdb-server" (API-committed edges). Built complete *before* seeding so
    # the committed roster (log entry 0) matches the on-disk roster exactly.
    roster = Roster(entries={"Skye": pub, _SERVER_AGENT: server_pub})

    try:
        commit_roster(storage, roster)
        rows = seed(storage, pub)
        _print_report(rows)
        _print_exit_criteria(storage)
        _print_attestation(storage, roster, pub)
        rec = persist_anchor(storage, roster, root)
        _print_anchor(rec)
    finally:
        storage.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
