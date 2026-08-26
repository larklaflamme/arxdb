# PHASE5_PLAN.md — Attestation Layer (provenance + blockchain seam)

**Version:** v0.1
**Status:** Draft — awaiting Lark's decisions on Q1–Q3
**Depends on:** Phase 1 (signing), Phase 2 (proofs), Phase 4 (seed corpus)
**ADR basis:** ADR-002 (proof embedded + signed), ADR-004 (anchorable DAG), ADR-010 (per-agent keys + genesis roster)

---

## 1. What Phase 5 is

Phase 5 turns the *already-built* signing primitives into the **attestation
layer**: the thing that lets an external party answer three questions about any
edge in the graph —

1. **Who signed it?** (provenance — a *named* agent, not an anonymous key)
2. **Has it been altered since?** (integrity — signature + hash chain)
3. **Is the proof bound to this edge and intact?** (binding — proof_hash in the
   content address, blob retrievable and matching)

The three guarantees from DESIGN.md §Layer 3: **access, integrity, binding**.

**Critical scoping fact:** Phase 1 already built the *cryptographic primitives*.
`keys.py` (Ed25519 sign/verify), `append_log.py` (signed hash chain, Merkle
root, inclusion proofs, `verify_entry`), `merkle.py` (RFC 6962), `object_store.py`
(content-addressed proof blobs), and `schema.py` (`Edge.signer_pubkey` +
`Edge.proof_hash`). Phase 5 does **not** re-implement any of that. It builds the
two things that are still missing:

1. **The roster** — ADR-010's "genesis roster" that binds a *name* to a *key*.
   This was decided but never built. Without it, `signer_pubkey` is an anonymous
   32-byte blob, and "Skye verified this" is indistinguishable from "some key
   verified this."
2. **The attestation-verification API** — public functions that *compose* the
   primitives into the three guarantees, plus the **anchor record** that makes
   `root_hash` the single blockchain-anchor point.

---

## 2. The gap, precisely (what exists vs. what's missing)

| Guarantee | Primitive (Phase 1) | Missing (Phase 5) |
|-----------|---------------------|-------------------|
| **Provenance** | `Edge.signer_pubkey` (32 bytes) | name ↔ key binding (the roster) |
| **Integrity** | `verify_entry` (single entry), hash chain | full-chain walk from a trusted root |
| **Binding** | `proof_hash` in edge content address | retrieve-blob-and-check accessor |
| **Anchor** | `root_hash()` | a clean, self-describing anchor record |

