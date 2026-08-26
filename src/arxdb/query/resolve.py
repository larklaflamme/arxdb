"""resolve.py — hash → Node/Edge record resolution.

The query layer's only way to turn a content address back into a meaningful
record. It decodes ObjectStore blobs (never reaching into SQLite): a node hash
resolves to a `Node`, an edge hash to an `Edge`.

Boundary discipline: this module uses only the public `Storage.objects.get`
primitive and the schema's `from_bytes` decoders. No sqlite3, no pathlib, no
private storage attributes.

Public API:
    resolve_node(h: Hash, storage: Storage) -> Node | None
    resolve_edge(h: Hash, storage: Storage) -> Edge | None
"""

from __future__ import annotations

from arxdb.storage.hashing import Hash
from arxdb.storage.storage import Storage

from arxdb.verification.schema import Edge, Node


def resolve_node(h: Hash, storage: Storage) -> Node | None:
    """Resolve a node hash to its `Node` record, or None.

    Returns None when the hash is absent from the ObjectStore, or when the
    blob at that address is not a node (e.g. it is an edge or a proof blob).
    A node and an edge have disjoint canonical key sets, so a decode failure
    cleanly distinguishes "not a node" from "corrupt node" — and for the query
    layer's purpose both are "I cannot use this as a node", hence None.
    """
    data = storage.objects.get(h)
    if data is None:
        return None
    try:
        return Node.from_bytes(data)
    except Exception:
        return None


def resolve_edge(h: Hash, storage: Storage) -> Edge | None:
    """Resolve an edge hash to its `Edge` record, or None.

    Returns None when the hash is absent, or when the blob at that address is
    not an edge (e.g. it is a node or a proof blob). See `resolve_node` for the
    disjoint-key rationale.
    """
    data = storage.objects.get(h)
    if data is None:
        return None
    try:
        return Edge.from_bytes(data)
    except Exception:
        return None
