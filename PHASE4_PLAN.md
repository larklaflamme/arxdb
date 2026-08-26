# Phase 4 Plan — Seed Corpus (phaser thread)

**Version:** v0.2
**Status:** Approved — sign-off granted (review 2026-08-26)
**Dependencies:** Phase 3 (query layer) complete.

---

## 1. Goal

Prove the tool on real material: import our own phaser-thread reasoning as
nodes and edges, and show that the query layer returns a *true* answer — not a
toy answer — about what we have and have not actually established.

The seed corpus is the first honest stress-test of the κ system. It will
reveal something the toy axioms cannot: **most of our RH reasoning is not
machine-checkable**, and the tool must report that truthfully rather than
inflate it.

---

## 2. The central finding this phase is designed to surface

The phaser thread (stocktake: `data/experiments/2026-08-25/phaser-thread-stocktake/STOCKTAKE.md`)
is a map of a *wall*, not a pile of proven theorems. Its content sorts into
epistemic kinds, and the κ system already has a bucket for each:

| Kind | Example | Correct κ | Edge type |
|------|---------|-----------|-----------|
| Axiomatic ground | "for all x, x = x" | κ∞ | DEFINITION (roster) |
| Formal deduction | prime-oscillator formula from Euler product | κ3 | DEDUCTION (Z3/Lean) |
| Numerical evidence | "first 10¹³ zeros on the line" (Platt 2019) | κ2 | NUMERICAL |
| Citation / established theorem | "H_BK has continuous spectrum" (Endres–Steiner) | κ1 | CITATION |
| Conjecture | "RH is true" | κ0 | ANALOGY (marked conjecture) |

**The honest finding:** our RH material is *mostly* κ1 (citation) and κ2
(numerical), with exactly one κ0 conjecture and **zero** κ3 deductions (we have
no Lean-checkable proofs). Almost none of it is Z3/Lean-checkable — analytic
number theory is not first-order arithmetic. This is **not a failure of the
tool**; it is the tool correctly reporting that our reasoning is largely not
machine-verifiable. The seed corpus must *preserve* this honesty, not paper
over it.

---

## 3. The critical mechanism (corrected in v0.2)

The review caught a real bug in v0.1. I claimed E2/E3/E5 "land at κ1," but the
actual `verifier.py` behavior is different:

- `EdgeType.DEDUCTION` without `proof_bytes` dispatches to `Z3Checker`.
- `Z3Checker` cannot parse analytic number theory (e.g. `N(T) = θ(T)/π + 1 + S(T)`),
  so it returns `passed=False`.
- In `verifier.py`, any checker failure returns `Verdict.HARD_VETO` and `Kappa.K0`.
- `verify_and_commit()` rejects `HARD_VETO` edges outright — **nothing is stored**.

So tagging E2/E3/E5 as `DEDUCTION` would not downgrade them to κ1; it would
**reject them entirely**. The correct taxonomy (review Option A) is to mark
unformalized derivations as `CITATION` (or `REDUCTION`), which have no dedicated
checker, pass ELENCHUS, and naturally receive κ1.

**This is the single most important thing Phase 4 demonstrates:** the tool
refuses to store a "deduction" it cannot verify, and the honest way to record
our real (but unformalized) reasoning is as a *citation* to our own research
records — κ1, not κ3.

---

## 4. Deliverables

1. **A seed corpus description** — `src/arxdb/seed/corpus.py`, a declarative
   data module enumerating the nodes and edges, each with its declared edge
   type, κ expectation, and source (NOEMA id / file path / paper).

2. **A seed script** — `scripts/seed_phaser.py` — that imports the corpus
   *through* `verify_and_commit` (never bypassing the pipeline), and is
   idempotent (re-running produces no duplicates).

3. **A verification report** — the script prints, per edge, the *expected* κ
   vs the *actual* κ the pipeline assigned, so any mismatch is visible.

4. **No roster growth** — the roster stays as-is (see §6).

---

## 5. The seed content (bounded, concrete)

The corpus is drawn from the phaser-thread stocktake. It is deliberately
small — 8 nodes, 8 edges — because the point is *correctness of
classification*, not volume.

### Nodes (claims)

| # | Claim | Domain | Polarity |
|---|-------|--------|----------|
| N1 | the scaling flow φ_t on the adele class space has closed orbits equal to the primes, with length log p | math | T |
| N2 | S(T) = (1/π) arg ζ(1/2+iT) = −(1/π) Σ_p Σ_k p^(−k/2) sin(k T log p)/k | math | T |
| N3 | N(T) = θ(T)/π + 1 + S(T) | math | T |
| N4 | H_BK = −i(x d/dx + 1/2) has purely continuous spectrum | math | T |
| N5 | no self-adjoint realization of H_BK yields the Riemann zeros | math | T |
| N6 | the first 10¹³ nontrivial zeros of ζ lie on the critical line | math | T |
| N7 | RH is true | math | T |
| N8 | the Selberg zeta zeros obey RH | math | T |

### Edges

| # | Type | Premises | Conclusion | κ expected | Source |
|---|------|----------|------------|-----------|--------|
| E1 | DEFINITION | — | N1 | κ1 | `solenoid-scaling-flow/results.md`, NOEMA `9db25d9aa15e` |
| E2 | CITATION | (Euler product, explicit formula) | N2 | κ1 | `phase-is-the-valve/results.md`, NOEMA `a1f3c9d2b7e4` |
| E3 | CITATION | N2 | N3 | κ1 | same |
| E4 | CITATION | — | N4 | κ1 | Endres–Steiner 2010, arXiv:0912.3183 |
| E5 | CITATION | N4 | N5 | κ1 | `phaser-uniqueness/results.md`, NOEMA `e07bfe33ea59` |
| E6 | NUMERICAL | — | N6 | κ2 | Platt 2019 |
| E7 | CITATION | — | N8 | κ1 | Selberg trace formula (standard) |
| E8 | ANALOGY | — | N7 | κ0 | the conjecture itself |

