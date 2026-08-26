# ArxDB — Architecture & Design Review (DESIGN.md)

**Review Date:** 2026-08-26  
**Document Reviewed:** [`DESIGN.md`](file:///home/ubuntu/arxdb/DESIGN.md) (v0.1)  
**Related Documents:** [`README.md`](file:///home/ubuntu/arxdb/README.md), [`DECISIONS.md`](file:///home/ubuntu/arxdb/DECISIONS.md), [`STORAGE_API.md`](file:///home/ubuntu/arxdb/STORAGE_API.md), [`ROADMAP.md`](file:///home/ubuntu/arxdb/ROADMAP.md)

---

## 1. Executive Summary

The foundational thesis of ArxDB is compelling, well-reasoned, and timely:
1. **Reasoning Graph vs. Knowledge Graph**: Shifting from *asserted facts* to *procedural derivations with proof obligations* addresses a critical blind spot in modern AI orchestration and formal mathematics tooling.
2. **Pragmatic Substrate Selection**: Leveraging a signed Merkle-DAG today while deferring on-chain consensus avoids premature blockchain complexity while retaining future anchoring capabilities.
3. **Layer Separation**: Isolating the fast, I/O-bound storage engine (Python prototype → Go) from the Python-native verification ecosystem (Lean 4, Z3, SymPy, ELENCHUS) establishes a clean architectural boundary.

This document identifies key architectural nuances, graph-theoretic considerations, and design refinements to resolve as the project moves into Phase 1 implementation.

---

## 2. Core Architectural Review & Feedback

### 2.1 Graph Semantics: Multi-Premise Inference is an AND-OR Hypergraph

In [`DESIGN.md` §1 & §2](file:///home/ubuntu/arxdb/DESIGN.md#L26-L45) and [`STORAGE_API.md` §2](file:///home/ubuntu/arxdb/STORAGE_API.md#L55-L72), edges carry `premises: list[Hash]` and `conclusion: Hash`.

```
Premise A ──┐
            ├─► [Inference Rule R] ──► Conclusion C
Premise B ──┘
```

* **The Challenge**: In a standard directed graph, reachability is single-path connectivity ($A \to B \to C$). In a reasoning graph where an inference step requires multiple premises ($A \land B \to C$), reachability is **AND-OR hypergraph resolution** (or Horn-clause deduction). Knowing a path from $A$ alone does *not* prove $C$ unless $B$ is also established.
* **Impact on Hop Count & Path Discovery**:
  * "Shortest path" is not a single linear chain; it is a **minimal proof tree / hyperpath**.
  * Hop count as a lower bound should be formally defined as either:
    - **Proof Tree Depth**: minimum parallel reasoning steps to establish the claim.
    - **Missing Edge Count**: total unverified hyper-edges / missing lemmas required to close all open branches.
* **Recommendation**: Explicitly specify the traversal model as an **AND-OR DAG (Hypergraph)** in [`DESIGN.md` §2](file:///home/ubuntu/arxdb/DESIGN.md#L35-L45).

---

### 2.2 Proof Refutation, Invalidation, & Defeasible Reasoning

[`DESIGN.md` §3](file:///home/ubuntu/arxdb/DESIGN.md#L48-L82) defines append-only Merkle storage. However, mathematical, empirical, and scientific reasoning is non-monotonic: lemmas can be refuted, edge proofs can be found flawed, or counterexamples may arise.

```
       ┌───────────┐
       │ Premise A │
       └─────┬─────┘
             │ (Edge E1: Deduction)
             ▼
       ┌───────────┐      [Counterexample Node X]
       │  Claim B  │                 │
       └─────┬─────┘                 │ (Edge E2: Refutation)
             │                       ▼
             │ ◄────────── [Veto / Invalidation of E1]
             ▼
       ┌───────────┐
       │  Claim C  │
       └───────────┘
```

* **The Challenge**: If an append-only DAG cannot mutate historical edges, how does the system revoke trust in a compromised derivation?
* **Recommendation**: Introduce a first-class **Refutation / Defeasibility mechanism**:
  * An edge can target another *edge* or *claim* with type `refutation` or `counterexample`.
  * The query layer computes the **active / valid subgraph** using argumentation semantics (e.g., Dung-style grounded extensions or validity propagation), filtering out invalidated branches without mutating the historical Merkle log.

---

### 2.3 The $\kappa$-Strength Algebra & Compositional Propagation

[`DESIGN.md` §3](file:///home/ubuntu/arxdb/DESIGN.md#L52-L67) specifies a $\kappa$-strength label on every edge, but leaves the algebra open in §10.

* **Discrete Scale Recommendation**:
  * $\kappa_0$: **Conjectural / Analogy** (unverified heuristics, exploratory).
  * $\kappa_1$: **Plausible / ELENCHUS-vetted** (passed sanity filters, no formal proof).
  * $\kappa_2$: **Empirically Checked** (CAS numerical verification, finite search, SymPy/mpmath).
  * $\kappa_3$: **Formally Verified** (Z3 SMT check, Lean 4 kernel verified).
  * $\kappa_\infty$: **Axiomatic / Definitional** (foundational ground truth).

* **Propagation Calculus**:
  * **Series (Transitivity)**: Weakest-link principle:
    $$\kappa(A \to C) = \min(\kappa_{A \to B}, \kappa_{B \to C})$$
  * **Parallel (Conjunction of premises $A, B \to C$)**:
    $$\kappa(C) = \min(\kappa(A), \kappa(B), \kappa_{\text{rule}})$$
  * **Corroboration (Multiple independent derivations of $C$)**:
    $$\kappa(C) = \max(\kappa_{\text{path}_1}, \kappa_{\text{path}_2})$$

---

### 2.4 Refining the Storage vs. Verification Boundary

[`STORAGE_API.md` §2](file:///home/ubuntu/arxdb/STORAGE_API.md#L66-L72) currently places `reachable()` and `shortest_path()` inside the Storage interface.

```
┌──────────────────────────────────────────────────────────────┐
│  Verification & Query Layer (Python)                         │
│  - AND-OR hyperpath traversal & proof-tree assembly          │
│  - κ-strength threshold filtering (e.g., κ ≥ κ₂)             │
│  - Refutation filtering & active status resolution           │
├──────────────────────────────────────────────────────────────┤
│  Storage Layer (Go / Python) — Dumb & Fast Engine            │
│  - ObjectStore: put(bytes), get(hash)                        │
│  - GraphIndex: add_node, add_edge, predecessors, successors  │
│  - AppendLog: append(entry, sig), root_hash()                │
└──────────────────────────────────────────────────────────────┘
```

* **The Challenge**: If Storage is "dumb" and knows nothing about $\kappa$-strength, validity, or AND-OR deduction, a naive `Storage.reachable()` cannot evaluate whether a path is valid under a given $\kappa$-threshold or whether all premises in a hyper-edge are satisfied.
* **Recommendation**:
  * Keep the Storage `GraphIndex` purely structural (`predecessors`, `successors`, raw topological reachability).
  * Move **Proof-Tree Reachability** and **$\kappa$-filtered path discovery** into the Verification/Query layer, or provide a parameter for edge-filtering callbacks.

---

### 2.5 Proof Embedding vs. Merkle-Linked Blobs

[`DESIGN.md` §3](file:///home/ubuntu/arxdb/DESIGN.md#L68-L82) emphasizes that proofs are *embedded, readable, first-class objects*, not dangling URLs.

* **Distinction**:
  * In a content-addressed Merkle-DAG, an edge containing `proof_hash: Hash` where `proof_hash` points to an immutable blob stored in the same local Merkle store is cryptographically bound, immutable, and self-contained.
  * Storing multi-megabyte Lean environment dumps or SMT traces directly inline within the JSON/CBOR edge record could bloat the graph index traversal.
* **Recommendation**: Clarify in [`DESIGN.md` §3](file:///home/ubuntu/arxdb/DESIGN.md#L68-L82) that "embedded" means **content-addressed Merkle-linked within the local bundle**, ensuring zero external dependency while keeping index records lightweight.

---

### 2.6 Edge Taxonomy Expansion

The current 4-type list (`citation`, `deduction`, `numerical`, `analogy`) in [`DESIGN.md` §3](file:///home/ubuntu/arxdb/DESIGN.md#L61-L67) can be strengthened by adding:

| Edge Type | Inputs | Verification Method | Default $\kappa$ |
| :--- | :--- | :--- | :--- |
| **`definition` / `axiom`** | $\emptyset \to C$ | Canonical equivalence / System ground | $\kappa_\infty$ |
| **`deduction`** | $\{P_i\} \to C$ | Formal checker (Lean 4 / Z3) or ELENCHUS | $\kappa_1 - \kappa_3$ |
| **`numerical`** | $\{P_i\} \to C$ | CAS cross-check (SymPy / mpmath) | $\kappa_2$ |
| **`reduction`** | $A \iff B$ or $A \implies B$ | Isomorphism / reduction proof | $\kappa_1 - \kappa_3$ |
| **`refutation`** | $\{P_i\} \to \neg C$ or $\neg E$ | Counterexample / inconsistency proof | $\kappa_2 - \kappa_3$ |
| **`analogy` / `conjecture`**| $\{P_i\} \to C$ | Structural heuristic / LLM proposal | $\kappa_0$ |
| **`citation`** | $\emptyset \to C$ | Source DOI / cryptographic bibliographic record | $\kappa_1$ |

---

## 3. Resolving the Four Open Questions ([DESIGN.md §10](file:///home/ubuntu/arxdb/DESIGN.md#L189-L195))

| Open Question | Recommended Decision | Rationale |
| :--- | :--- | :--- |
| **1. Serialization Format** | **Canonical CBOR** (RFC 8949) | Deterministic key sorting, binary compact, native support in Python (`cbor2`) and Go (`fxamacker/cbor`). Avoids JSON float/whitespace ambiguity. |
| **2. Hash Function** | **BLAKE3** | Outperforms SHA-256 by an order of magnitude; supports tree-hashing and incremental verification. (Add a format byte prefix for multihash agility). |
| **3. Graph Index Backend** | **In-memory + SQLite WAL** (Proto) $\to$ **BadgerDB / Pebble** (Go) | SQLite WAL in Python gives single-file persistence, concurrency safety, and easy relational querying before Go migration. |
| **4. Key Management** | **Per-Agent Ed25519 Keys + Genesis Roster** | Captures individual contributor/verifier provenance (e.g. `skye_ed25519_...`). Decentralized signatures on the append log. |

---

## 4. Actionable Checklist for Next Phases

1. **Update [`DESIGN.md`](file:///home/ubuntu/arxdb/DESIGN.md)**:
   - Formulate the traversal model as an AND-OR proof-tree / hypergraph search.
   - Include the refutation / defeasibility model.
   - Formalize the discrete $\kappa$-scale ($\kappa_0$ through $\kappa_\infty$) and propagation rules.
2. **Record Decisions in [`DECISIONS.md`](file:///home/ubuntu/arxdb/DECISIONS.md)**:
   - Canonical CBOR serialization format.
   - BLAKE3 default hashing.
   - SQLite WAL prototype indexing backend.
   - Per-agent Ed25519 signing scheme.
3. **Refine [`STORAGE_API.md`](file:///home/ubuntu/arxdb/STORAGE_API.md)**:
   - Adjust `GraphIndex` to provide structural primitives (`predecessors`, `successors`, `all_edges`) and leave semantic $\kappa$-filtering and AND-OR resolution to the Verification/Query Layer.
