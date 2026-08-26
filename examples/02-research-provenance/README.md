# 02 — Research provenance

How the κ-strength scale maps onto *real* research artifacts, and how path
discovery names the "wall" — the exact missing step that would upgrade a
conjecture to a theorem.

## The scenario

You are running a research program (say, on the Riemann Hypothesis). Your
reasoning is a mix of:

- **axioms** you take as ground (κ∞),
- **assumptions** you assert but haven't proven (κ1),
- **deductions** you machine-check (κ3),
- **identities** you verify with a CAS (κ2),
- **citations** to the literature (κ1).

ArxDB classifies each edge by strength, so you can ask "is this claim
established *at κ2 or better*?" — and when the answer is no, it tells you
exactly what's missing.

## Run it

```bash
cd /home/ubuntu/arxdb
conda activate arxdb
python examples/02-research-provenance/research.py
```

## Expected output

```
kappa_inf (axiom)        -> verdict=PASS       kappa=K_INF
kappa1 (assumption)      -> verdict=PASS       kappa=K1
kappa3 (Z3 deduction)    -> verdict=PASS       kappa=K3
kappa2 (CAS identity)    -> verdict=PASS       kappa=K2
kappa1 (citation)        -> verdict=PASS       kappa=K1
kappa1 (citation)        -> verdict=PASS       kappa=K1

reachable(RH, min_kappa=K0     ) -> established=True
reachable(RH, min_kappa=K1     ) -> established=True
reachable(RH, min_kappa=K2     ) -> established=False
reachable(RH, min_kappa=K3     ) -> established=False

path_discovery(RH, min_kappa=K2): reachable=False
  missing: conclusion=1e202be5fa15... blocking=1 rule='cite'
```

## Walkthrough

### The κ scale, one edge per level

| Edge | Type | Checker | κ |
|------|------|---------|---|
| "for all x, x = x" | DEFINITION | roster | K_INF |
| "x > 0" | DEFINITION | roster (unlisted) | K1 |
| "x > 0" → "x + 1 > 0" | DEDUCTION | Z3 | K3 |
| "x²−1 = (x−1)(x+1)" | NUMERICAL | sympy | K2 |
| "RH is unproven" | CITATION | none | K1 |
| "RH is unproven" → "zeros on the line" | CITATION | none | K1 |

The point: the *same* claim can be held at different strengths depending on
*how* you got there. A citation is κ1; a machine-checked deduction is κ3.

### Reachability at a threshold

```python
reachable(rh.node_id(), store, min_kappa=Kappa.K2)
```

The RH claim is only ever established at κ1 (it is cited, not proven). So at
`min_kappa=K2` it is **not** established — which is the honest answer: we have
not *proven* RH, we have only *cited* it.

### Path discovery: name the wall

```python
path_discovery(rh.node_id(), store, min_kappa=Kappa.K2)
```

Reports the goal-specific missing frontier: the unestablished premises in the
target's backward dependency cone. This is the tool's answer to "what would it
take to upgrade RH from κ1 to κ2?" — it names the exact blocking step.

## Handling scenarios

- **Isolate a conjecture** — ask `reachable(claim, min_kappa=K2)`: if False, the
  claim is a conjecture (κ1 or below), not a theorem.
- **Find the weakest link** — `path_discovery` with a high `min_kappa` surfaces
  the specific citation/assumption that is holding a derivation back.
- **Track a proof as it lands** — when you finally machine-check the missing
  step, re-commit it as a DEDUCTION (κ3) and re-run `reachable`: the claim
  flips to established at κ3.

## Key API

`verify_and_commit`, `reachable` (with `min_kappa`), `path_discovery`,
`Kappa`, `EdgeType`.
