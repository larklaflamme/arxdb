# ArxDB — Decision Log (ADR)

Architecture Decision Records. Each entry: what we decided, why, and what we
rejected. This is the single source of truth for "why is it this way."

---

## ADR-001 — Reasoning graph, not knowledge graph

**Status:** Accepted (2026-08-26)

**Decision:** Nodes are *claims* (propositions with truth value + domain), not
entities or concepts. Edges are *typed inference steps*: "B follows from A by
rule R," carrying a proof obligation.

**Why:** A knowledge graph stores asserted facts; a reasoning graph stores
*derived* claims with the *how* attached. The product value is in the proof
obligation — an edge that can be checked, refuted, or found to be a
non-sequitur.

**Rejected:** Knowledge-graph framing (entities + relations). It can't carry
the verification moat.

---

## ADR-002 — Proof embedded in the edge, cryptographically signed

**Status:** Accepted (2026-08-26)

**Decision:** The proof is a first-class object *embedded* in the edge, and the
signature binds proof-to-edge. Three properties: **access** (readable, not a
pointer), **integrity** (not mangled), **binding** (can't swap in a proof for a
different claim).

**Why:** This collapses the "reproducibility is expensive" problem. The proof is
stored, not just committed — you *inspect* it rather than re-run it. The
signature certifies "genuine, unmodified proof," *not* "correct proof" — but
because the proof is embedded and readable, correctness becomes inspectable
rather than trusted.

**Rejected:** Storing a commitment/hash and re-running verification on demand
(costly, and conflates integrity with validity).

---

## ADR-003 — Tiered verification (Option C)

**Status:** Accepted (2026-08-26)

**Decision:** Verification is tiered by edge type. LLM proposes; ELENCHUS
hard-veto predicates reject non-sequiturs/category errors/self-model leaks;
formal checkers (Lean/Z3/CAS) run *only on load-bearing edges*; every edge gets
a κ-strength label.

**Why:** Formal checking is expensive. Running it on every edge is waste; running
it on none is unsound. Tiering puts the expensive check where it matters.

**Rejected:** Uniform formal verification (too costly), or no verification
(no moat).

---

## ADR-004 — Blockchain-anchorable signed Merkle-DAG (not blockchain now)

**Status:** Accepted (2026-08-26)

**Decision:** Substrate is a content-addressed, append-only, signed Merkle-DAG.
Blockchain is *deferred*, not rejected — the DAG is designed to be anchored to a
chain later (commit root hash → trustless verifiability).

**Why:** Everything the ontology needs (tamper-evidence, provenance,
append-only, ordering) is satisfied by a signed Merkle-DAG. Blockchain uniquely
adds *decentralized consensus among mutually-distrusting parties* — a governance
model, not a storage property. We don't have untrusted parties yet.

**The network effect** ("longer chain = more verified proofs") is real and is
the reason the *public multi-institution* version is valuable — but it's a
property of shared append-only storage, not of consensus. Design for the future,
build for now.

**Rejected:** Building on a blockchain now (paying consensus cost before we have
untrusted parties).

---

## ADR-005 — Python prototype → Go storage (split, not rewrite)

**Status:** Accepted (2026-08-26)

**Decision:** Two layers with a clean storage-API boundary. Verification layer
stays Python *permanently* (the formal tools live there). Storage layer is
prototyped in Python, then reimplemented in **Go** behind the same interface.

**Why Go over Rust:** The storage layer is I/O-bound and concurrency-bound
(hashing, disk/network I/O, graph traversal), not compute-bound. Go's goroutines
and fast compile solve the concurrency problem; Rust's zero-cost abstractions
solve a CPU problem we don't have. Decisive: a content-addressed signed
Merkle-DAG is structurally a minimal IPFS, and the reference IPFS implementation
is Go (`go-ipfs`); `crypto/ed25519` is in the Go stdlib.

**Rejected:** Rust (CPU-bound optimization for a non-CPU-bound workload; no
IPFS ecosystem advantage). Also rejected: "rewrite everything in Go" — the
verification layer stays Python because that's where sympy/mpmath/z3/Lean live.

---

## ADR-006 — Rewrite trigger defined in advance