The single most important missing piece is the **roster**, because provenance is
the whole point of the attestation layer (ADR-010: "per-agent keys make
provenance *real*"), and provenance is meaningless without a name↔key binding.

---

## 3. Deliverables

### 3.1 `attestation/roster.py` — the genesis roster

A `Roster` maps `agent_id: str ↔ pubkey: bytes`. It is:

- **Content-addressed** — the roster is a canonical CBOR record whose hash is
  its identity, so a given roster is self-authenticating by its content address.
- **Append-only** — key rotation/revocation is a *new binding appended*, never a
  mutation (preserves the append-only guarantee; see Q3).
- **The trust anchor** — the roster's content address is committed as the
  genesis log entry, so it is anchored in the hash chain and verifiable from
  `root_hash`.

Public API:
```
Roster(entries: dict[str, bytes])          # agent_id -> pubkey
    to_canonical() -> dict
    roster_bytes() -> bytes
    roster_hash() -> Hash
    resolve(agent_id) -> bytes | None      # name -> key
    identify(pubkey) -> str | None         # key -> name (reverse lookup)
    from_bytes(data) -> Roster
```

### 3.2 `attestation/attest.py` — the verification API

The public functions that compose the primitives into the three guarantees:

```
verify_edge_attestation(edge, storage) -> AttestationResult
    # provenance: signer_pubkey resolves to a named agent in the roster
    # integrity:  the edge's log entry signature verifies
    # binding:    proof_hash -> blob retrievable, hash_bytes(blob) == proof_hash

verify_history(storage, trusted_root) -> bool
    # walk seq 0..N: each entry's signature verifies AND prev_log_hash links
    # AND the Merkle root over entry hashes == trusted_root

anchor(storage) -> AnchorRecord
    # { root_hash, entry_count, timestamp, roster_hash } — the single
    # self-describing record to commit to a blockchain later (ADR-004)
```

`AttestationResult` carries: `signer_agent_id`, `signature_valid`, `proof_bound`,
`proof_intact`, and a single `ok` boolean (all three guarantees hold).

### 3.3 `storage.py` — one small extension

`commit_edge_tx` already stores the proof blob in the ObjectStore. Add a
`get_proof(edge_hash) -> bytes | None` accessor (or expose it via the attestation
module) so the proof is *retrievable* — the "access" guarantee made explicit.

---

## 4. Exit criteria (from ROADMAP, made concrete)

1. **"Signed by X, unaltered since"** — `verify_edge_attestation` returns
   `signer_agent_id="Skye"` and `signature_valid=True` for a genuine edge, and
   `signature_valid=False` for a tampered edge.
2. **Tampering invalidates the signature** — flip one byte in a proof blob or an
   edge payload; `verify_edge_attestation` reports `ok=False` (binding or
   integrity fails).
3. **Root hash verifies the whole history** — `verify_history(storage, root)`
   returns `True` for an untampered log and `False` after any entry is altered,
   using *only* the trusted root (no trust in the local DB).

---

## 5. The three decisions I need (Q1–Q3)

**Q1 — Roster scope.** Which agents get keys in the genesis roster?
- **Recommendation:** the five named agents — Skye, Lark, Thea, Theoria, Axioma
  — with Lark as the founder/root identity. This matches ADR-010's explicit list
  and gives the seed corpus real provenance ("Skye verified E1" vs "Lark
  proposed N7").

**Q2 — Roster authentication.** How is the genesis roster itself trusted?
- **Recommendation:** content-addressed + committed as the genesis log entry.
  The roster's hash is *in* the hash chain, so trusting `root_hash` transitively
  trusts the roster. No separate "founder signs the roster" ceremony for v0.1 —
  the anchor is the trust root, and the roster hangs off it. (This is the
  "turtles all the way down" answer: the anchor is the bottom turtle.)

**Q3 — Key rotation/revocation.** Build now, or defer?
- **Recommendation:** **defer**, but design the roster so a key can be
  *superseded* (append a new binding, never mutate). Flag as a known gap: if an
  agent's key is compromised, v0.1 has no revocation ceremony — provenance for
  that agent's post-compromise edges is unsound until rotation is built. This is
  the honest failure mode to name, not hide.

---

## 6. Module layout

```
src/arxdb/attestation/
    __init__.py
    roster.py       # Roster: agent_id <-> pubkey, genesis roster record
    attest.py       # verify_edge_attestation, verify_history, anchor

tests/
    test_roster.py  # roster round-trip, resolve/identify, content-addressing
    test_attest.py  # the three guarantees + tamper detection + history walk
```

---

## 7. Test plan

**test_roster.py**
- `test_roster_round_trip` — roster_bytes → from_bytes → identical entries
- `test_roster_content_addressed` — same entries → same roster_hash; reorder → different
- `test_resolve_identify` — resolve("Skye") == pubkey; identify(pubkey) == "Skye"
- `test_unknown_agent` — resolve("nobody") is None; identify(unknown_key) is None

**test_attest.py**
- `test_genuine_edge_attests` — verify_edge_attestation → ok=True, signer="Skye"
- `test_tampered_proof_detected` — flip a byte in the proof blob → ok=False (binding fails)
- `test_tampered_edge_detected` — flip a byte in the edge payload → ok=False (integrity fails)
- `test_unknown_signer` — edge signed by a key not in the roster → provenance fails
- `test_verify_history_clean` — verify_history(storage, root) → True
- `test_verify_history_tampered` — alter one log entry → verify_history → False
- `test_anchor_record` — anchor() returns root_hash + roster_hash + count

---

## 8. Adjacent frames & failure modes (breadth)

**Adjacent frame — Certificate Transparency / Sigstore.** The architecture
"signed append-only log + Merkle root + external anchor" is *exactly* RFC 6962
(Certificate Transparency) and the Sigstore software-supply-chain model. We are
building a lightweight, single-party version of the same thing. Naming this is
useful: it means the design is *proven*, not novel, and the known attacks
(append-only violation, split-view, key compromise) are documented in that
literature.

**Failure mode 1 — conflating "signed" with "correct."** ADR-002 already names
this: a signed non-sequitur is still a non-sequitur. The attestation layer
certifies *provenance and integrity*, never *validity*. The plan must keep this
line sharp — `verify_edge_attestation` says nothing about whether the proof is
*right*, only that it's *genuine and unaltered*.

**Failure mode 2 — key compromise without rotation.** If an agent's key leaks,
every edge "signed by" that agent is now suspect, and without a revocation
ceremony the roster can't express that. This is the honest gap behind Q3. The
mitigation is to design the roster append-only from day one so rotation is a
*new binding*, not a breaking change.

**Failure mode 3 — the roster is itself unanchored.** If the roster is trusted
"because we say so," provenance collapses to a self-assertion. The fix is Q2's
answer: the roster's content address is committed as the genesis log entry, so
it is anchored in the same hash chain as everything else. Trust in `root_hash`
is the *only* trust required.

---

## 9. What would strengthen or refute this plan

- **Strengthen:** a real multi-agent scenario (Skye signs an edge, Lark signs
  another, verify each resolves to the correct name) — this is the seed corpus
  re-run with per-agent keys, and it's the natural Phase 5 acceptance test.
- **Refute:** if `verify_history` cannot be made to work from *only* the trusted
  root (i.e., it secretly trusts the local DB), then the "trustless" claim in
  ADR-004 is false and the anchor story needs rework. This is the first thing to
  test.
- **Open question for later:** whether the anchor record should include a
  timestamp commitment (for the blockchain-anchor use case) — deferred, since
  ADR-004 explicitly defers the chain itself.
