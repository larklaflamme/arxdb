# ArxDB — Phase 4 Plan Review & Sign-Off (PHASE4_PLAN.md)

**Review Date:** 2026-08-26  
**Document Reviewed:** [`PHASE4_PLAN.md`](file:///home/ubuntu/arxdb/PHASE4_PLAN.md) (v0.1)  
**Related Documents:** [`DESIGN.md`](file:///home/ubuntu/arxdb/DESIGN.md), [`STORAGE_API.md`](file:///home/ubuntu/arxdb/STORAGE_API.md), [`DECISIONS.md`](file:///home/ubuntu/arxdb/DECISIONS.md), [`PHASE3_PLAN.md`](file:///home/ubuntu/arxdb/PHASE3_PLAN.md)

---

## 1. Executive Assessment & Formal Sign-Off

[`PHASE4_PLAN.md`](file:///home/ubuntu/arxdb/PHASE4_PLAN.md) transitions ArxDB from toy test cases to real mathematical reasoning by importing the **phaser-thread corpus**.

### Assessment: **APPROVED / SIGN-OFF GRANTED** ✅

The plan demonstrates exceptional epistemic discipline:
1. **Epistemic Honesty over Inflation**: Explicitly recognizes that advanced analytic number theory is not first-order arithmetic checkable by Z3. The tool's primary virtue is truthfully reporting that derivations without formal machine proofs land at $\kappa_1$ (literature citation / ELENCHUS-vetted) or $\kappa_2$ (numerical computation), rather than artificially promoting them to $\kappa_3$ or $\kappa_\infty$.
2. **Diagnostic Power**: Verifies that `path_discovery(RH)` correctly fails reachability and surfaces the *exact theoretical wall* (the missing self-adjoint operator / positive-definite metric) as the missing frontier.
3. **Clean Decoupling**: Maintains the corpus as declarative data (`src/arxdb/seed/corpus.py`) and executes ingestion exclusively through the public `verify_and_commit` pipeline (`scripts/seed_phaser.py`).

---

## 2. Critical Implementation Insight: Handling Unformalized Deductions

In [`PHASE4_PLAN.md` §4 & §11 (Q2)](file:///home/ubuntu/arxdb/PHASE4_PLAN.md#L86-L103), edges E2, E3, and E5 are listed as `DEDUCTION` with the expectation that they land at $\kappa_1$.

### The Technical Mechanism in `verifier.py`:
In the Phase 2 implementation ([`src/arxdb/verification/verifier.py`](file:///home/ubuntu/arxdb/src/arxdb/verification/verifier.py#L94-L165)):
* `EdgeType.DEDUCTION` without `proof_bytes` is dispatched to `Z3Checker`.
* If `Z3Checker` fails to parse natural-language analytic mathematics (e.g. `_parse("N(T) = θ(T)/π + 1 + S(T)")`), it returns `passed=False`.
* In `verifier.py`, any checker failure returns `Verdict.HARD_VETO` and `Kappa.K0`.
* `verify_and_commit()` rejects `HARD_VETO` edges outright, meaning nothing is stored in the database.

### Recommended Resolution for `corpus.py`:
To achieve the intended epistemic classification where unformalized mathematical derivations land at $\kappa_1$ without triggering a `HARD_VETO`:
1. **Option A (Taxonomy Fidelity - Recommended)**: Mark unformalized derivations (E2, E3, E5) in `corpus.py` as `EdgeType.CITATION` (or `REDUCTION` where applicable) referencing their NOEMA artifact or research notes. In `verifier.py`, `CITATION` edges undergo ELENCHUS sanity filtering and naturally receive $\kappa_1$.
2. **Option B (Deduction Fallback)**: If tagged as `DEDUCTION`, provide a mock or informal proof tag, or acknowledge that formal `DEDUCTION` requires a valid Z3 parse or Lean kernel proof to avoid `HARD_VETO`.

Option A accurately reflects the epistemic status: until a full Lean 4 script is authored, these steps represent cited derivations from research records.

---

## 3. Review of the Three Open Decisions

| Question | Assessment & Recommendation |
| :--- | :--- |
| **Q1: Roster Growth** | **Accept Recommendation (Keep As-Is)**: Do not inflate `roster.py` with non-axiomatic theorems. Real mathematical theorems belong in the graph as cited nodes ($\kappa_1$) or formal deductions ($\kappa_3$), not hardcoded system ground ($\kappa_\infty$). |
| **Q2: Analytic Deductions Landing at $\kappa_1$** | **Accept Recommendation**: Report the $\kappa_1$ classification truthfully. The verification report in `scripts/seed_phaser.py` should prominently display the expected vs. actual $\kappa$. |
| **Q3: Corpus Scope (Phaser Thread Only)** | **Accept Recommendation**: Scope v0.1 to the ~10 nodes and ~8 edges of the phaser thread. The free-energy spectrum thread can be imported as a Phase 4.1 expansion. |

---

## 4. Module & Script Architecture

```
scripts/
    seed_phaser.py       — Ingestion CLI running verify_and_commit + printing κ report
src/arxdb/seed/
    __init__.py
    corpus.py            — Declarative CorpusNode and CorpusEdge data structures
tests/
    test_seed.py         — Automated verification of the seeded graph & exit queries
```

### 4.1 Data Schema in `src/arxdb/seed/corpus.py`

```python
from dataclasses import dataclass
from typing import Sequence
from arxdb.verification.schema import EdgeType, Kappa

@dataclass(frozen=True)
class CorpusNode:
    key: str
    claim: str
    domain: str = "math"
    polarity: bool = True

@dataclass(frozen=True)
class CorpusEdge:
    key: str
    edge_type: EdgeType
    premise_keys: tuple[str, ...]
    conclusion_key: str
    rule: str
    expected_kappa: Kappa
    source: str
    proof_bytes: bytes | None = None
```

### 4.2 Ingestion & Reporting in `scripts/seed_phaser.py`

1. **Topological Ingestion**:
   - Iterate through `CORPUS_NODES` and `CORPUS_EDGES`.
   - Idempotency check: verify if `edge_hash` or `node_id` is already present before committing.
   - Ingest through `verify_and_commit`.
2. **Verification Report Output**:
   ```
   ====================== ARXDB SEED REPORT: PHASER THREAD ======================
   EDGE | TYPE       | RULE                       | EXPECTED | ACTUAL | STATUS
   -----+------------+----------------------------+----------+--------+-------
   E1   | DEFINITION | solenoid scaling flow      | K1       | K1     | MATCH
   E2   | CITATION   | Euler product explicit eq  | K1       | K1     | MATCH
   E3   | CITATION   | phase-is-the-valve         | K1       | K1     | MATCH
   E4   | CITATION   | Endres-Steiner 2010        | K1       | K1     | MATCH
   E5   | CITATION   | phaser uniqueness theorem  | K1       | K1     | MATCH
   E6   | NUMERICAL  | Platt 2019 zeros bound     | K2       | K2     | MATCH
   E7   | CITATION   | Selberg trace formula      | K1       | K1     | MATCH
   E8   | ANALOGY    | Riemann Hypothesis         | K0       | K0     | MATCH
   ==============================================================================
   ```

---

## 5. Exit Criteria Validation Matrix

| Query / Invariant | Method | Expected Outcome |
| :--- | :--- | :--- |
| **Query A (Reachability)** | `reachable(target=N5_hash, storage=storage)` | `established=True`, `kappa=Kappa.K1`, `depth=1` (Proves phaser $\ne$ Berry-Keating at $\kappa_1$). |
| **Query B (Path Discovery)** | `path_discovery(target=N7_hash, storage=storage)` | `reachable=False`, `missing_edges` contains the unproven hypothesis frontier for RH. |
| **Conjecture Isolation** | `reachable(target=N7_hash, min_kappa=Kappa.K1)` | `established=False` (RH conjecture is not established). |
| **Script Idempotency** | Run `seed_phaser.py` twice | Second run detects all objects, commits 0 duplicates, log length remains invariant. |

---

## 6. Sign-Off Checklist

- [x] Epistemic classification and non-inflation thesis verified.
- [x] Node and edge definitions for Phaser thread approved.
- [x] Storage pipeline compatibility and `verify_and_commit` integration confirmed.
- [x] Exit queries A & B test specifications verified.

**Phase 4 implementation is fully approved to proceed.**