**Status:** Accepted (2026-08-26)

**Decision:** Swap storage Python → Go when (a) a single reachability query over
10⁶ edges exceeds a target latency, OR (b) concurrent append throughput
saturates under a defined load. Not "when it feels slow."

**Why:** A concrete, measurable trigger ensures the rewrite happens for the
right reason, not as premature optimization.

---

## ADR-007 — Canonical CBOR serialization

**Status:** Accepted (2026-08-26)

**Decision:** Nodes and edges are serialized to **canonical CBOR (RFC 8949)** —
deterministic key sorting, binary compact, native support in Python (`cbor2`)
and Go (`fxamacker/cbor`).

**Why:** Content-addressing requires *deterministic* byte output so the same
logical object hashes identically across implementations. CBOR avoids JSON's
float/whitespace/key-order ambiguity and is more compact than JSON.

**Rejected:** JSON (float/whitespace ambiguity, no canonical form without extra
discipline), msgpack (no canonical ordering guarantee).

---

## ADR-008 — BLAKE3 content addressing (multihash-prefixed)

**Status:** Accepted (2026-08-26)

**Decision:** Content addressing uses **BLAKE3**, with a multihash format-byte
prefix for future hash agility.

**Why:** BLAKE3 outperforms SHA-256 by roughly an order of magnitude and supports
tree-hashing and incremental verification — both useful for a Merkle-DAG. The
multihash prefix lets us add SHA-256 later (e.g. for FIPS compliance in the
enterprise AI-audit use case) without breaking the addressing scheme.

**Rejected:** SHA-256 as the default (slower; FIPS is a *future* requirement,
not a current one — we can add it as an option when it becomes a hard constraint).

---

## ADR-009 — SQLite WAL prototype index → BadgerDB/Pebble (Go)

**Status:** Accepted (2026-08-26)

**Decision:** The prototype graph index uses **SQLite with WAL mode** (single-file
persistence, concurrency safety, easy relational querying). The Go production
engine uses **BadgerDB or Pebble** (embedded LSM-tree key-value stores).

**Why:** SQLite WAL gives us persistence and concurrency safety in Python with
zero operational overhead during prototyping. BadgerDB/Pebble are the Go-native
equivalents — embedded, fast, no external service — matching the "boring,
correct, maintainable" storage-layer goal.

**Rejected:** In-memory-only adjacency (no persistence across restarts), and a
separate database *service* (operational complexity we don't need for an
embedded engine).

---

## ADR-010 — Per-agent Ed25519 keys + genesis roster

**Status:** Accepted (2026-08-26)

**Decision:** Signing uses **per-agent Ed25519 keys** (Skye, Lark, Thea, Theoria,
Axioma, …), with a **genesis roster** recording each agent's public key.

**Why:** Per-agent keys make provenance *real* — "Skye verified this" is a
different, stronger claim than "the org verified this." The genesis roster is the
trust anchor: it binds an identity to a key at the start, so later signatures
are attributable to a named contributor, not an anonymous key.

**Rejected:** A single org key (provenance collapses to "the org did it" — loses
the individual-verifier signal that is the whole point of the attestation layer).

---

## Remaining open decisions (deferred, not blocking Phase 1)

- Concurrency model for the Go storage engine (read-write lock vs MVCC).
- Exact argumentation semantics for refutation resolution (Dung grounded vs
  preferred extensions).

---

## ADR-009 amendment — Pebble (not BadgerDB) for the Go storage engine

**Status:** Accepted (2026-08-26)

**Decision:** The Go production storage engine uses **Pebble**
(`github.com/cockroachdb/pebble`), not BadgerDB.

**Why:** Pebble is actively developed (maintained by CockroachDB), has better
write amplification, and is the forward-looking choice. BadgerDB is in
maintenance mode. For a storage-only swap (append + read-by-key), Pebble's
transaction API gives us the atomic `CommitEdgeTx` we need.

**Rejected:** BadgerDB (maintenance mode, less active development).

**Note:** This resolves the ADR-009 "BadgerDB or Pebble" ambiguity. The
remaining open decision (concurrency model) is now answered by Pebble's
snapshot + batch semantics.
