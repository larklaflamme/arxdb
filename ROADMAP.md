# 🗺️ ArxDB — Execution Roadmap

> Phased plan for building a reasoning graph database: claims as nodes, verified
> inference steps as edges, proofs embedded and cryptographically signed.

Each phase has a **goal**, **deliverables**, **exit criteria**, and **dependencies**.
A phase is "done" only when its exit criteria are met — not when it "feels done."

---

## Phase 0 — Foundations (✅ mostly complete)

**Goal:** Lock the design before writing code.

**Deliverables:**
- [x] `DESIGN.md` — core concept, two queries, three layers, substrate, tech mappings
- [x] `DECISIONS.md` — ADR log (Python→Go split, Go over Rust, tiered verification, etc.)
- [x] `STORAGE_API.md` — the interface boundary that makes the swap a drop-in
- [x] `README.md` — product-facing first impression
- [ ] Resolve the four open questions (serialization, hash fn, graph index, concurrency)

**Exit criteria:** All open questions answered and recorded in `DECISIONS.md`.

---

## Phase 1 — Core Storage Prototype (Python)

**Goal:** A working, content-addressed, append-only, signed store behind the
`Storage` interface — dumb and fast, no judgment.

**Deliverables:**
- Object store: `put`/`get` by BLAKE3 content hash (idempotent)
- Graph index: `add_node`/`add_edge`/`reachable`/`shortest_path` (in-memory adjacency)
- Append log: signed `append`/`root_hash` (Merkle root)
- Canonical serialization (CBOR) so content-addressing is stable
- Ed25519 signing

**Exit criteria:**
- Round-trip: put → get returns byte-identical object
- Idempotency: putting the same object twice yields the same hash, no duplicate
- `root_hash` changes iff the log changes; tampering is detectable
- Unit tests pass

**Dependencies:** Phase 0 (open questions resolved).

---

## Phase 2 — Edge Schema + Verification Pipeline (the moat)

**Goal:** The thing that makes ArxDB a *reasoning* graph, not a knowledge graph.

**Deliverables:**
- Edge type taxonomy (citation / deduction / numerical / analogy — confirm or extend)
- Proof as first-class embedded object
- ELENCHUS integration (hard-veto / soft-flag)
- κ-tiering (discrete levels — confirm scale)

**Exit criteria:**
- An edge can be added, its proof checked, and a verdict + κ assigned
- A hard-veto edge is rejected, not stored as "verified"
- The verification layer never inspects storage internals (boundary holds)

**Dependencies:** Phase 1 (needs storage to persist edges).

---

## Phase 3 — The Two Queries

**Goal:** The product. Reachability + path discovery.

**Deliverables:**
- `reachable(claim)` — "have we reasoned about this before?"
- `path_discovery(claim)` — "what would it take?" (verified hops + missing edges)
- Hop count reported as a *lower bound*, never a difficulty prediction

**Exit criteria:**
- Reachability returns correct yes/no on a seeded graph
- Path discovery returns the minimum verified hop count and names missing edges
- Queries run against the storage layer, not in-memory ad-hoc structures

**Dependencies:** Phase 2 (edges must carry verdicts for "verified path" to mean anything).

---

## Phase 4 — Seed Corpus (RH / phaser thread)

**Goal:** Prove the tool on real material — import our own reasoning.

**Deliverables:**
- Import the phaser-thread claims as nodes (zeros-as-resonances, phase-is-the-valve, etc.)
- Import the verified inference steps as edges with proofs
- A reachability query that returns a real, non-trivial answer

**Exit criteria:**
- The seeded graph answers at least one genuine "have we reasoned about this?" query
- Path discovery on an open RH claim returns a meaningful missing-edge list

**Dependencies:** Phase 3.

---

## Phase 5 — Attestation Layer (provenance + blockchain seam)

**Goal:** The three guarantees — access, integrity, provenance.

**Deliverables:**
- Proof embedded in edge, cryptographically signed, binding proof-to-edge
- Per-agent keys (Skye, Lark, sisters) — provenance, not just "the org"
- `root_hash` exposed as the single blockchain-anchor point

**Exit criteria:**
- A signed edge can be verified as "signed by X, unaltered since"
- Tampering with a proof invalidates the signature (detectable)
- The root hash is sufficient to trustlessly verify the whole history

**Dependencies:** Phase 2 (proofs) + Phase 1 (signing).

---

## Phase 6 — Go Storage Swap

**Goal:** Replace the Python storage layer with Go, behind the same interface.

**Trigger (defined in advance, not "when it feels slow"):**
- A single reachability query over 10⁶ edges exceeds target latency, OR
- Concurrent append throughput saturates under defined load.

**Deliverables:**
- Go implementation of the `Storage` interface (object store + graph index + log)
- Drop-in swap; verification layer untouched

**Exit criteria:**
- Same test suite passes against the Go backend
- Measured latency/throughput improvement on the trigger workload

**Dependencies:** Phase 1 (interface must be stable first).

---

## Phase 7 — Productization (AI Trust & Audit)

**Goal:** Turn the research tool into the product.

**Deliverables:**
- Public API (HTTP/gRPC) over the two queries
- Documentation for external users
- The AI Trust & Audit use case: reproduce a reasoning edge, verify its proof

**Exit criteria:**
- An external user can query reachability and reproduce a proof without us
- The "reproduce the proof" story works end-to-end

**Dependencies:** Phase 5 (attestation) + Phase 3 (queries).

---

## Dependency graph (summary)

```
Phase 0 ──► Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4
                 │            │
                 │            └──► Phase 5 ──► Phase 7
                 └──► Phase 6 (parallel, gated by trigger)
```

**Critical path:** 0 → 1 → 2 → 3 → 4 → 5 → 7.
**Parallelizable:** Phase 6 (Go swap) can proceed once Phase 1's interface is frozen.

---

## Open questions blocking Phase 1

1. Serialization format — CBOR vs sorted-key JSON (leaning CBOR)
2. Hash function — BLAKE3 vs SHA-256 (leaning BLAKE3; SHA-256 for FIPS later)
3. Graph index — in-memory adjacency (prototype) vs on-disk
4. Concurrency model — read-write lock vs MVCC (Go impl decision)

*Resolve these in `DECISIONS.md` before writing Phase 1 code.*
