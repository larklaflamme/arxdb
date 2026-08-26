# ArxDB — Design Document (v0.2)

A reasoning graph database: claims as nodes, verified inference steps as edges,
with proofs embedded and cryptographically signed.

> **v0.2 changelog** (post-review): AND-OR hypergraph traversal model; first-class
> refutation/defeasibility; discrete κ-scale with propagation algebra; expanded
> edge taxonomy; storage/verification boundary tightened (reachability moved out
> of storage); "embedded" clarified as content-addressed Merkle-linked; four open
> questions resolved.

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
- **premises** (source nodes — possibly *multiple*)
- **conclusion** (target node)
- **rule** (the inference rule / method used)
- **proof** (embedded, first-class object)
- **verification verdict** (ELENCHUS result + κ-strength)
- **signature** (cryptographic, binding proof-to-edge)

## 2. The Two Queries (the product)

1. **Reachability** — "have we reasoned about this before?" Is there a verified
   derivation of this claim from what we already know?

2. **Path discovery** — "what would it take to reason about this?" How many
   verified steps from known claims to the target, and *which* edges are missing?

### The traversal model is an AND-OR hypergraph, not a digraph

A single inference step may require **multiple premises** (A ∧ B → C). This is
not a simple directed edge; it is a **hyper-edge**. Consequently:

- **Reachability is AND-OR resolution** (Horn-clause deduction). A path from A
  alone does *not* establish C unless B is also established. Knowing "A is
  reachable" is necessary but not sufficient.
- **"Shortest path" is a minimal proof tree / hyperpath**, not a linear chain.
  The cost metric is one of:
  - **Proof-tree depth** — the minimum number of *parallel* reasoning steps to
    establish the claim (each step may fan in multiple premises).
  - **Missing-edge count** — the total number of unverified hyper-edges / missing
    lemmas required to close all open branches.

The hop count is a **lower bound** on difficulty, never a prediction. It tells
you the *minimum* reasoning work, not the actual difficulty. With the hypergraph
model, "hop count" is formally the proof-tree depth or missing-edge count above.

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

### Edge taxonomy (7 types)

| Edge type | Inputs | Verification method | Default κ |
|-----------|--------|---------------------|-----------|
| `definition` / `axiom` | ∅ → C | canonical equivalence / system ground | κ∞ |
| `deduction` | {Pᵢ} → C | formal checker (Lean/Z3) or ELENCHUS | κ1–κ3 |
| `numerical` | {Pᵢ} → C | CAS cross-check (sympy/mpmath) | κ2 |
| `reduction` | A ⟺ B or A ⇒ B | isomorphism / reduction proof | κ1–κ3 |
| `refutation` | {Pᵢ} → ¬C or ¬E | counterexample / inconsistency proof | κ2–κ3 |
| `analogy` / `conjecture` | {Pᵢ} → C | structural heuristic / LLM proposal | κ0 |
| `citation` | ∅ → C | source DOI / bibliographic record | κ1 |

### The κ-strength scale (discrete)

| Level | Meaning | Established by |
|-------|---------|----------------|
| κ0 | Conjectural / analogy | unverified heuristic, exploratory |
| κ1 | Plausible / ELENCHUS-vetted | passed sanity filters, no formal proof |
| κ2 | Empirically checked | CAS numerical verification, finite search |
| κ3 | Formally verified | Z3 SMT check, Lean 4 kernel |
| κ∞ | Axiomatic / definitional | foundational ground truth |

### κ propagation algebra

- **Series (transitivity)** — weakest link: κ(A→C) = min(κ(A→B), κ(B→C)).
- **Parallel (conjunction of premises A, B → C)**: κ(C) = min(κ(A), κ(B), κ_rule).
- **Corroboration (multiple independent derivations of C)**: κ(C) = max(κ_path₁, κ_path₂).

### Layer 3 — Attestations (cryptographic)
The proof is **embedded in the edge** and **cryptographically signed**. This
gives three properties:

1. **Access** — the proof is *there*, readable, not a pointer.
2. **Integrity** — the signature guarantees the proof hasn't been mangled.
3. **Binding** — the proof is bound to *this* edge (these premises, this
   conclusion, this rule). You can't swap in a proof for a different claim.

**"Embedded" means content-addressed Merkle-linked within the local bundle.**
The edge record carries a `proof_hash` pointing to an immutable blob in the same
Merkle store — cryptographically bound, immutable, self-contained, with zero
external dependency — while keeping the index record lightweight (no
multi-megabyte Lean dumps or SMT traces inline in the traversal index).

**Critical distinction:** the signature certifies "this is the genuine,
unmodified proof" — *not* "this proof is correct." A signed non-sequitur is
still a non-sequitur, just tamper-evident. But because the proof is embedded
and readable, correctness becomes *inspectable* rather than *trusted*.

