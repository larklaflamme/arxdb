# ArxDB — Phase 2 Implementation Plan (v0.2)

**Goal:** the verification layer — the moat. Edge schema + κ-tiering pipeline +
ELENCHUS integration, built on the Phase 1 storage substrate, behind the
boundary discipline.

**Scope:** verification layer only. No query/traversal (Phase 3), no refutation
resolution (Phase 3), no seed corpus (Phase 4).

> **v0.2 changelog** (post-review): Node made immutable (truth is graph-derived,
> not static state); node payload persistence specified; formal-checker protocol
> with execution guardrails (timeout/memory caps); four open questions resolved;
> test-plan requirements added.

## What Phase 1 delivered (the substrate we build on)

- `storage.py` — `Storage` facade + `commit_edge_tx(premises, conclusion,
  edge_data, proof=None) -> (edge_hash, log_entry)`.
- `graph_index.py` — `register_node`, `register_edge`, `incoming_edges`,
  `outgoing_edges`, `get_connectivity` (returns `(premises, conclusion)` tuple).
- `append_log.py` — `LogEntry` with `seq, timestamp_ns, signer_pubkey,
  entry_hash, prev_log_hash, signature, payload`.
- `object_store.py`, `merkle.py`, `keys.py`, `hashing.py`, `serialization.py`.

## The boundary (non-negotiable)

Storage is dumb and fast. The verification layer:
- serializes nodes/edges to CBOR bytes and passes them to storage as opaque
  blobs;
- **never inspects storage internals** — no `sqlite3`, no `pathlib`, no `_conn`,
  no `objects.root`; only the public `Storage` API;
- owns all meaning: edge type, verdict, κ, proof binding.

This is an exit criterion, and it is *testable*: the verification modules must
not import `sqlite3` or `pathlib`, and must only reference `Storage`'s public
methods. A structural test enforces it.

## Pre-work: reconcile STORAGE_API.md (doc debt)

`STORAGE_API.md` still documents the pre-implementation signatures: `add_node`/
`add_edge`, the `EdgeConnectivity` dataclass, `commit_edge_tx` with
`signer_pubkey`/`signature` args, and `LogEntry` without `payload`. Phase 1
actually implemented `register_*`, tuple returns, `commit_edge_tx(premises,
conclusion, edge_data, proof)`, and `LogEntry` with `payload`. Reconcile the doc
to the code before Phase 2 starts — the boundary contract must match reality.

## Implementation order (each step independently testable)

1. **`schema.py`** — `Node` and `Edge` dataclasses, canonical CBOR
   serialization, `EdgeType` enum, `Kappa` enum, `Verdict` enum.
2. **`kappa.py`** — the κ scale + propagation algebra (series / parallel /
   corroboration).
3. **`elenchus.py`** — ELENCHUS adapter: hard-veto / soft-flag / pass.
4. **`checkers/`** — pluggable formal checkers behind a bounded protocol
   (`base.py`, `z3_check.py`, `cas_check.py`, `lean_check.py`, `roster.py`).
5. **`verifier.py`** — the κ-tiering pipeline: dispatch by type → run the
   right check → return `(verdict, kappa)`.
6. **`commit.py`** — verify-then-commit facade: verify → reject-or-store.

## The edge schema (the heart of Phase 2)

### Node (a claim — immutable)

```python
@dataclass(frozen=True)
class Node:
    claim: str            # the proposition, e.g. "RH ⟺ Λ ≤ 0"
    domain: str           # "math" | "physics" | "consciousness" | ...
    polarity: bool = True # True = "P", False = "¬P"
```

`node_id = hash_bytes(canonical_encode(node))` — content-addressed.

**Why no `truth_value` field:** a proposition's truth status (proven / unproven
/ contradicted) is a *graph-derived property*, not static state. If `truth_value`
were embedded in the content-address, proving a claim would change its hash and
break every edge that referenced it. The Node carries only the invariant
proposition (claim + domain + polarity); whether it is currently proven or
refuted is computed in Phase 3 by checking which verified paths / refutation
edges reach it.

**Node payload persistence:** `commit.py` must ensure `node_bytes =
canonical_encode(node)` is stored in `ObjectStore` (`storage.objects.put`) for
every node it introduces, so that anyone holding a `node_hash` can retrieve the
human-readable claim text. Phase 1's `commit_edge_tx` registers node hashes in
the graph index but does *not* store the node bytes — Phase 2 closes that gap.

### Edge (a typed inference step)

```python
@dataclass(frozen=True)
class Edge:
    type: EdgeType        # 7 values, see taxonomy
    premises: tuple[Hash] # node hashes (possibly empty for axioms/citations)
    conclusion: Hash      # node hash
    rule: str             # the inference rule / method used
    proof_hash: Hash|None # content hash of the proof blob — THE BINDING
    verdict: Verdict      # PASS | SOFT_FLAG | HARD_VETO
    kappa: Kappa          # K0 | K1 | K2 | K3 | K_INF
    signer_pubkey: bytes  # who verified it
```

`edge_bytes = canonical_encode(edge)`; `edge_hash = hash_bytes(edge_bytes)`.

**The proof binding (fixes a Phase 1 gap):** Phase 1's `commit_edge_tx` stores
the proof as an independent blob but does *not* record the edge→proof link. The
`proof_hash` field makes the binding explicit and content-addressed: the proof
is bound to *this* edge (these premises, this conclusion, this rule), and the
whole edge record — including `proof_hash` — is signed in the log. You cannot
swap in a proof for a different claim without changing `edge_hash`.

**Verdict + κ are embedded in the edge record**, so they are part of the edge's
content-addressed identity and covered by the log signature. A stored edge
carries its own verdict; "verified" is not a side-channel.

