# ArxDB — Design Document (v0.1)

A reasoning graph database: claims as nodes, verified inference steps as edges,
with proofs embedded and cryptographically signed.

## 1. Core Concept

A **knowledge graph** stores *asserted* facts ("A —is-a→ B"). The edge is a
recorded relation, true or false on its own.

A **reasoning graph** stores *derived* claims. An edge "A → B" means:

> **B follows from A by rule R.**

The edge carries a **proof obligation** — a claim that can be checked, refuted,
or found to be a non-sequitur. Edges are *procedural*: they tell you *how* to
reach a node from where you are, and whether that move is valid.

### Nodes = claims
A proposition with a truth value and a domain. Not entities, not concepts —
*claims*.

- "The zeros of ζ_N(s) drift to Re=1" — a node (a verified negative result).
- "RH ⟺ Λ ≤ 0" — a node (de Bruijn–Newman).

### Edges = typed inference steps
Each edge carries:
- **premises** (source nodes)
- **conclusion** (target node)
- **rule** (the inference rule / method used)
- **proof** (embedded, first-class object)
- **verification verdict** (ELENCHUS result + κ-strength)
- **signature** (cryptographic, binding proof-to-edge)

## 2. The Two Queries (the product)

1. **Reachability** — "have we reasoned about this before?" Is there a verified
   path to this claim from what we already know?

2. **Path discovery** — "what would it take to reason about this?" How many
   verified hops from known claims to the target, and *which* edges are missing?

The hop count is a **lower bound** on difficulty, never a prediction. It tells
you the *minimum* reasoning work, not the actual difficulty.

## 3. Three Layers

### Layer 1 — Nodes (claims)
Claim + truth value + domain. Backed by NOEMA-style formal object store.

### Layer 2 — Edges (typed inference + verification)
The verification verdict is the moat. **Tiered verification (Option C):**

- **LLM proposes** the edge and a candidate proof.
- **ELENCHUS hard-veto predicates** reject non-sequiturs, category errors,
  self-model leaks.
- **Formal checkers** (Lean, Z3, CAS) run *only on load-bearing edges*.
- **κ-strength label** on every edge: how much can you stand on it?

Edge types and their required checks:
| Edge type | Required verification |
|-----------|----------------------|
| citation | source check |
| deduction | proof check (formal or ELENCHUS) |
| numerical | CAS cross-check |
| analogy | none — labeled weak, never load-bearing |

### Layer 3 — Attestations (cryptographic)
The proof is **embedded in the edge** and **cryptographically signed**. This
gives three properties:

1. **Access** — the proof is *there*, readable, not a pointer.
2. **Integrity** — the signature guarantees the proof hasn't been mangled.
3. **Binding** — the proof is bound to *this* edge (these premises, this
   conclusion, this rule). You can't swap in a proof for a different claim.

**Critical distinction:** the signature certifies "this is the genuine,
unmodified proof" — *not* "this proof is correct." A signed non-sequitur is
still a non-sequitur, just tamper-evident. But because the proof is embedded
and readable, correctness becomes *inspectable* rather than *trusted*.

## 4. Substrate: blockchain-anchorable signed Merkle-DAG

Content-addressed, append-only, signed. This is *both*:
- the cheap thing we need now (internal reasoning graph), and
- the exact substrate that can be **anchored to a blockchain later** (commit
  the root hash to a chain → trustless verifiability of the whole history).

**Design for the future, build for now.** The Merkle-DAG is the right substrate
precisely because it's cheap today and blockchain-compatible tomorrow.

### Why not blockchain now?
Everything the ontology needs (tamper-evidence, provenance, append-only,
ordering) is satisfied by a signed Merkle-DAG. Blockchain uniquely adds
*decentralized consensus among mutually-distrusting parties* — a governance
model, not a storage property. We don't have untrusted parties yet.

### The network effect (the future value)
"Longer chain = more verified proofs." A proof verified once is verified
forever; every new contributor inherits every prior proof. This is the
*commons* argument — the reason the public multi-institution version is
valuable. It's a property of shared append-only storage, not of consensus.

