# ArxDB — Phase 3 Implementation Plan (v0.2)

**Goal:** the query layer — the product. AND-OR reachability + path discovery
(the two queries), plus refutation resolution, built on the Phase 2 verification
layer and the Phase 1 storage substrate, behind the boundary discipline.

**Scope:** query/traversal only. No seed corpus (Phase 4), no Go swap (Phase 6),
no attestation (Phase 5).

> **v0.2 changelog** (post-review): both open questions resolved (Q1 → option b
> with `extra_seeds` enhancement; Q2 → grounded semantics); path discovery
> switched from global frontier to backward goal-cone traversal; public API
> dataclass signatures specified; test matrix expanded to match the review's
> requirements (including the AST boundary test).

## What Phase 2 delivered (the substrate we build on)

- `schema.py` — `Node` (claim + domain + polarity, immutable, no truth field),
  `Edge` (type + premises + conclusion + rule + proof_hash + verdict + κ +
  signer_pubkey), canonical CBOR, `node_id()`/`edge_bytes()`/`from_bytes()`.
- `kappa.py` — total order K0 < K1 < K2 < K3 < K_INF; `series`=min,
  `parallel`=min, `corroborate`=max.
- `verifier.py` — `verify(premises, conclusion, rule, type) -> VerificationResult`
  (verdict + κ + checker).
- `commit.py` — `verify_and_commit(...) -> CommitResult`; stores node payloads
  in ObjectStore, commits edge bytes + proof atomically.
- Storage: `incoming_edges`, `outgoing_edges`, `get_connectivity` (structural
  adjacency only), `objects.get` (content-addressed blobs).

## The boundary (non-negotiable)

Storage is dumb and fast. The query layer:
- resolves node/edge hashes → `Node`/`Edge` records by decoding ObjectStore
  blobs (never by reaching into SQLite);
- computes AND-OR resolution, κ-propagation, and refutation resolution itself;
- **never inspects storage internals** — no `sqlite3`, no `pathlib`, no `_conn`.

## The core model: AND-OR hypergraph, not a digraph

A hyper-edge has multiple premises (A ∧ B → C). Reachability is **Horn-clause
deduction** (AND-OR resolution), not BFS over a digraph. A node is *established*
iff:

1. it is the conclusion of a zero-premise edge (definition/axiom), **or**
2. it is the conclusion of an active edge whose premises are *all* established.

The classic failure mode (already documented in STORAGE_API.md): a dumb BFS
marks C reachable as soon as *any one* premise is connected — logically unsound
for multi-premise inference. Phase 3 exists to do this correctly.

## The two queries (precise semantics)

### 1. Reachability — "have we reasoned about this before?"

`reachable(target, min_kappa=K0, extra_seeds=()) -> ReachabilityResult`

- `established: bool` — is there a derivation of `target` from the seed set?
- `kappa: Kappa` — the strength of the *best* derivation (max over paths of the
  min over edges; corroboration = max, series/parallel = min).
- `depth: int` — proof-tree depth of the best derivation (see path discovery).
- `proof_tree_edges: tuple[Hash, ...]` — the sub-hypergraph edges of the best
  derivation (optional, for auditability).

`established` is true iff `kappa >= min_kappa` (κ-threshold filtering).

**Hypothetical reasoning:** `extra_seeds: Sequence[Hash] = ()` lets the caller
inject conditional assumptions ("if we assume H, does C follow?"). These are
treated as established at K_INF for the duration of the query, without mutating
storage. This is the review's enhancement to Q1.

### 2. Path discovery — "what would it take?"

`path_discovery(target) -> PathResult`

- `reachable: bool`
- `depth: int` — minimum number of *parallel* reasoning steps (proof-tree depth,
  not linear chain length). Each step may fan in multiple premises.
- `missing_edges: tuple[MissingEdge, ...]` — the goal-specific missing frontier.

**Backward goal-cone traversal (not global frontier).** A forward scan of
unproven premises identifies *all* missing lemmas in the database — but the
caller asking `path_discovery(target)` needs to know what is missing to
establish *target specifically*. So:

1. Compute forward reachability to know which nodes are already established.
2. If `target` is established: return `reachable=True`, `depth=depth[target]`,
   `missing_edges=()`, and optionally the proof tree.
