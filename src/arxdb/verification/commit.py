"""commit.py — the verify-then-commit facade.

The final module of Phase 2. It composes the verifier (the κ-tiering pipeline)
with the Phase 1 storage substrate into a single atomic operation:

    propose an edge → verify → reject-or-store.

The facade does three things the lower layers cannot do alone:

    1. **Verify** — run the κ-tiering pipeline (`verifier.verify`). A HARD_VETO
       rejects the edge outright: nothing is stored, and the caller gets a
       `CommitResult` with `edge=None` and `rejected=True`.

    2. **Build the signed Edge** — on a pass, construct the `Edge` record with
       the earned verdict + κ, the content-addressed `proof_hash` (the binding),
       and the signer's public key. The edge record is the *only* thing stored
       as "verified"; verdict and κ are embedded in it, not a side-channel.

    3. **Persist node payloads + commit** — store every node's canonical bytes
       in the ObjectStore (closing the Phase 1 gap where node hashes were
       registered but their claim text was not retrievable), then commit the
       edge bytes + proof blob atomically via `Storage.commit_edge_tx`.

Boundary discipline: this module uses only the *public* Storage API
(`Storage.commit_edge_tx`, `Storage.objects.put`) and the public primitives
(`hashing`, `serialization`). It never touches `sqlite3`, `pathlib`, `_conn`,
or any private `Storage` attribute.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from arxdb.storage.append_log import LogEntry
from arxdb.storage.hashing import Hash, hash_bytes
from arxdb.storage.storage import Storage

from .schema import Edge, EdgeType, Node
from .verifier import VerificationResult, verify


@dataclass(frozen=True)
class CommitResult:
    """The facade's outcome for a single edge proposal.

    `verification` carries the full κ-tiering result (verdict, κ, which
    predicate fired, which checker ran). `edge`, `edge_hash`, and `log_entry`
    are populated only on a store (i.e. when `rejected` is False); on a
    rejection they are all `None`.
    """

    verification: VerificationResult
    edge: Edge | None
    edge_hash: Hash | None
    log_entry: LogEntry | None

    @property
    def rejected(self) -> bool:
        """True iff the edge was vetoed and nothing was stored."""
        return self.verification.rejected


def verify_and_commit(
    storage: Storage,
    signer_pubkey: bytes,
    premises: Sequence[Node],
    conclusion: Node,
    rule: str,
    edge_type: EdgeType,
    proof_bytes: bytes | None = None,
    timeout_seconds: float = 5.0,
) -> CommitResult:
    """Verify an edge proposal, then reject-or-store it.

    On a HARD_VETO the edge is rejected: nothing is written, and the returned
    `CommitResult` has `edge=None`, `edge_hash=None`, `log_entry=None`,
    `rejected=True`.

    On a pass (PASS or SOFT_FLAG) the edge is built, its node payloads are
    persisted, and it is committed atomically. The returned `CommitResult`
    carries the built `Edge`, its content address, and the signed log entry.

    `signer_pubkey` is the public key of the party doing the verification; it
    is embedded in the edge record (and therefore covered by the content
    address and the log signature) as the "who verified it" attestation.
    """
    # 1. Verify.
    result = verify(
        premises, conclusion, rule, edge_type, proof_bytes, timeout_seconds
    )

    # 2. Reject on veto — nothing is stored.
    if result.rejected:
        return CommitResult(
            verification=result, edge=None, edge_hash=None, log_entry=None
        )

    # 3. Build the signed Edge.
    premise_hashes = [p.node_id() for p in premises]
    conclusion_hash = conclusion.node_id()
    proof_hash = hash_bytes(proof_bytes) if proof_bytes is not None else None

    edge = Edge(
        type=edge_type,
        premises=tuple(premise_hashes),
        conclusion=conclusion_hash,
        rule=rule,
        proof_hash=proof_hash,
        verdict=result.verdict,
        kappa=result.kappa,
        signer_pubkey=signer_pubkey,
    )

    # 4. Persist node payloads (close the Phase 1 gap): anyone holding a
    #    node_hash can retrieve the human-readable claim text.
    for p in premises:
        storage.objects.put(p.node_bytes())
    storage.objects.put(conclusion.node_bytes())

    # 5. Commit atomically: edge bytes + proof blob, graph + log in one tx.
    edge_hash, log_entry = storage.commit_edge_tx(
        premises=list(premise_hashes),
        conclusion=conclusion_hash,
        edge_data=edge.edge_bytes(),
        proof=proof_bytes,
    )

    return CommitResult(
        verification=result,
        edge=edge,
        edge_hash=edge_hash,
        log_entry=log_entry,
    )
