"""schema.py — Node and Edge dataclasses, enums, canonical serialization.

The heart of Phase 2. A `Node` is an immutable claim (proposition + domain +
polarity); an `Edge` is a typed inference step carrying its verdict, κ-strength,
and — crucially — a content-addressed `proof_hash` that binds the proof to this
specific edge.

Both are content-addressed: `node_id = hash_bytes(canonical_encode(node))` and
`edge_hash = hash_bytes(canonical_encode(edge))`. Canonical CBOR (sorted keys,
definite-length forms) guarantees that structurally equal records produce
byte-identical encodings, so the content address is stable.

Boundary discipline: this module imports only the *public* storage primitives
(`hashing`, `serialization`) — never `sqlite3`, `pathlib`, or any private
`Storage` attribute.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from arxdb.storage.hashing import Hash, hash_bytes
from arxdb.storage.serialization import canonical_decode, canonical_encode


class EdgeType(str, Enum):
    """The 7-way edge taxonomy (resolved Q3: keep all seven)."""

    DEFINITION = "definition"
    DEDUCTION = "deduction"
    NUMERICAL = "numerical"
    REDUCTION = "reduction"
    REFUTATION = "refutation"
    ANALOGY = "analogy"
    CITATION = "citation"


class Kappa(str, Enum):
    """Discrete κ-strength scale. Ordering lives in `kappa.py`."""

    K0 = "K0"
    K1 = "K1"
    K2 = "K2"
    K3 = "K3"
    K_INF = "K_INF"


class Verdict(str, Enum):
    """ELENCHUS + checker outcome for an edge."""

    PASS = "PASS"
    SOFT_FLAG = "SOFT_FLAG"
    HARD_VETO = "HARD_VETO"


@dataclass(frozen=True)
class Node:
    """An immutable claim (proposition).

    Truth is *not* a field: whether a claim is proven / unproven / contradicted
    is a graph-derived property (computed in Phase 3), not static state. If a
    truth field were embedded in the content address, proving a claim would
    change its hash and break every edge referencing it. The Node carries only
    the invariant proposition.

    `polarity` distinguishes "P" (True) from "¬P" (False) as *content*, so a
    claim and its negation are distinct nodes without a mutable truth field.
    """

    claim: str
    domain: str
    polarity: bool = True

    def to_canonical(self) -> dict:
        """The canonical Python structure for content-addressing."""
        return {
            "claim": self.claim,
            "domain": self.domain,
            "polarity": self.polarity,
        }

    def node_bytes(self) -> bytes:
        """Deterministic CBOR encoding of this node."""
        return canonical_encode(self.to_canonical())

    def node_id(self) -> Hash:
        """Content address of this node."""
        return hash_bytes(self.node_bytes())

    @classmethod
    def from_bytes(cls, data: bytes) -> "Node":
        """Reconstruct a Node from its canonical CBOR bytes."""
        d = canonical_decode(data)
        return cls(claim=d["claim"], domain=d["domain"], polarity=d["polarity"])


@dataclass(frozen=True)
class Edge:
    """A typed inference step: premises → conclusion by `rule`.

    `proof_hash` is the content hash of the proof blob — the binding that fixes
    ADR-002's "you cannot swap in a proof for a different claim" property. The
    proof is bound to *this* edge (these premises, this conclusion, this rule),
    and the whole edge record — including `proof_hash` — is signed in the log.
    """

    type: EdgeType
    premises: tuple[Hash, ...]
    conclusion: Hash
    rule: str
    proof_hash: Hash | None
    verdict: Verdict
    kappa: Kappa
    signer_pubkey: bytes

    def to_canonical(self) -> dict:
        """The canonical Python structure for content-addressing."""
        return {
            "type": self.type.value,
            "premises": list(self.premises),
            "conclusion": self.conclusion,
            "rule": self.rule,
            "proof_hash": self.proof_hash,
            "verdict": self.verdict.value,
            "kappa": self.kappa.value,
            "signer_pubkey": self.signer_pubkey,
        }

    def edge_bytes(self) -> bytes:
        """Deterministic CBOR encoding of this edge."""
        return canonical_encode(self.to_canonical())

    def edge_hash(self) -> Hash:
        """Content address of this edge."""
        return hash_bytes(self.edge_bytes())

    @classmethod
    def from_bytes(cls, data: bytes) -> "Edge":
        """Reconstruct an Edge from its canonical CBOR bytes."""
        d = canonical_decode(data)
        return cls(
            type=EdgeType(d["type"]),
            premises=tuple(Hash(p) for p in d["premises"]),
            conclusion=Hash(d["conclusion"]),
            rule=d["rule"],
            proof_hash=Hash(d["proof_hash"]) if d["proof_hash"] is not None else None,
            verdict=Verdict(d["verdict"]),
            kappa=Kappa(d["kappa"]),
            signer_pubkey=d["signer_pubkey"],
        )
