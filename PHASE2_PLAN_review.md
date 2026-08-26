# ArxDB — Phase 2 Implementation Plan Review (PHASE2_PLAN.md)

**Review Date:** 2026-08-26  
**Document Reviewed:** [`PHASE2_PLAN.md`](file:///home/ubuntu/arxdb/PHASE2_PLAN.md)  
**Related Documents:** [`STORAGE_API.md`](file:///home/ubuntu/arxdb/STORAGE_API.md), [`DECISIONS.md`](file:///home/ubuntu/arxdb/DECISIONS.md), [`DESIGN.md`](file:///home/ubuntu/arxdb/DESIGN.md), [`PROJECT_STRUCTURE.md`](file:///home/ubuntu/arxdb/PROJECT_STRUCTURE.md)

---

## 1. Executive Summary

[`PHASE2_PLAN.md`](file:///home/ubuntu/arxdb/PHASE2_PLAN.md) defines the core moat of ArxDB: the **verification layer**. It successfully translates the conceptual design into an actionable, modular engineering plan.

### Key Strengths of the Plan:
1. **Explicit Proof Binding**: Resolving Phase 1's loose proof storage by embedding `proof_hash: Hash | None` directly inside the signed, content-addressed `Edge` record binds premises, conclusion, rule, and proof cryptographically.
2. **Strict Boundary Discipline**: Enforcing that `src/arxdb/verification/` talks *only* to the public `Storage` API via AST-based structural tests preserves the swappability of the Go storage engine.
3. **Sound Tiering Pipeline**: The two-stage verification (ELENCHUS hard-veto filter followed by type-dispatched formal checking) balances performance with mathematical rigor.

Below is a detailed analysis of architectural nuances, resolutions for the 4 open questions, and concrete recommendations for execution.

---

## 2. Architectural Nuances & Design Refinements

### 2.1 Node Immutability & Proposition Polarity

In [`PHASE2_PLAN.md` § Edge Schema](file:///home/ubuntu/arxdb/PHASE2_PLAN.md#L58-L65):
```python
Node:
    claim: str            # proposition, e.g. "RH ⟺ Λ ≤ 0"
    domain: str           # "math" | "physics" | ...
    truth_value: enum     # TRUE | FALSE | UNKNOWN | CONTRADICTED
```

* **The Challenge**: If `node_hash = hash_bytes(canonical_encode(node))`, embedding a mutable property like `truth_value` into the content-addressed hash creates a major issue:
  - If a proposition is initialized as `UNKNOWN` and later proven `TRUE`, changing `truth_value` changes its `node_hash`.
  - All existing edges that referenced the initial `node_hash` would break or point to an obsolete node!
* **Recommendation**:
  - `Node` should represent the **invariant proposition / claim**:
    ```python
    @dataclass(frozen=True)
    class Node:
        claim: str            # The mathematical / empirical proposition
        domain: str           # Domain tag ("math", "physics", etc.)
        polarity: bool = True # True for positive claim "P", False for negated claim "¬P"
    ```
  - Whether a proposition is currently proven, unproven, or contradicted is a **graph-derived property** (evaluated in Phase 3 by checking if valid paths or refutation edges lead to it), *not* static state inside the node's content-address.

---

### 2.2 Persisting `Node` Payloads in `ObjectStore`

* **The Gap in Phase 1 Integration**:
  - In Phase 1, `Storage.commit_edge_tx` registers node hashes in SQLite `GraphIndex` (`nodes` table), and stores `edge_data` and `proof` in `ObjectStore`.
  - However, `Storage` does not automatically store the `Node` object bytes themselves.
* **Recommendation**:
  - In `commit.py` (or via a helper `register_node(node: Node)`), ensure `node_bytes = canonical_encode(node)` is stored in `ObjectStore` via `storage.objects.put(node_bytes)` whenever a node is introduced.
  - This guarantees that anyone holding a `node_hash` can retrieve the human-readable claim text from storage.

---

### 2.3 Formal Checker Protocol & Execution Guardrails

In [`PHASE2_PLAN.md` § checkers/](file:///home/ubuntu/arxdb/PHASE2_PLAN.md#L49):
Formal checkers (`z3`, `sympy`/`mpmath`, `lean`) can execute arbitrary code, consume unbounded memory, or enter non-terminating loops.

* **Recommendation**: Define a strict `Checker` protocol with execution bounds:
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
* **Guardrails**:
  - All external checker invocations (Lean sub-processes, Z3 solver runs, SymPy expansions) must be wrapped in strict execution timeouts (default: 5.0s) and memory caps.

---

## 3. Review of the Four Open Questions

| Question | Evaluation & Recommendation | Rationale |
| :--- | :--- | :--- |
| **Q1: $\kappa_\infty$ for Definitions / Axioms** | **Accept Proposal**: $\kappa_\infty$ only for curated Genesis/System Ground roster; otherwise default to $\kappa_1$. | Prevents unverified LLM-generated assertions from masquerading as axiomatic truth and corrupting downstream $\min$-propagation. |
| **Q2: $\kappa$ Algebra Location** | **Accept Proposal**: Define algebra functions in Phase 2 (`kappa.py`); apply during traversal in Phase 3. | Clean separation of algebra definition (`min_series`, `min_conjunction`, `max_corroboration`) from graph traversal algorithms. |
| **Q3: Edge Taxonomy (7 Types)** | **Accept Proposal**: Keep all 7 types (`definition`, `deduction`, `numerical`, `reduction`, `refutation`, `analogy`, `citation`). | Provides precise semantic labeling; empirical usage can be evaluated on real data in Phase 4 (RH seed corpus). |
| **Q4: Verdict Model & Refutations** | **Accept Proposal**: Scalar $\kappa$ + `refutation` edge type in Phase 2; active subgraph resolution in Phase 3. | Keeps edge storage simple and append-only while allowing non-monotonic logic resolution during query time. |

---

## 4. Module-by-Module Implementation Blueprint

```
src/arxdb/verification/
├── __init__.py
├── schema.py         # Node, Edge, EdgeType, Kappa, Verdict dataclasses + CBOR
├── kappa.py          # Kappa scale, comparison, and propagation functions
├── elenchus.py       # Hard-veto & soft-flag filter predicates
├── checkers/
│   ├── __init__.py
│   ├── base.py       # BaseChecker protocol & CheckerResult
│   ├── z3_check.py   # SMT-LIB / Z3 solver checker
│   ├── cas_check.py  # SymPy & mpmath numerical / algebraic checker
│   ├── lean_check.py # Lean 4 kernel / Lake environment runner
│   └── roster.py     # Curated genesis roster for κ_INF definitions
├── verifier.py       # Pipeline dispatcher: ELENCHUS → Checker → (verdict, κ)
└── commit.py         # Verification facade: verify_and_commit(storage, edge, ...)
```

---

## 5. Phase 2 Test Plan Requirements

To achieve sign-off for Phase 2, the test suite (`tests/`) should include:

1. **`test_schema.py`**:
   - Canonical CBOR serialization stability for `Node` and `Edge`.
   - Structural equality: swapping field order or dict keys yields byte-identical output.
   - Proof binding: altering `proof_bytes` changes `proof_hash` and invalidates `edge_hash`.

2. **`test_kappa.py`**:
   - Transitive series propagation: $\min(\kappa_3, \kappa_1) = \kappa_1$.
   - Conjunction premise propagation: $\min(\kappa_2, \kappa_3, \kappa_3) = \kappa_2$.
   - Corroboration propagation: $\max(\kappa_1, \kappa_3) = \kappa_3$.
   - Axiom absorption: $\min(\kappa_\infty, \kappa_2) = \kappa_2$.

3. **`test_elenchus.py`**:
   - Hard-veto triggers on category error, self-model leak, or non-sequitur premise.
   - Vetoed edge returns `Verdict.HARD_VETO` and is prevented from committing.

4. **`test_checkers.py`**:
   - CAS numerical verification with SymPy (verifies true identities, rejects false identities).
   - Z3 SMT solver verification (verifies valid implications, rejects counter-models).
   - Checker timeout handling (long-running computations cleanly abort and fail).
   - Axiom roster verification ($\kappa_\infty$ for known axioms, $\kappa_1$ for unlisted definitions).

5. **`test_verifier_pipeline.py` & `test_boundary.py`**:
   - Full end-to-end flow: `verify_and_commit` $\to$ rejected on veto, stored on pass.
   - **Boundary Enforcement Test**: AST inspection ensuring `src/arxdb/verification/` contains no imports of `sqlite3`, `pathlib`, or private `Storage` attributes.

---

## 6. Action Items Before Phase 2 Execution

1. **Reconcile [`STORAGE_API.md`](file:///home/ubuntu/arxdb/STORAGE_API.md)** to match Phase 1 implemented signatures (`register_node`, `register_edge`, `get_connectivity` tuple returns, `LogEntry.payload`).
2. **Adopt the refined `Node` proposition model** (moving dynamic truth evaluation out of static node content hashing).
3. **Proceed with implementation in `src/arxdb/verification/`** following the step-by-step order in [`PHASE2_PLAN.md`](file:///home/ubuntu/arxdb/PHASE2_PLAN.md).
