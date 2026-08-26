"""Attestation layer (Phase 5) — provenance, integrity, binding.

Turns the Phase 1 signing primitives into the attestation layer: the thing
that lets an external party answer, about any edge in the graph —

  1. Who signed it?   (provenance — a *named* agent via the roster)
  2. Has it been altered since? (integrity — signature + hash chain)
  3. Is the proof bound to this edge and intact? (binding)

Modules:
    roster  — the genesis roster (agent_id <-> pubkey)
    attest  — verify_edge_attestation, verify_history, anchor
"""

from .attest import (
    AnchorRecord,
    AttestationResult,
    anchor,
    commit_roster,
    verify_edge_attestation,
    verify_history,
)
from .roster import Roster

__all__ = [
    "Roster",
    "AttestationResult",
    "AnchorRecord",
    "verify_edge_attestation",
    "verify_history",
    "anchor",
    "commit_roster",
]
