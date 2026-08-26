# ArxDB — Phase 5 Plan Review & Sign-Off (PHASE5_PLAN.md)

**Review Date:** 2026-08-26  
**Document Reviewed:** [`PHASE5_PLAN.md`](file:///home/ubuntu/arxdb/PHASE5_PLAN.md) (v0.1)  
**Related Documents:** [`DESIGN.md`](file:///home/ubuntu/arxdb/DESIGN.md) (§Layer 3), [`DECISIONS.md`](file:///home/ubuntu/arxdb/DECISIONS.md) (ADR-002, ADR-004, ADR-010), [`STORAGE_API.md`](file:///home/ubuntu/arxdb/STORAGE_API.md), [`PHASE4_PLAN.md`](file:///home/ubuntu/arxdb/PHASE4_PLAN.md)

---

## 1. Executive Assessment & Formal Sign-Off

[`PHASE5_PLAN.md`](file:///home/ubuntu/arxdb/PHASE5_PLAN.md) defines the **Attestation Layer**: the mechanism that provides cryptographic provenance, tamper-evidence, proof binding, and blockchain anchoring.

### Assessment: **APPROVED / SIGN-OFF GRANTED** ✅

The plan exhibits exceptional engineering discipline:
1. **Precise Scoping**: Recognizes that Phase 1 already delivered the low-level cryptographic primitives (`keys.py`, `append_log.py`, `merkle.py`, `object_store.py`). Phase 5 focuses strictly on composing these into high-level attestation guarantees and building the missing **Genesis Roster**.
2. **Three Invariant Guarantees**: Concrete implementation of the three Layer 3 guarantees:
   - **Provenance**: Resolving raw 32-byte public keys to named contributors (Skye, Lark, etc.).
   - **Integrity**: Verifying Ed25519 signatures and Merkle log hash-chain continuity.
   - **Binding & Access**: Ensuring proof blobs are content-addressed within `Edge.proof_hash` and retrievable without external dependencies.
3. **Trustless Anchor Seam**: Defines a clean, self-describing `AnchorRecord` enabling any external auditor to verify the full history against a single published `root_hash` without trusting the local database.

---

## 2. Deep-Dive Technical Review

### 2.1 The Genesis Roster (`src/arxdb/attestation/roster.py`)

* **Purpose**: Binds human/agent identities to Ed25519 public keys (ADR-010).
* **Properties**:
  - **Deterministic Content-Addressing**: Canonical CBOR encoding ensures `roster_hash = hash_bytes(canonical_encode(roster))` is immutable and self-authenticating.
  - **Bidirectional Resolution**: $O(1)$ forward lookup `resolve(agent_id) -> pubkey` and reverse lookup `identify(pubkey) -> agent_id`.
  - **Genesis Identities**: Pre-populated with the 5 core agents: `Skye`, `Lark`, `Thea`, `Theoria`, and `Axioma`.

```python
@dataclass(frozen=True)
class Roster:
    entries: dict[str, bytes]  # agent_id -> 32-byte pubkey

    def resolve(self, agent_id: str) -> bytes | None: ...
    def identify(self, pubkey: bytes) -> str | None: ...
    def roster_bytes(self) -> bytes: ...
    def roster_hash(self) -> Hash: ...
```

---

### 2.2 The Verification API (`src/arxdb/attestation/attest.py`)

#### A. Edge Attestation Verification (`verify_edge_attestation`)
Composes the three guarantees for an individual inference step:
1. **Provenance Check**: `signer_agent_id = roster.identify(edge.signer_pubkey)`. Fails if signer is not in the roster.
2. **Integrity Check**: Verifies that the edge's serialized bytes match its hash and that the corresponding log entry carries a valid Ed25519 signature from `edge.signer_pubkey`.
3. **Binding & Access Check**:
   - If `edge.proof_hash is None`: `proof_bound=True`, `proof_intact=True`.
   - If `edge.proof_hash is not None`: Retrieves `proof_bytes = storage.objects.get(edge.proof_hash)` and checks `hash_bytes(proof_bytes) == edge.proof_hash`.

```python
@dataclass(frozen=True)
class AttestationResult:
    edge_hash: Hash
    signer_agent_id: str | None
    signature_valid: bool
    proof_bound: bool
    proof_intact: bool
    ok: bool  # True iff signature_valid and proof_bound and proof_intact and (signer_agent_id is not None)
```

#### B. Full History Verification (`verify_history`)
* Walks the entire sequence `seq = 0 .. N-1` in `storage.log`:
  1. Verifies each entry's Ed25519 signature against `entry.signer_pubkey`.
  2. Verifies hash-chain linkage: `entry[i].prev_log_hash == hash_bytes(entry[i-1].payload)`.
  3. Rebuilds the Merkle tree over all entry hashes and asserts `recomputed_root == trusted_root`.
* **Result**: Completely trustless audit from a single 34-byte root hash.

#### C. The Anchor Seam (`anchor`)
* Produces the `AnchorRecord` ready for anchoring to L1/L2 blockchains:
```python
@dataclass(frozen=True)
class AnchorRecord:
    root_hash: Hash
    entry_count: int
    timestamp_ns: int
    roster_hash: Hash

    def anchor_bytes(self) -> bytes: ...
    def anchor_hash(self) -> Hash: ...
```

---

## 3. Decisions & Open Questions Review

| Question | Assessment & Decision | Rationale |
| :--- | :--- | :--- |
| **Q1: Roster Scope** | **Accept Recommendation**: 5 named agents (`Skye`, `Lark`, `Thea`, `Theoria`, `Axioma`) with Lark as founder. | Directly implements ADR-010, giving real provenance to seed corpus inference steps. |
| **Q2: Roster Authentication** | **Accept Recommendation**: Content-addressed and committed at genesis; `roster_hash` anchored in `AnchorRecord`. | Clean, self-contained, and avoids circular key-signing ceremonies. Trust in `root_hash` transitively validates the roster. |
| **Q3: Key Rotation / Revocation** | **Accept Recommendation**: Defer full ceremony for v0.1; keep Roster append-only. | Pragmatic scope control. Key rotation can be added in Phase 7 as a superseding log entry without breaking existing Merkle proofs. |

---

## 4. Module Architecture & Layout

```
src/arxdb/attestation/
    __init__.py     # Exports: Roster, AttestationResult, AnchorRecord,
                    #          verify_edge_attestation, verify_history, anchor, genesis_roster
    roster.py       # Roster class, serialization, resolve/identify, genesis roster definition
    attest.py       # verify_edge_attestation, verify_history, anchor, get_edge_proof

tests/
    test_roster.py  # Roster serialization, identity lookups, content addressing
    test_attest.py  # Three guarantees, tamper detection, history walk, anchor records
```

---

## 5. Phase 5 Test Plan Matrix

| Test Module | Test Case | Target Assertion |
| :--- | :--- | :--- |
| **`test_roster.py`** | `test_roster_round_trip` | `Roster.from_bytes(roster.roster_bytes()) == roster` |
| | `test_roster_content_addressed` | Equal rosters produce identical `roster_hash`; distinct entries produce distinct hashes. |
| | `test_resolve_and_identify` | Forward and reverse lookup work for all 5 genesis agents. |
| | `test_unknown_agent_returns_none` | Unregistered agent ID or pubkey returns `None`. |
| **`test_attest.py`** | `test_genuine_edge_attestation` | `verify_edge_attestation` returns `ok=True`, `signer_agent_id="Skye"`. |
| | `test_tampered_proof_detected` | Mutating proof blob in ObjectStore causes `proof_intact=False` and `ok=False`. |
| | `test_tampered_edge_payload_detected`| Mutating edge bytes causes `signature_valid=False` and `ok=False`. |
| | `test_unknown_signer_fails_provenance`| Edge signed by unknown key returns `signer_agent_id=None` and `ok=False`. |
| | `test_verify_history_success` | `verify_history(storage, trusted_root)` returns `True` for valid log. |
| | `test_tampered_history_fails` | Mutating any log entry or breaking hash chain causes `verify_history` to return `False`. |
| | `test_anchor_record_integrity` | `anchor(storage, roster)` produces valid `AnchorRecord` containing current `root_hash` and `roster_hash`. |

---

## 6. Sign-Off Checklist

- [x] Scope boundary validated: low-level crypto reused from Phase 1.
- [x] Three guarantees (Provenance, Integrity, Binding) fully formalized.
- [x] Genesis Roster design approved (5 agents).
- [x] Trustless history verification algorithm verified.
- [x] Anchor record format approved for future blockchain commits.

**Phase 5 implementation is fully approved to proceed.**
