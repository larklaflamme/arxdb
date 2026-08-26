"""attest.py — the attestation-verification API.

Composes the Phase 1 primitives (Ed25519 signatures, the signed hash chain,
the Merkle root, the content-addressed proof blobs) into the three guarantees
of DESIGN.md §Layer 3:

  1. **provenance** — who signed it (a *named* agent via the roster)
  2. **integrity**  — has it been altered since (signature + hash chain)
  3. **binding**    — is the proof bound to this edge and intact

Public API (Phase 5):
    verify_edge_attestation(edge, storage, roster) -> AttestationResult
    verify_history(storage, trusted_root) -> bool
    commit_roster(storage, roster) -> LogEntry | None
    anchor(storage, roster) -> AnchorRecord

Boundary discipline: this module uses only the *public* Storage API
(`storage.log.get`, `storage.log.verify_entry`, `len(storage.log)`,
`storage.objects.get`, `storage.log.root_hash`) and the public primitives
(`hashing`, `serialization`, `merkle`). It never touches `sqlite3`, `pathlib`,
`_conn`, or any private `Storage` attribute.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from arxdb.storage.append_log import GENESIS_PREV_HASH, LogEntry
from arxdb.storage.hashing import Hash, hash_bytes
from arxdb.storage.merkle import root_hash
from arxdb.storage.serialization import canonical_encode
from arxdb.storage.storage import Storage
from arxdb.verification.schema import Edge

from .roster import Roster


@dataclass(frozen=True)
class AttestationResult:
    """The outcome of verifying an edge's attestation.

    `ok` is True iff all three guarantees hold: the signer resolves to a named
    agent, the signature is valid, and the proof (if any) is bound and intact.
    """

    signer_agent_id: str | None
    signature_valid: bool
    proof_bound: bool
    proof_intact: bool

    @property
    def ok(self) -> bool:
        return (
            self.signer_agent_id is not None
            and self.signature_valid
            and self.proof_bound
            and self.proof_intact
        )


@dataclass(frozen=True)
class AnchorRecord:
    """The single self-describing record to commit to a blockchain (ADR-004).

    Carries the Merkle root (the trust anchor), the entry count, a timestamp,
    and the roster's content address — everything an external party needs to
    verify the whole history from this one record.
    """

    root_hash: Hash
    entry_count: int
    timestamp_ns: int
    roster_hash: Hash

    def to_canonical(self) -> dict:
        return {
            "version": 1,
            "root_hash": self.root_hash,
            "entry_count": self.entry_count,
            "timestamp_ns": self.timestamp_ns,
            "roster_hash": self.roster_hash,
        }

    def anchor_bytes(self) -> bytes:
        """Deterministic CBOR encoding of this anchor record."""
        return canonical_encode(self.to_canonical())

    def anchor_hash(self) -> Hash:
        """Content address of this anchor record."""
        return hash_bytes(self.anchor_bytes())


def _find_log_entry(storage: Storage, edge_hash: Hash):
    """The log entry whose content hash is `edge_hash`, or None.

    The edge's content address (`edge.edge_hash()`) equals the log entry's
    `entry_hash` because `commit_edge_tx` stores `edge.edge_bytes()` as the
    payload. Walking the log is O(N); fine for v0.1.
    """
    for seq in range(len(storage.log)):
        entry = storage.log.get(seq)
        if entry.entry_hash == edge_hash:
            return entry
    return None


def verify_edge_attestation(
    edge: Edge, storage: Storage, roster: Roster
) -> AttestationResult:
    """Verify an edge's provenance, integrity, and proof binding.

    provenance: `edge.signer_pubkey` resolves to a named agent in `roster`.
    integrity:  the edge's log entry signature verifies.
    binding:    `edge.proof_hash` (if any) resolves to a retrievable blob whose
                content hash matches.
    """
    # provenance
    signer_agent_id = roster.identify(edge.signer_pubkey)

    # integrity — find the log entry and verify its signature
    entry = _find_log_entry(storage, edge.edge_hash())
    signature_valid = entry is not None and storage.log.verify_entry(entry)

    # binding — proof blob retrievable and matching its content address
    if edge.proof_hash is None:
        proof_bound = True
        proof_intact = True
    else:
        blob = storage.objects.get(edge.proof_hash)
        proof_bound = blob is not None
        proof_intact = blob is not None and hash_bytes(blob) == edge.proof_hash

    return AttestationResult(
        signer_agent_id=signer_agent_id,
        signature_valid=signature_valid,
        proof_bound=proof_bound,
        proof_intact=proof_intact,
    )


def verify_history(storage: Storage, trusted_root: Hash) -> bool:
    """Verify the whole log from *only* the trusted root.

    Walks seq 0..N and checks, for every entry:
      - its signature verifies (integrity of the entry),
      - its `prev_log_hash` links to the previous entry's hash (chain integrity),
      - the Merkle root over all entry hashes equals `trusted_root`.

    No trust in the local DB: any tampering (altered payload, broken link,
    forged signature) makes this return False.
    """
    n = len(storage.log)
    entry_hashes: list[Hash] = []
    prev = Hash(GENESIS_PREV_HASH)
    for seq in range(n):
        entry = storage.log.get(seq)
        if entry is None:
            return False
        if not storage.log.verify_entry(entry):
            return False
        if entry.prev_log_hash != prev:
            return False
        prev = entry.entry_hash
        entry_hashes.append(entry.entry_hash)
    return root_hash(entry_hashes) == trusted_root


def anchor(storage: Storage, roster: Roster) -> AnchorRecord:
    """Build the self-describing anchor record for the current log state."""
    return AnchorRecord(
        root_hash=storage.log.root_hash(),
        entry_count=len(storage.log),
        timestamp_ns=time.time_ns(),
        roster_hash=roster.roster_hash(),
    )


def commit_roster(storage: Storage, roster: Roster) -> LogEntry | None:
    """Commit the roster as the genesis log entry (idempotent).

    The roster is committed as entry 0 so that `root_hash` — the Merkle root
    over all entry hashes — transitively commits to the roster. Trusting the
    anchor's `root_hash` therefore means trusting the roster, with no separate
    "founder signs the roster" ceremony (ADR-010 / plan Q2).

    Idempotent:
      - empty log  -> append the roster, return the new entry;
      - entry 0 is already the roster (same content hash) -> return it;
      - otherwise  -> return None (the log is non-empty and not the roster;
        the caller must not silently re-anchor a different history).
    """
    if len(storage.log) == 0:
        return storage.log.append(roster.roster_bytes())
    entry0 = storage.log.get(0)
    if entry0 is not None and entry0.entry_hash == roster.roster_hash():
        return entry0
    return None
