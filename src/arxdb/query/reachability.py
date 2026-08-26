"""reachability.py — AND-OR reachability with κ-propagation.

The first of the two queries: "have we reasoned about this before?" It answers
whether a target claim is derivable from the seed set (axioms/definitions) via
verified inference edges, and at what κ-strength.

The traversal model is an AND-OR hypergraph, not a digraph: a hyper-edge has
multiple premises (A ∧ B → C), so reachability is Horn-clause deduction, not
BFS. A node is established iff it is the conclusion of a zero-premise edge
(definition/axiom) or of an active edge whose premises are *all* established.

Reachability + κ-propagation collapse into one max-min semiring least-fixpoint
over the finite κ lattice (5 values, so it terminates):

    series/parallel  = inner min  (weakest link of the conjunction)
    corroboration    = outer max  (a node's κ only rises as stronger
                                   independent paths are found)

Boundary discipline: this module resolves records via `resolve.py` (ObjectStore
decode) and reads structural adjacency via the public `Storage.graph` methods.
No sqlite3, no pathlib, no private storage attributes.

Public API:
    ReachabilityResult  — target, established, kappa, depth, proof_tree_edges
    reachable(target, storage, min_kappa=K0, extra_seeds=(), active_edges=None)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from arxdb.storage.hashing import Hash
from arxdb.storage.storage import Storage

from arxdb.verification.kappa import (
    Kappa,
    min_kappa as _kappa_min,
    rank,
)
from arxdb.verification.schema import Edge, EdgeType, Verdict

from .resolve import resolve_edge


@dataclass(frozen=True)
class ReachabilityResult:
    """The outcome of a reachability query.

    `established` is the thresholded answer: True iff `target` is derivable at
    κ ≥ `min_kappa`. `kappa`, `depth`, and `proof_tree_edges` describe the
    *actual* best derivation whenever one exists (even if it falls below the
    threshold); they are None/empty only when `target` is unreachable.
    """

    target: Hash
    established: bool
    kappa: Kappa | None
    depth: int | None
    proof_tree_edges: tuple[Hash, ...]


def _derivation_edges(
    storage: Storage, active_edges: frozenset[Hash] | None
) -> list[tuple[Hash, Edge]]:
    """Resolve every edge and keep those that participate in derivation.

    A derivation edge is one that can *establish* a conclusion: verdict PASS or
    SOFT_FLAG, and not a REFUTATION (refutations attack, they do not derive).
    When `active_edges` is given (the IN set from refutation resolution), only
    those edges are considered — this is the composition point that makes
    reachability respect refutation.
    """
    out: list[tuple[Hash, Edge]] = []
    for h in storage.graph.all_edges():
        if active_edges is not None and h not in active_edges:
            continue
        e = resolve_edge(h, storage)
        if e is None:
            continue
        if e.type == EdgeType.REFUTATION:
            continue
        if e.verdict not in (Verdict.PASS, Verdict.SOFT_FLAG):
            continue
        out.append((h, e))
    return out


def _fixpoint(
    derivation_edges: list[tuple[Hash, Edge]],
    extra_seeds: Sequence[Hash],
) -> tuple[dict[Hash, Kappa], dict[Hash, int], dict[Hash, Hash]]:
    """Compute κ (max-min fixpoint) and depth (level-order) for all reachable nodes.

    Returns:
        kappa     — node → strongest κ (max over paths of min over edges)
        depth     — node → minimum proof-tree depth (min over derivations of
                    1 + max(depth[premises]))
        best_edge — node → the edge hash that established it at its best κ
                    (None-valued entries are simply absent; seeds from
                    `extra_seeds` have no edge)
    """
    kappa: dict[Hash, Kappa] = {}
    depth: dict[Hash, int] = {}
    best_edge: dict[Hash, Hash] = {}

    # 1. Seeds: zero-premise edges (definitions/axioms) establish their
    #    conclusion at the edge's own κ, at depth 0.
    for h, e in derivation_edges:
        if len(e.premises) == 0:
            _seed(kappa, depth, best_edge, e.conclusion, e.kappa, h)

    # 2. Hypothetical seeds: established at K_INF, depth 0, no edge.
    for s in extra_seeds:
        _seed(kappa, depth, best_edge, s, Kappa.K_INF, None)

    # 3. κ fixpoint (max-min semiring). Terminates: κ is a finite lattice of
    #    height 5, each node's κ is monotone non-decreasing and bounded by
    #    K_INF, so at most 5·|V| updates.
    changed = True
    while changed:
        changed = False
        for h, e in derivation_edges:
            if len(e.premises) == 0:
                continue
            if not all(p in kappa for p in e.premises):
                continue
            path_kappa = _kappa_min(e.kappa, *[kappa[p] for p in e.premises])
            if e.conclusion not in kappa or rank(path_kappa) > rank(kappa[e.conclusion]):
                kappa[e.conclusion] = path_kappa
                best_edge[e.conclusion] = h
                changed = True

    # 4. Depth: level-order over the established nodes. An edge fires at
    #    1 + max(depth[premises]); a node's depth is the minimum over its
    #    incoming edges. (Parallel steps count once, not summed.)
    changed = True
    while changed:
        changed = False
        for h, e in derivation_edges:
            if len(e.premises) == 0:
                continue
            if e.conclusion not in kappa:
                continue
            if not all(p in depth for p in e.premises):
                continue
            d = 1 + max(depth[p] for p in e.premises)
            if e.conclusion not in depth or d < depth[e.conclusion]:
                depth[e.conclusion] = d
                changed = True

    return kappa, depth, best_edge


def _seed(
    kappa: dict[Hash, Kappa],
    depth: dict[Hash, int],
    best_edge: dict[Hash, Hash],
    node: Hash,
    k: Kappa,
    edge: Hash | None,
) -> None:
    """Register a seed node (zero-premise edge or hypothetical seed)."""
    if node not in kappa or rank(k) > rank(kappa[node]):
        kappa[node] = k
    depth[node] = 0
    if edge is not None:
        best_edge[node] = edge


def _collect_proof_tree(
    target: Hash,
    best_edge: dict[Hash, Hash],
    edge_map: dict[Hash, Edge],
) -> tuple[Hash, ...]:
    """Collect the sub-hypergraph edges of `target`'s best derivation.

    Walks `best_edge` pointers backward from `target` to the seeds, gathering
    every edge in the derivation tree. Deterministic order (sorted by hex).
    """
    edges: set[Hash] = set()
    stack = [target]
    while stack:
        node = stack.pop()
        h = best_edge.get(node)
        if h is None or h in edges:
            continue
        edges.add(h)
        e = edge_map.get(h)
        if e is not None:
            stack.extend(e.premises)
    return tuple(sorted(edges, key=lambda x: x.hex()))


def reachable(
    target: Hash,
    storage: Storage,
    min_kappa: Kappa = Kappa.K0,
    extra_seeds: Sequence[Hash] = (),
    active_edges: frozenset[Hash] | None = None,
) -> ReachabilityResult:
    """Answer "is `target` derivable from the seed set, at κ ≥ `min_kappa`?"

    `extra_seeds` injects conditional assumptions ("if we assume H, does C
    follow?") treated as established at K_INF for the duration of the query,
    without mutating storage.

    `active_edges` restricts the derivation to a given edge set — the natural
    composition point with `refutation.compute_active_subgraph`, so that a
    refuted edge does not contribute to reachability.
    """
    derivation_edges = _derivation_edges(storage, active_edges)
    kappa, depth, best_edge = _fixpoint(derivation_edges, extra_seeds)

    if target not in kappa:
        return ReachabilityResult(target, False, None, None, ())

    k = kappa[target]
    d = depth[target]
    established = rank(k) >= rank(min_kappa)
    edge_map = {h: e for h, e in derivation_edges}
    proof_tree = _collect_proof_tree(target, best_edge, edge_map)

    return ReachabilityResult(target, established, k, d, proof_tree)
