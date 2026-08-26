"""Serialization — canonical CBOR encode/decode.

Canonical encoding is the foundation of content-addressing: two structurally
equal objects must produce byte-identical encodings. We use cbor2 with
canonical ordering (sorted map keys, definite-length forms).

Invariant:
    canonical_encode(x) == canonical_encode(y)  iff  x == y (structurally)

Custom types are canonicalized before encoding:
    - dict      -> keys and values canonicalized; cbor2 sorts keys
    - list/tuple-> definite-length array (tuples decode as lists)
    - set       -> sorted list (sorted by canonical encoding of each element)
    - Hash      -> byte string (it is a bytes subclass, so it round-trips)

Public API (Phase 1):
    canonical_encode(obj) -> bytes
    canonical_decode(data: bytes) -> obj
"""

from __future__ import annotations

import cbor2


def _canonicalize(obj):
    """Recursively convert `obj` to a canonical Python structure.

    The result is a structure cbor2 can encode deterministically: dicts with
    canonicalized keys/values, lists in place of tuples, sorted lists in place
    of sets, and bytes (including Hash) left as-is.
    """
    if isinstance(obj, dict):
        return {_canonicalize(k): _canonicalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_canonicalize(x) for x in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted((_canonicalize(x) for x in obj), key=_sort_key)
    if isinstance(obj, bytes):
        return obj  # includes Hash (bytes subclass)
    return obj  # str, int, float, bool, None


def _sort_key(x):
    """Deterministic sort key for heterogeneous set elements.

    Sorting by the canonical CBOR encoding of each element gives a total order
    that does not depend on Python's (type-restricted) comparison operators.
    """
    return cbor2.dumps(x, canonical=True)


def canonical_encode(obj) -> bytes:
    """Encode `obj` to deterministic CBOR bytes (sorted keys, definite length)."""
    return cbor2.dumps(_canonicalize(obj), canonical=True)


def canonical_decode(data: bytes):
    """Decode canonical CBOR bytes back to a Python object."""
    return cbor2.loads(data)