## The κ-tiering pipeline

For each edge, the verifier:

1. **ELENCHUS hard-veto** (always, every edge): category errors, non-sequiturs,
   self-model leaks. If veto → **reject** (do not store).
2. **Type-appropriate check** (dispatch by `EdgeType`):

| Edge type | Check | κ on pass |
|-----------|-------|-----------|
| `definition` / `axiom` | roster match (see resolved Q1) | κ∞ or κ1 |
| `deduction` | formal checker (z3 / lean) | κ3 |
| `numerical` | CAS cross-check (sympy / mpmath) | κ2 |
| `reduction` | isomorphism / reduction proof | κ1–κ3 |
| `refutation` | counterexample / inconsistency | κ2–κ3 |
| `analogy` / `conjecture` | none (structural heuristic only) | κ0 |
| `citation` | source DOI / bibliographic record | κ1 |

3. **Assign verdict + κ**, embed in the edge, commit via `Storage.commit_edge_tx`.

## Formal checker protocol (execution guardrails)

Formal checkers (`z3`, `sympy`/`mpmath`, `lean`) can execute arbitrary code,
consume unbounded memory, or loop forever. Every checker is bounded:

```python
@dataclass(frozen=True)
class CheckerResult:
    passed: bool
    kappa: Kappa
    details: dict[str, Any]
    error_msg: str | None = None

class BaseChecker(Protocol):
    def check(
        self,
        premises: Sequence[Node],
        conclusion: Node,
        rule: str,
        proof_bytes: bytes | None,
        timeout_seconds: float = 5.0,
    ) -> CheckerResult: ...
```

**Guardrails (non-negotiable):**
- Every external invocation (Lean subprocess, Z3 run, SymPy expansion) is
  wrapped in a strict timeout (default 5.0s) and a memory cap.
- A timeout or OOM is a **clean failure** (`passed=False`, `error_msg` set),
  never a hang and never a silent pass.

## κ propagation algebra (`kappa.py`)

- **Series (transitivity):** κ(A→C) = min(κ(A→B), κ(B→C)).
- **Parallel (conjunction of premises A, B → C):** κ(C) = min(κ(A), κ(B), κ_rule).
- **Corroboration (independent derivations of C):** κ(C) = max(κ_path₁, κ_path₂).

*Note:* the algebra is *defined* here (Phase 2), but its *application* — walking
the graph to compute a node's κ from its derivation paths — requires traversal
and belongs to Phase 3 (query). See resolved Q2.

## Resolved open questions (per review)

**Q1 — κ∞ for definitions/axioms. RESOLVED:** κ∞ only if the claim matches a
**curated roster** (`checkers/roster.py`, the "system ground" set); otherwise
κ1 (ELENCHUS-vetted only). Prevents unverified LLM-generated assertions from
masquerading as axiomatic truth and corrupting downstream min-propagation.

**Q2 — κ propagation algebra location. RESOLVED:** define the algebra in Phase 2
(`kappa.py`); apply it during traversal in Phase 3. Clean separation of algebra
definition from graph-traversal algorithms.

**Q3 — edge taxonomy. RESOLVED:** keep all 7 types (`definition`, `deduction`,
`numerical`, `reduction`, `refutation`, `analogy`, `citation`). Precise semantic
labeling; empirical usage evaluated on real data in Phase 4 (RH seed corpus).

**Q4 — verdict model. RESOLVED:** scalar κ + `refutation` edge type in Phase 2;
active-subgraph resolution (where "refuted" becomes a *computed* status) in
Phase 3. Keeps edge storage simple and append-only while allowing non-monotonic
logic resolution at query time.

## Test plan requirements (Phase 2 sign-off)

1. **`test_schema.py`** — canonical CBOR stability for `Node`/`Edge`; structural
   equality (field order / dict keys → byte-identical output); proof binding
   (altering `proof_bytes` changes `proof_hash` and invalidates `edge_hash`).
2. **`test_kappa.py`** — series min(κ3, κ1)=κ1; conjunction min(κ2, κ3, κ3)=κ2;
   corroboration max(κ1, κ3)=κ3; axiom absorption min(κ∞, κ2)=κ2.
3. **`test_elenchus.py`** — hard-veto on category error / self-model leak /
   non-sequitur; vetoed edge returns `Verdict.HARD_VETO` and is not committed.
4. **`test_checkers.py`** — CAS verifies true identities / rejects false; Z3
   verifies valid implications / rejects counter-models; timeout cleanly aborts;
   roster gives κ∞ for known axioms, κ1 for unlisted definitions.
5. **`test_verifier_pipeline.py` + `test_boundary.py`** — end-to-end
   `verify_and_commit` (reject on veto, store on pass); AST inspection asserting
   `verification/` imports no `sqlite3`/`pathlib` and touches no private
   `Storage` attributes.

## Exit criteria (Phase 2 is "done" when ALL hold)

- [ ] An edge can be added, its proof checked, and a `(verdict, κ)` assigned.
- [ ] A hard-veto edge is rejected — never stored as "verified".
- [ ] The verification layer never inspects storage internals (structural test:
      no `sqlite3`/`pathlib` imports in `verification/`).
- [ ] `proof_hash` binding: swapping the proof changes `edge_hash`.
- [ ] κ propagation algebra is correct on hand-checked examples (series /
      parallel / corroboration).
- [ ] A real end-to-end run: propose an edge → verify → commit → retrieve.
- [ ] Node payloads are retrievable from `ObjectStore` by `node_hash`.
- [ ] Checker guardrails hold: a timeout/OOM is a clean failure, not a hang.