## 5. Business Use Cases

1. **AI Trust & Audit @ Scale** — the attestation layer. "Not only does the AI
   show its work — the work is signed, reproducible, and auditable." Buyers:
   regulated industries, enterprise agent orchestration.

2. **Research provenance** — universities and research institutions get all
   proofs embedded for free; the record compounds. No one re-derives what's
   already derived.

3. **RH proof work (internal)** — path visibility. RH's difficulty is not "we
   don't know the facts" but "we can't see the *path* between the facts." A
   reasoning graph is a path-visibility instrument.

## 6. High-Level Design

```
┌─────────────────────────────────────────────────┐
│  Query Layer (reachability, path discovery)      │
├─────────────────────────────────────────────────┤
│  Verification Layer (Python — the moat)          │
│  ELENCHUS predicates · κ-tiering · proof checks  │
│  sympy · mpmath · z3 · Lean bindings             │
├─────────────────────────────────────────────────┤
│  Storage Layer (Go — the engine)            │
│  content-addressed Merkle-DAG · signed log       │
│  graph traversal · concurrency                   │
└─────────────────────────────────────────────────┘
```

The boundary is the **storage API**. Define it cleanly now; the storage layer
is swappable (Python prototype → Go) while the verification layer stays
Python permanently.

## 7. Technological Mappings

| Concern | Technology | Rationale |
|---------|-----------|-----------|
| Prototype storage | Python (dict/sqlite) | fast iteration on schema |
| Production storage | Go | I/O + concurrency-bound; IPFS ecosystem; stdlib ed25519 |
| Verification | Python (sympy, mpmath, z3, Lean) | the tools already live here |
| Content addressing | SHA-256 / BLAKE3 | Merkle-DAG integrity |
| Signing | Ed25519 | compact, fast, standard |
| Formal check (load-bearing) | Lean 4 / Z3 | soundness where it matters |
| CAS cross-check | sympy / mpmath | numerical edge verification |
| ELENCHUS | existing predicates | hard-veto / soft-flag |

### Why Go over Rust (decision)

The storage layer is **I/O-bound and concurrency-bound**, not compute-bound:
hashing (BLAKE3), disk I/O, network I/O, graph traversal. Rust's advantage
(zero-cost abstractions, no GC, max CPU throughput) solves a problem we don't
have. Go's advantage (goroutines, trivial concurrency, fast compile, boring and
maintainable) solves exactly the problem we do have: many agents reading and
writing concurrently, small team iterating fast.

Decisive: a content-addressed signed Merkle-DAG is structurally a minimal IPFS,
and the reference IPFS implementation is Go (`go-ipfs`). `crypto/ed25519` is in
the Go stdlib. We build on the exact toolchain that already solved our problem.

Rust would win only for (a) extreme CPU-bound performance or (b) formally
verified memory safety in the storage layer itself. Neither applies: the
correctness-critical part is the *verification* layer, which stays Python.

## 8. Rewrite Trigger (defined in advance)

Swap storage layer Python → Go when:
- a single reachability query over 10⁶ edges exceeds a target latency, OR
- concurrent append throughput saturates under a defined load.

Not "when it feels slow" — a concrete, measurable trigger.

## 9. MVP Scope

1. **Edge schema** — node (claim + domain + truth value), edge (type + rule +
   proof + ELENCHUS verdict + κ + signature).
2. **Verifier** — the κ-tiering pipeline: what check each edge type requires,
   and which can be automated.
3. **Two queries** — reachability, and path discovery with hop-count as lower
   bound.

Seed corpus: the RH phaser thread (~15 files of real reasoning with real
negative results, derivations, and numerical checks). Ground truth already on
disk.

## 10. Open Questions

- Storage API shape (what exactly does the verification layer need from storage?)
- Edge type taxonomy (is the 4-type list complete?)
- κ-strength scale (discrete levels vs continuous?)
- Signature scheme and key management (who signs? per-agent keys?)