3. If `target` is **not** established: traverse **backward from `target`** along
   candidate edges, finding the unestablished premises in `target`'s dependency
   cone. Unestablished premises with no verified derivation form the
   goal-specific missing frontier.

The hop count is a **lower bound** on difficulty, never a prediction.

## The core algorithm: max-min semiring fixpoint

Reachability + κ-propagation is a single least-fixpoint over the κ lattice
(5 values, finite, so it terminates):

```
kappa = {seed: edge.kappa for each zero-premise edge}   # axioms/definitions
changed = True
while changed:
    changed = False
    for edge in active_edges:                            # PASS/SOFT_FLAG, non-refutation
        if all(p in kappa for p in edge.premises):
            path_kappa = min(edge.kappa, min(kappa[p] for p in edge.premises))
            if edge.conclusion not in kappa or path_kappa > kappa[edge.conclusion]:
                kappa[edge.conclusion] = path_kappa
                changed = True
```

- **series/parallel** = the inner `min` (weakest link of the conjunction).
- **corroboration** = the outer `>` comparison (a node's κ only ever *rises* as
  stronger independent paths are found).
- **termination** is guaranteed: κ is a finite lattice of height 5, each node's
  κ is monotone non-decreasing and bounded above by K_INF, so the fixpoint
  terminates in at most `5 · |V|` updates.
- **cycle safety**: a cycle (A → B → A) with no axiom grounding never enters the
  seed set, so neither A nor B is ever established — no infinite loop.

This is Horn-clause Datalog bottom-up evaluation, hand-rolled (~30 lines) rather
than pulling in a Datalog engine (Soufflé/pyDatalog) — transparent, no new
dependency, and the fixpoint is the whole point.

## Path discovery: level-order over the hypergraph

Compute `depth[n]` = minimum proof-tree depth at which `n` becomes established,
via level-order (BFS over the AND-OR structure, not a digraph):

- seeds (zero-premise edges) are depth 0.
- an edge fires at depth `1 + max(depth[p] for p in premises)`.
- a node's depth is the minimum over its incoming edges.

The **missing-edge frontier** (goal-specific, per §2 above) = unestablished
premises in `target`'s backward dependency cone. Each is reported as a
`MissingEdge(conclusion, premises, blocking_nodes, rule)` naming the conclusion
that needs a verified edge from established premises, and which premises block it.

## Refutation resolution (second half of Phase 3)

Revocation is a first-class edge type, not a deletion. An edge can target
another edge or claim with type `refutation`. The query layer computes the
**active subgraph** — which edges are "in" (valid) vs "out" (defeated).

**Resolved semantics: Dung grounded extension over edges** (skeptical, poly-time,
deterministic):

- an edge is *in* iff it is not attacked by any *in* edge;
- an edge is *out* iff it is attacked by some *in* edge;
- the grounded extension is the least fixpoint of this labeling.

**Attack graph definition:**
- an edge `E_ref` of type `REFUTATION` whose `conclusion == E_target.edge_hash()`
  attacks `E_target`;
- additionally, if `E1` concludes proposition `P` (polarity=True) and `E2`
  concludes `P` (polarity=False), they are in contention.

**Labeling:** `IN` (not attacked by any IN edge), `OUT` (attacked by ≥1 IN edge),
`UNDECIDED` (unresolvable mutual cycles, e.g. symmetric ungrounded refutations).

**Properties:**
- monotonic & skeptical — never accepts an edge unless all its attackers are OUT;
- reinstatement — if E1 attacks E2 and E3 attacks E1, then E3 ∈ IN ⟹ E1 ∈ OUT ⟹
  E2 ∈ IN (the original edge is restored);
- runs in polynomial time O(|E|²).

This handles the non-monotonic case cleanly and is the conservative (skeptical)
choice, matching the moat philosophy — never claim more than is defensible.
(Preferred extensions are credulous and NP-hard; deferred.)

## Module layout

```
src/arxdb/query/
    __init__.py     # public exports: reachable, path_discovery, resolve_node, resolve_edge
    resolve.py      # resolve_node(h, storage) -> Node | None
                    # resolve_edge(h, storage) -> Edge | None
    reachability.py # ReachabilityResult, reachable(target, min_kappa, storage, extra_seeds=())
    path.py         # PathResult, MissingEdge, path_discovery(target, storage)
    refutation.py   # compute_active_subgraph(storage) -> set[Hash] (grounded semantics)
```

