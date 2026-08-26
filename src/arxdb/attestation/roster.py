"""roster.py — the genesis roster: agent_id <-> pubkey bindings.

The roster is the trust anchor of the attestation layer (ADR-010). It binds a
*human-readable agent name* to an Ed25519 public key, so that a `signer_pubkey`
on an edge resolves to a *named* agent ("Skye verified this") rather than an
anonymous 32-byte blob.

The roster is:

  - **content-addressed** — its identity is `roster_hash()`, the BLAKE3
    multihash of its canonical CBOR encoding, so a given roster is
    self-authenticating by its content address.
  - **append-only** — bindings are an *ordered list*; key rotation/revocation
    is a *new binding appended* (never a mutation), so `resolve` returns the
    latest binding for an agent. Rotation is deferred to a later phase, but the
    ordering is designed in now so it is a data change, not a schema change.

Public API (Phase 5):
    Roster(entries: dict[str, bytes])          # agent_id -> pubkey (insertion-ordered)
        to_canonical() -> dict
        roster_bytes() -> bytes
        roster_hash() -> Hash
        resolve(agent_id: str) -> bytes | None  # name -> key (latest binding)
        identify(pubkey: bytes) -> str | None  # key -> name (reverse lookup)
        from_bytes(data: bytes) -> Roster      # classmethod
"""

from __future__ import annotations

from dataclasses import dataclass, field

from arxdb.storage.hashing import Hash, hash_bytes
from arxdb.storage.serialization import canonical_decode, canonical_encode

PUBLIC_KEY_SIZE = 32


@dataclass(frozen=True)
class Roster:
    """An ordered set of agent_id -> pubkey bindings (the genesis roster).

    `entries` is insertion-ordered (Python dict semantics) and treated as
    immutable after construction. Order is meaningful: append-only rotation
    appends new bindings, and `resolve` returns the latest.
    """

    entries: dict[str, bytes] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for agent_id, pubkey in self.entries.items():
            if not isinstance(agent_id, str) or not agent_id:
                raise ValueError(
                    f"agent_id must be a non-empty str, got {agent_id!r}"
                )
            if not isinstance(pubkey, bytes) or len(pubkey) != PUBLIC_KEY_SIZE:
                got = len(pubkey) if isinstance(pubkey, bytes) else type(pubkey)
                raise ValueError(
                    f"pubkey for {agent_id!r} must be {PUBLIC_KEY_SIZE} bytes, "
                    f"got {got}"
                )

    def to_canonical(self) -> dict:
        """The canonical structure for content-addressing.

        Bindings are an *ordered list* of [agent_id, pubkey] pairs in insertion
        order. A `version` field future-proofs the encoding.
        """
        return {
            "version": 1,
            "bindings": [
                [agent_id, pubkey] for agent_id, pubkey in self.entries.items()
            ],
        }

    def roster_bytes(self) -> bytes:
        """Deterministic CBOR encoding of this roster."""
        return canonical_encode(self.to_canonical())

    def roster_hash(self) -> Hash:
        """Content address of this roster."""
        return hash_bytes(self.roster_bytes())

    def resolve(self, agent_id: str) -> bytes | None:
        """The public key bound to `agent_id` (latest binding), or None."""
        return self.entries.get(agent_id)

    def identify(self, pubkey: bytes) -> str | None:
        """The agent_id bound to `pubkey`, or None.

        For provenance, a *superseded* key still identifies the agent who held
        it (historical attribution), so this returns the first agent whose
        binding matches. In v0.1 each agent has exactly one key, so the lookup
        is unambiguous.
        """
        for agent_id, pk in self.entries.items():
            if pk == pubkey:
                return agent_id
        return None

    @classmethod
    def from_bytes(cls, data: bytes) -> "Roster":
        """Reconstruct a Roster from its canonical CBOR bytes."""
        d = canonical_decode(data)
        entries = {agent_id: bytes(pubkey) for agent_id, pubkey in d["bindings"]}
        return cls(entries=entries)