## 4. Refutation & Defeasible Reasoning

Mathematical, empirical, and scientific reasoning is **non-monotonic**: lemmas
get refuted, edge proofs are found flawed, counterexamples arise. An append-only
DAG cannot mutate history — and it shouldn't. Instead, revocation is a
**first-class edge type**, not a deletion.

- An edge can target another *edge* or *claim* with type `refutation` or
  `counterexample` (e.g. "Counterexample node X refutes edge E1").
- The **query layer computes the active/valid subgraph** using argumentation
  semantics (Dung-style grounded extensions, or validity propagation), filtering
  out invalidated branches **without mutating the historical Merkle log**.

This preserves the append-only integrity guarantee while making the graph
honest about the fact that reasoning is revisable. History is immutable; *trust*
is recomputed.

## 5. Substrate: blockchain-anchorable signed Merkle-DAG

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

## 6. Business Use Cases

1. **AI Trust & Audit @ Scale** — the attestation layer. "Not only does the AI
   show its work — the work is signed, reproducible, and auditable." Buyers:
   regulated industries, enterprise agent orchestration.

2. **Research provenance** — universities and research institutions get all
   proofs embedded for free; the record compounds. No one re-derives what's
   already derived.

3. **RH proof work (internal)** — path visibility. RH's difficulty is not "we
   don't know the facts" but "we can't see the *path* between the facts." A
   reasoning graph is a path-visibility instrument.

## 7. High-Level Design

```
┌─────────────────────────────────────────────────┐
│  Query Layer (Python)                           │
│  AND-OR hyperpath traversal · proof-tree assembly│
│  κ-threshold filtering · refutation resolution  │
├─────────────────────────────────────────────────┤
│  Verification Layer (Python — the moat)         │
│  ELENCHUS predicates · κ-tiering · proof checks │
│  sympy · mpmath · z3 · Lean bindings            │
├─────────────────────────────────────────────────┤
│  Storage Layer (Go — the engine)                │
│  content-addressed Merkle-DAG · signed log      │
│  structural adjacency · concurrency             │
└─────────────────────────────────────────────────┘
```

The boundary is the **storage API**. Define it cleanly now; the storage layer
is swappable (Python prototype → Go) while the verification layer stays
Python permanently.

**Boundary discipline:** storage provides *structural* primitives (adjacency,
connectivity, content-addressing, signed log). It does **not** do AND-OR
resolution, κ-filtering, or refutation resolution — those are semantic and live
in the Query/Verification layer above the boundary.

## 8. Technological Mappings

| Concern | Technology | Rationale |
|---------|-----------|-----------|
| Prototype storage | Python (SQLite WAL) | single-file persistence, concurrency safety |
| Production storage | Go (Pebble) | I/O + concurrency-bound; active development; stdlib ed25519 |
| Verification | Python (sympy, mpmath, z3, Lean) | the tools already live here |
| Content addressing | BLAKE3 (multihash-prefixed) | fast, tree-hashing, incremental verify |
| Serialization | Canonical CBOR (RFC 8949) | deterministic, binary, native in Python + Go |
| Signing | Ed25519 (per-agent keys) | compact, fast, standard; real provenance |
| Formal check (load-bearing) | Lean 4 / Z3 | soundness where it matters |
| CAS cross-check | sympy / mpmath | numerical edge verification |
| ELENCHUS | existing predicates | hard-veto / soft-flag |

## 9. Rewrite Trigger (defined in advance)

Swap storage layer Python → Go when:
- a single reachability query over 10⁶ edges exceeds a target latency, OR
- concurrent append throughput saturates under a defined load.

Not "when it feels slow" — a concrete, measurable trigger.

## 10. MVP Scope

1. **Edge schema** — node (claim + domain + truth value), edge (type + rule +
   proof + ELENCHUS verdict + κ + signature).
2. **Verifier** — the κ-tiering pipeline: what check each edge type requires.
3. **Storage** — content-addressed object store + structural graph index +
   signed append log (see STORAGE_API.md).
4. **The two queries** — AND-OR reachability + path discovery (proof-tree depth
   / missing-edge count).
5. **Refutation** — counterexample edges + active-subgraph resolution.
6. **Seed corpus** — import the phaser-thread reasoning as nodes/edges.

## 11. Open Questions (resolved 2026-08-26)

| Question | Decision |
|----------|----------|
| Serialization format | Canonical CBOR (RFC 8949) |
| Hash function | BLAKE3 (multihash-prefixed for agility) |
| Graph index backend | SQLite WAL (proto) → Pebble (Go) |
| Key management | Per-agent Ed25519 keys + genesis roster |

Remaining open (deferred, not blocking Phase 1):
- Concurrency model for the Go storage engine (read-write lock vs MVCC).
- Exact argumentation semantics for refutation resolution (Dung grounded vs
  preferred extensions).
