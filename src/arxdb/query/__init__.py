"""Query layer (Phase 3) — the product.

AND-OR hyperpath traversal, proof-tree assembly, κ-threshold filtering,
refutation resolution. The two queries: reachability and path discovery.

Public API:
    resolve_node, resolve_edge          — hash → Node/Edge records
    reachable, ReachabilityResult       — "have we reasoned about this before?"
    path_discovery, PathResult, MissingEdge — "what would it take?"
    compute_active_subgraph, ActiveSubgraph — refutation resolution (grounded)
"""

from .path import MissingEdge, PathResult, path_discovery
from .reachability import ReachabilityResult, reachable
from .refutation import ActiveSubgraph, compute_active_subgraph
from .resolve import resolve_edge, resolve_node

__all__ = [
    "resolve_node",
    "resolve_edge",
    "reachable",
    "ReachabilityResult",
    "path_discovery",
    "PathResult",
    "MissingEdge",
    "compute_active_subgraph",
    "ActiveSubgraph",
]