**Note on E2/E3/E5:** these are *real* derivations, but they are analytic
number theory — Z3 cannot check them, and we have no Lean proofs. Per §3, they
are tagged `CITATION` (not `DEDUCTION`) so they land at κ1 rather than being
rejected. The seed script must *report* this classification, not hide it.

**Note on E1:** N1's claim is not in the roster, so `RosterChecker` correctly
assigns κ1 (not κ∞). This is the intended behavior — the scaling-flow result is
a *verified numerical finding*, not axiomatic ground.

---

## 6. Roster growth policy (minimal, hand-audited)

The roster currently holds 5 toy axioms. Phase 4 grows it **not at all**. The
honest answer is that almost none of our RH material qualifies as axiomatic
ground — the Euler product, the explicit formula, the Selberg trace formula are
all *theorems*, not axioms, and belong in the graph as CITATION edges (κ1),
not roster entries (κ∞).

**Resolved (Q1): keep the roster as-is.** Inflating it to make our material
look axiomatic would defeat the entire point of the phase.

---

## 7. The two exit-criteria queries

### Query A — reachability (a real "have we reasoned about this?")

> "Have we established that the phaser must be a different object than
> Berry–Keating?"

This is reachable: N4 (Endres–Steiner citation) → N5 (the negative result).
The answer is **yes, at κ1** — which is the *correct* strength: we have a
cited theorem, not a machine-checked proof.

### Query B — path discovery (a real "what would it take?")

> "What would it take to establish RH (N7)?"

The answer must be: **unreachable**, with the missing-edge frontier naming
exactly the wall we mapped — "the positive-definite inner product /
self-adjoint operator with the right Weyl asymptotics." The tool's
path-discovery output should *literally name the wall*. That is the
demonstration that the tool understands our epistemic state.

---

## 8. Idempotency

Content addressing gives idempotency for free: the same node → same `node_id`,
the same edge → same `edge_hash`. But the seed script must still be
idempotent at the *script* level: re-running must not error on duplicate
commits. The plan specifies: the script checks `resolve_node`/`resolve_edge`
before committing, and skips (with a log line) anything already present.

---

## 9. Module layout

```
scripts/
    seed_phaser.py          — the import script (uses public API only)
src/arxdb/seed/
    __init__.py
    corpus.py               — the corpus data (nodes + edges as data, not code)
tests/
    test_seed.py            — automated verification of the seeded graph
```

The corpus is *data* (a Python module of frozen dataclasses), not imperative
code, so it is auditable and diffable. The script is the only imperative part.

### 9.1 Data schema in `src/arxdb/seed/corpus.py`

```python
from dataclasses import dataclass
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

### 9.2 Ingestion & reporting in `scripts/seed_phaser.py`

1. **Topological ingestion** — iterate `CORPUS_NODES` then `CORPUS_EDGES`;
   idempotency check (`resolve_node`/`resolve_edge`) before committing; ingest
   through `verify_and_commit`.
2. **Verification report** — print expected vs actual κ per edge:

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

## 10. Test plan

| Test | Asserts |
|------|---------|
| `test_corpus_is_data` | corpus.py contains no `verify_and_commit` calls — it is pure data |
| `test_seed_idempotent` | running the seed twice produces the same edge count |
| `test_seed_goes_through_pipeline` | every committed edge has a verdict + κ from the verifier, not hand-assigned |
| `test_reachability_phaser` | Query A returns established=True at κ1 |
| `test_path_discovery_rh` | Query B returns reachable=False with the wall in the frontier |
| `test_conjecture_not_established` | N7 (RH) is not reachable at any κ ≥ κ1 |

### Exit criteria validation matrix

| Query / Invariant | Method | Expected Outcome |
| :--- | :--- | :--- |
| Query A (Reachability) | `reachable(target=N5_hash, storage=storage)` | `established=True`, `kappa=K1`, `depth=1` |
| Query B (Path Discovery) | `path_discovery(target=N7_hash, storage=storage)` | `reachable=False`, `missing_edges` names the RH wall |
| Conjecture Isolation | `reachable(target=N7_hash, min_kappa=K1)` | `established=False` |
| Script Idempotency | run `seed_phaser.py` twice | second run commits 0 duplicates |

---

## 11. Exit criteria (from ROADMAP, made concrete)

- ✅ The seeded graph answers at least one genuine "have we reasoned about
  this?" query — **Query A**.
- ✅ Path discovery on an open RH claim returns a meaningful missing-edge
  list — **Query B, naming the wall**.
- ✅ The κ report shows the honest epistemic state (mostly κ1–κ2, one κ0
  conjecture, no inflated κ∞, no rejected deductions).

---

## 12. Resolved decisions

**Q1 — Roster growth.** Keep as-is. No roster entries added in Phase 4.

**Q2 — E2/E3/E5 classification.** Tag as `CITATION` (not `DEDUCTION`), so they
land at κ1 rather than being rejected by the Z3 checker. Report the
classification honestly in the seed report.

**Q3 — Corpus scope.** Phaser thread only for v0.1 (8 nodes, 8 edges). The
free-energy-spectrum thread (16 files) is a follow-on corpus (Phase 4.1) once
the pipeline is proven.