### Public API signatures

```python
@dataclass(frozen=True)
class ReachabilityResult:
    target: Hash
    established: bool
    kappa: Kappa | None
    depth: int | None
    proof_tree_edges: tuple[Hash, ...]


@dataclass(frozen=True)
class MissingEdge:
    conclusion: Hash
    premises: tuple[Hash, ...]
    blocking_nodes: tuple[Hash, ...]
    rule: str


@dataclass(frozen=True)
class PathResult:
    target: Hash
    reachable: bool
    depth: int | None
    kappa: Kappa | None
    missing_edges: tuple[MissingEdge, ...]
```

## Pre-work: storage enumeration extension

The graph index has `incoming_edges`/`outgoing_edges`/`get_connectivity` but **no
enumeration**. The query layer needs to find the seed set (zero-premise edges)
and iterate all edges. Add to `GraphIndex`:

```python
def all_nodes(self) -> list[Hash]:
    """All indexed node hashes in deterministic order."""
    rows = self._conn.execute(
        "SELECT node_hash FROM nodes ORDER BY node_hash"
    ).fetchall()
    return [Hash(r[0]) for r in rows]

def all_edges(self) -> list[Hash]:
    """All indexed edge hashes in deterministic order."""
    rows = self._conn.execute(
        "SELECT edge_hash FROM edges ORDER BY edge_hash"
    ).fetchall()
    return [Hash(r[0]) for r in rows]
```

These are structural (adjacency enumeration), not semantic — they stay inside
the boundary. This is a small Phase 1 extension, done as Phase 3 pre-work.

## Resolved decisions

**Q1 — seed-set discovery: option (b), with enhancement.** Enumerate zero-premise
edges (requires the `all_edges()` extension); the system discovers its own seeds.
*Enhancement:* `reachable()` accepts an optional `extra_seeds: Sequence[Hash] = ()`
argument to support hypothetical/conditional reasoning ("if we assume H, does C
follow?") without mutating storage.

**Q2 — refutation semantics: grounded.** Dung grounded extensions provide
deterministic, polynomial-time skeptical evaluation — ideal for audit and
automated verification. Preferred (credulous, NP-hard) deferred.

## Test plan requirements (Phase 3 sign-off)

1. **`test_resolve.py`** — hash → `Node`/`Edge` round-trip via ObjectStore;
   absent hash → `None` (not an exception).
2. **`test_reachability.py`** —
   - single axiom → target reachable;
   - multi-premise (A ∧ B → C): C reachable only when *both* A and B established;
   - unreachable when a premise is missing;
   - κ propagation: min over a path (series), corroboration max over independent
     paths;
   - κ-threshold filtering: reachable at κ2 but not κ3;
   - fixpoint terminates on a cyclic graph (no infinite loop);
   - hypothetical seed: providing `extra_seeds=[H]` establishes conditional
     derivations.
3. **`test_path.py`** —
   - proof-tree depth correct (parallel steps counted once, not summed);
   - missing-edge frontier isolates only the blocking premises in `target`'s
     dependency cone (not the global frontier).
4. **`test_refutation.py`** —
   - refuted edge excluded from the active subgraph; downstream nodes lose
     derived status;
   - refutation-of-refutation reinstates the original edge and derived nodes;
   - mutual refutation → skeptically excluded (UNDECIDED);
   - grounded fixpoint terminates.
5. **`test_boundary.py`** — AST check ensuring `src/arxdb/query/` contains no
   imports of `sqlite3`, `pathlib`, or private storage attributes (`_conn`,
   `objects.root`).

## Sign-off checklist

- [ ] Reachability returns correct yes/no on a seeded graph (AND-OR, not BFS).
- [ ] Path discovery returns minimum proof-tree depth + names goal-specific
      missing edges (backward cone, not global frontier).
- [ ] κ propagates correctly (min over path, max over corroboration).
- [ ] Refutation resolution computes the active subgraph (grounded, with
      reinstatement).
- [ ] Queries run against the storage layer, not in-memory ad-hoc structures.
- [ ] Boundary holds: no `sqlite3`/`pathlib`/`_conn` in `query/` (AST-verified).
