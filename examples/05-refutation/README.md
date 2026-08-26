# 05 — Refutation

Attack and defend edges. Revocation is a first-class edge type, not a deletion,
and the query layer computes the **active subgraph** — which edges are IN
(valid), OUT (defeated), or UNDECIDED (mutual cycles).

## The scenario

You have a chain of reasoning: A → B → C. Someone refutes the B step. The
question: does C still hold?

ArxDB answers this with **Dung's grounded extension** (skeptical, deterministic,
polynomial-time): an edge is IN iff it is not attacked by any IN edge. A
refuted edge is OUT, and everything downstream of it loses its derived status —
until the refutation is itself refuted.

## Run it

```bash
cd /home/ubuntu/arxdb
conda activate arxdb
python examples/05-refutation/refutation.py
```

## Expected output

```
[before]    C established=True
[active]    B in=False out=True
[after]     C established=False
[reinstated] C established=True
```

## Walkthrough

### A refutation's conclusion is the target edge's hash

A REFUTATION edge attacks the edge whose hash is its `conclusion` — *not* a
node hash. Because `verify_and_commit` computes a conclusion from a `Node`, a
refutation is built directly:

```python
edge = Edge(
    type=EdgeType.REFUTATION,
    premises=(),
    conclusion=target_edge_hash,   # the edge being attacked
    rule="refute",
    proof_hash=None,
    verdict=Verdict.PASS,
    kappa=Kappa.K1,
    signer_pubkey=signer_pubkey,
)
edge_hash, _ = store.commit_edge_tx(
    premises=[], conclusion=target_edge_hash, edge_data=edge.edge_bytes(),
)
```

### The active subgraph

```python
active = compute_active_subgraph(store)
# active.in_edges, active.out_edges, active.undecided_edges
```

After refuting B, B is OUT. Passing `active_edges=active.in_edges` to
`reachable` makes reachability respect refutation: C is no longer established.

### Refuting the refutation

Refute the refutation edge, and B is reinstated (the refutation is now OUT, so
B is no longer attacked by any IN edge). C is established again.

## Handling scenarios

- **Mutual contention** — two edges concluding the same proposition with
  opposite polarity attack each other and land in `undecided_edges`
  (skeptically excluded). This is the "P vs ¬P" deadlock.
- **Long refutation chains** — the grounded fixpoint terminates on arbitrarily
  long attack chains (see `tests/test_refutation.py` for the 4-edge chain).
- **Debate** — model a back-and-forth as alternating refutations; the grounded
  extension deterministically labels the winner.
- **Revoke without deleting** — because refutation is an edge, the history is
  preserved: you can always see *what* was refuted and *why*, and the
  refutation itself is auditable.

## Key API

`compute_active_subgraph`, `reachable` (with `active_edges`), `Edge` (built
directly), `EdgeType.REFUTATION`.
