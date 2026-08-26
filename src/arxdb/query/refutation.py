"""refutation.py — refutation resolution: the active subgraph (grounded).

Revocation is a first-class edge type, not a deletion. A REFUTATION edge
attacks its target (another edge, or a claim in contention), and the query
layer computes the **active subgraph** — which edges are IN (valid), OUT
(defeated), or UNDECIDED (unresolvable mutual cycles).

Resolved semantics: **Dung's grounded extension over edges** (skeptical,
poly-time, deterministic):

    - an edge is IN  iff it is not attacked by any IN edge;
    - an edge is OUT iff it is attacked by ≥1 IN edge;
    - the grounded extension is the least fixpoint of this labeling.

Attack graph:
    - a REFUTATION edge whose `conclusion == E_target.edge_hash()` attacks
      `E_target`;
    - two edges concluding the same proposition (claim + domain) with opposite
      polarity are in contention (mutual attack).

Boundary discipline: resolve via ObjectStore decode, read adjacency via public
`Storage.graph` methods. No sqlite3, no pathlib, no private storage attributes.

Public API:
    ActiveSubgraph          — in_edges, out_edges, undecided_edges
    compute_active_subgraph(storage) -> ActiveSubgraph
"""

from __future__ import annotations

from dataclasses import dataclass

from arxdb.storage.hashing import Hash
from arxdb.storage.storage import Storage

from arxdb.verification.schema import Edge, EdgeType

from .resolve import resolve_edge, resolve_node


@dataclass(frozen=True)
class ActiveSubgraph:
    """The grounded labeling of the edge graph.

    `in_edges` is the active subgraph — the edges that survive refutation and
    may contribute to reachability. `out_edges` are defeated. `undecided_edges`
    are trapped in unresolvable mutual cycles (skeptically excluded).
    """

    in_edges: frozenset[Hash]
    out_edges: frozenset[Hash]
    undecided_edges: frozenset[Hash]


def compute_active_subgraph(storage: Storage) -> ActiveSubgraph:
    """Compute the grounded extension over all stored edges.

    Returns the IN/OUT/UNDECIDED labeling. The active subgraph is `in_edges`;
    pass it to `reachable(..., active_edges=...)` to make reachability respect
    refutation (a refuted edge no longer contributes to derivation).
    """
    edges: dict[Hash, Edge] = {}
    for h in storage.graph.all_edges():
        e = resolve_edge(h, storage)
        if e is not None:
            edges[h] = e

    # Attack graph: attackers[h] = edges h attacks; attacked_by[h] = edges
    # attacking h.
    attackers: dict[Hash, set[Hash]] = {h: set() for h in edges}
    attacked_by: dict[Hash, set[Hash]] = {h: set() for h in edges}

    # 1. Refutation attacks: a REFUTATION edge attacks the edge whose hash is
    #    its conclusion.
    for h, e in edges.items():
        if e.type == EdgeType.REFUTATION:
            target = e.conclusion
            if target in edges:
                attackers[h].add(target)
                attacked_by[target].add(h)

    # 2. Contention: edges concluding the same proposition with opposite
    #    polarity attack each other.
    by_prop: dict[tuple[str, str], list[tuple[Hash, bool]]] = {}
    for h, e in edges.items():
        n = resolve_node(e.conclusion, storage)
        if n is None:
            continue
        by_prop.setdefault((n.claim, n.domain), []).append((h, n.polarity))
    for items in by_prop.values():
        pos = [h for h, pol in items if pol]
        neg = [h for h, pol in items if not pol]
        for h1 in pos:
            for h2 in neg:
                attackers[h1].add(h2)
                attackers[h2].add(h1)
                attacked_by[h1].add(h2)
                attacked_by[h2].add(h1)

    # 3. Grounded labeling: least fixpoint of IN/OUT.
    in_edges: set[Hash] = set()
    out_edges: set[Hash] = set()
    changed = True
    while changed:
        changed = False
        for h in edges:
            if h in in_edges or h in out_edges:
                continue
            # h is IN iff every attacker of h is already OUT (vacuously true
            # when h has no attackers).
            if all(a in out_edges for a in attacked_by[h]):
                in_edges.add(h)
                changed = True
                for t in attackers[h]:
                    if t not in out_edges:
                        out_edges.add(t)
                        changed = True

    undecided = set(edges) - in_edges - out_edges
    return ActiveSubgraph(
        frozenset(in_edges), frozenset(out_edges), frozenset(undecided)
    )
