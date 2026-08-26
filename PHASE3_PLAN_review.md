# ArxDB — Phase 3 Implementation Plan Review & Sign-Off (PHASE3_PLAN.md)

**Review Date:** 2026-08-26  
**Document Reviewed:** [`PHASE3_PLAN.md`](file:///home/ubuntu/arxdb/PHASE3_PLAN.md) (v0.1)  
**Related Documents:** [`DESIGN.md`](file:///home/ubuntu/arxdb/DESIGN.md), [`STORAGE_API.md`](file:///home/ubuntu/arxdb/STORAGE_API.md), [`DECISIONS.md`](file:///home/ubuntu/arxdb/DECISIONS.md), [`PHASE2_PLAN.md`](file:///home/ubuntu/arxdb/PHASE2_PLAN.md)

---

## 1. Executive Assessment & Formal Sign-Off

[`PHASE3_PLAN.md`](file:///home/ubuntu/arxdb/PHASE3_PLAN.md) delivers the core product capability of ArxDB: **the Query Layer**.

### Assessment: **APPROVED / SIGN-OFF GRANTED** ✅

The plan exhibits high theoretical rigor and systems discipline:
1. **Accurate Hypergraph Formulation**: Correctly models multi-premise reasoning as Horn-clause AND-OR resolution rather than naive single-path digraph search.
2. **Mathematically Sound Fixpoint**: Employs a monotone max-min semiring least-fixpoint over the finite $\kappa$ lattice ($\mathcal{H} = 5$), guaranteeing convergence and termination even on cyclic or recursive claim graphs.
3. **Principled Non-Monotonic Defeasibility**: Adopts Dung's grounded argumentation semantics (skeptical, poly-time, deterministic) for refutation resolution, enabling verifiable proof revocation without mutating historical Merkle logs.
4. **Strict Boundary Adherence**: Keeps storage strictly structural while query resolution operates entirely above the storage boundary via public methods and CBOR object decoding.

Below is a detailed analysis, algorithmic recommendations, and test requirements for Phase 3.

---

## 2. Deep-Dive Algorithmic Analysis

### 2.1 AND-OR Reachability & the $\kappa$-Lattice Fixpoint

The reachability algorithm computes the strongest derivation for every reachable node using a bottom-up Datalog-style fixpoint:

```
Initialize:
    kappa_map = { conclusion(e): e.kappa for e in active_edges if len(e.premises) == 0 }

Loop until convergence:
    For each edge e in active_edges (where len(e.premises) > 0):
        If all premises p in e.premises are in kappa_map:
            path_kappa = min(e.kappa, min(kappa_map[p] for p in e.premises))
            If path_kappa > kappa_map.get(e.conclusion, K_MIN):
                kappa_map[e.conclusion] = path_kappa
                Mark changed
```

* **Lattice Invariant**: The scale $\kappa_0 < \kappa_1 < \kappa_2 < \kappa_3 < \kappa_\infty$ is a finite chain of height 5. Because each node's $\kappa$ value is strictly monotone non-decreasing and upper-bounded by $\kappa_\infty$, the fixpoint terminates in at most $5 \cdot |V|$ updates.
* **Cycle Safety**: Cycles in deduction graphs (e.g., $A \to B \to A$) do not cause infinite loops. If $A$ is not grounded by an axiom, neither $A$ nor $B$ ever enters the initial seed set.

---

### 2.2 Path Discovery: Backward Goal Cone vs. Global Frontier

In [`PHASE3_PLAN.md` § Path discovery](file:///home/ubuntu/arxdb/PHASE3_PLAN.md#L99-L112):
* **Observation**: A forward scan of unproven premises identifies *all* missing lemmas in the entire database. However, when querying `path_discovery(target)`, the user specifically needs to know what is missing to establish `target`.
* **Recommendation**:
  1. Compute forward reachability to know which nodes are already established.
  2. If `target` is established: return `reachable=True`, `depth=depth[target]`, `missing_edges=[]`, and optionally the sub-hypergraph proof tree.
  3. If `target` is **not** established: perform a **backward traversal from `target`** along candidate/unverified edges:
     - For each candidate path leading into `target`, find the unestablished premises.
     - The unestablished premises that have no verified derivations form the **goal-specific missing frontier** (`MissingEdge(conclusion, unproven_premises, blocking_nodes)`).

---

### 2.3 Refutation Resolution: Dung Grounded Semantics

In [`PHASE3_PLAN.md` § Refutation resolution](file:///home/ubuntu/arxdb/PHASE3_PLAN.md#L113-L129):
* **Attack Graph Definition**:
  - An edge $E_{\text{ref}}$ of type `REFUTATION` whose `conclusion == E_{\text{target}}.edge_hash()` attacks $E_{\text{target}}$.
  - Additionally, if an edge $E_1$ concludes proposition $P$ (polarity=True) and $E_2$ concludes $P$ (polarity=False), they are in mutual or directional contention.
* **Grounded Extension Labeling**:
  - `IN`: Edges not attacked by any `IN` edge.
  - `OUT`: Edges attacked by at least one `IN` edge.
  - `UNDECIDED`: Unresolvable mutual cycles (e.g., symmetric ungrounded refutations).
* **Properties**:
  - Monotonic & Skeptical: Never accepts an edge unless all its attackers are proven `OUT`.
  - Reinstatement: If $E_1$ attacks $E_2$, and $E_3$ attacks $E_1$, then $E_3 \in \text{IN} \implies E_1 \in \text{OUT} \implies E_2 \in \text{IN}$. The original edge is restored.
  - Runs in polynomial time $O(|E|^2)$.

---

## 3. Decisions & Open Questions Review

| Question | Assessment & Decision |
| :--- | :--- |
| **Q1: Seed-Set Discovery** | **Accept Option (b)**: Auto-discover seeds from zero-premise edges (`premises == ()`).<br>• *Enhancement*: Allow an optional `extra_seeds: Sequence[Hash] = ()` argument in `reachable()` to support hypothetical / conditional reasoning ("If we assume $H$, does $C$ follow?"). |
| **Q2: Refutation Semantics** | **Accept Grounded Semantics**: Grounded extensions provide deterministic, polynomial-time skeptical evaluation. Ideal for audit and automated verification. |

---

## 4. Pre-Work: Structural Additions to `GraphIndex`

To support query iteration without violating boundary discipline, add two structural enumeration methods to `src/arxdb/storage/graph_index.py`:

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

---

## 5. Query Layer Architecture & Module Plan

```
src/arxdb/query/
├── __init__.py         # Public exports: reachable, path_discovery, resolve_node, resolve_edge
├── resolve.py          # resolve_node(h, storage) -> Node | None
│                       # resolve_edge(h, storage) -> Edge | None
├── refutation.py       # compute_active_subgraph(storage) -> set[Hash] (Grounded semantics)
├── reachability.py     # ReachabilityResult, reachable(target, min_kappa, storage, seeds=())
└── path.py             # PathResult, MissingEdge, path_discovery(target, storage)
```

### Public API Signatures:

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

---

## 6. Comprehensive Phase 3 Test Matrix

| Test Module | Test Case | Expected Behavior |
| :--- | :--- | :--- |
| **`test_resolve.py`** | `test_resolve_node_and_edge` | Decodes stored CBOR blobs back into `Node` and `Edge` instances. |
| | `test_resolve_missing_returns_none` | Unknown hash returns `None` without raising. |
| **`test_reachability.py`** | `test_single_axiom_reachable` | Zero-premise definition immediately establishes conclusion at edge $\kappa$. |
| | `test_and_conjunction_soundness` | Edge $A \land B \to C$: $C$ is unreachable if only $A$ is established; becomes reachable once both $A$ and $B$ are established. |
| | `test_series_min_propagation` | $A \xrightarrow{\kappa_3} B \xrightarrow{\kappa_1} C \implies \kappa(C) = \kappa_1$. |
| | `test_corroboration_max_propagation`| Path 1 gives $\kappa_1$, Path 2 gives $\kappa_3 \implies \kappa(C) = \kappa_3$. |
| | `test_kappa_threshold_filter` | Querying `min_kappa=K3` returns `established=False` for $\kappa_2$ derivation. |
| | `test_cyclic_graph_terminates` | Cycle $A \to B \to A$ terminates safely without infinite recursion. |
| | `test_hypothetical_seed_reachability`| Providing hypothetical seed $H$ establishes conditional derivations. |
| **`test_path.py`** | `test_proof_tree_depth_parallel` | Proof tree with two depth-0 premises yielding conclusion has depth 1 (not 2). |
| | `test_missing_edge_frontier_isolation` | For unproven target $T$, identifies only the blocking premises in $T$'s dependency cone. |
| **`test_refutation.py`** | `test_refutation_defeats_edge` | Active refutation edge removes target edge from active subgraph; downstream nodes lose derived status. |
| | `test_reinstatement_of_refuted_edge`| Refuting the refutation reinstates the original edge and derived nodes. |
| | `test_mutual_refutation_undecided` | Symmetric attacks are skeptically excluded from grounded extension. |
| **`test_boundary.py`** | `test_query_layer_boundary` | AST check ensuring `src/arxdb/query/` contains no imports of `sqlite3`, `pathlib`, or private storage attributes. |

---

## 7. Sign-Off Checklist

- [x] Hypergraph AND-OR Horn-clause resolution model validated.
- [x] Max-min semiring least-fixpoint algorithm verified for convergence.
- [x] Dung grounded extension refutation semantics approved.
- [x] Pre-work structural additions (`all_nodes`, `all_edges`) specified.
- [x] AST boundary test requirements confirmed.

**Phase 3 implementation is fully approved to proceed.**
