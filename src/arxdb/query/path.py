"""path.py — path discovery: "what would it take to reason about this?"

The second of the two queries. It reports the minimum proof-tree depth to a
target, and — when the target is not yet derivable — the *goal-specific*
missing-edge frontier: the unestablished premises in the target's backward
dependency cone (not the global frontier of every missing lemma in the DB).

Boundary discipline: same as reachability — resolve via ObjectStore decode,
read adjacency via public `Storage.graph` methods. No sqlite3, no pathlib, no
private storage attributes.

Public API:
    MissingEdge      — conclusion, premises, blocking_nodes, rule
    PathResult       — target, reachable, depth, kappa, missing_edges
    path_discovery(target, storage) -> PathResult
"""

from __future__ import annotations

from dataclasses import dataclass

from arxdb.storage.hashing import Hash
from arxdb.storage.storage import Storage

from arxdb.verification.kappa import Kappa

from .reachability import _derivation_edges, _fixpoint


@dataclass(frozen=True)
class MissingEdge:
    """A single gap in the target's dependency cone.

    `conclusion` is the node that needs establishing. `premises` is the full
    premise set of a candidate edge that would establish it; `blocking_nodes`
    is the subset of those premises that are not yet established (and therefore
    block the derivation). `rule` is the candidate edge's rule.

    A leaf (a node with no incoming derivation edge at all) is reported with
    empty `premises`, empty `blocking_nodes`, and empty `rule` — the signal
    that it needs a zero-premise definition/axiom to be grounded.
    """

    conclusion: Hash
    premises: tuple[Hash, ...]
    blocking_nodes: tuple[Hash, ...]
    rule: str


@dataclass(frozen=True)
class PathResult:
    """The outcome of a path-discovery query.

    When `reachable` is True, `depth` and `kappa` describe the best derivation
    and `missing_edges` is empty. When False, `depth`/`kappa` are None and
    `missing_edges` names the goal-specific frontier.
    """

    target: Hash
    reachable: bool
    depth: int | None
    kappa: Kappa | None
    missing_edges: tuple[MissingEdge, ...]


def path_discovery(target: Hash, storage: Storage) -> PathResult:
    """Report the minimum proof-tree depth to `target`, or the missing frontier.

    Forward reachability first (to know what is already established); if the
    target is established, return the depth and κ. Otherwise traverse backward
    from the target along candidate derivation edges, collecting the
    unestablished premises in its dependency cone as the goal-specific missing
    frontier.
    """
    derivation_edges = _derivation_edges(storage, None)
    kappa, depth, _ = _fixpoint(derivation_edges, ())
    established = set(kappa)

    if target in established:
        return PathResult(target, True, depth[target], kappa[target], ())

    edge_map = {h: e for h, e in derivation_edges}
    missing: list[MissingEdge] = []
    visited: set[Hash] = set()
    stack = [target]

    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)

        # Candidate derivation edges that conclude `node` (refutation and
        # vetoed edges are excluded by the edge_map filter).
        incoming = [
            (h, edge_map[h])
            for h in storage.graph.incoming_edges(node)
            if h in edge_map
        ]

        if not incoming:
            # Leaf: nothing establishes this node — it needs a definition.
            missing.append(MissingEdge(node, (), (), ""))
            continue

        for h, e in incoming:
            blocking = tuple(p for p in e.premises if p not in established)
            if blocking:
                missing.append(MissingEdge(node, e.premises, blocking, e.rule))
                for p in blocking:
                    stack.append(p)

    return PathResult(target, False, None, None, tuple(missing))
