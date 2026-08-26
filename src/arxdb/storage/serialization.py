"""Serialization — canonical CBOR encode/decode.

Canonical encoding is the foundation of content-addressing: two structurally
equal objects must produce byte-identical encodings. We use cbor2 with
canonical ordering (sorted map keys, definite-length forms).

Invariant:
    canonical_encode(x) == canonical_encode(y)  iff  x == y (structurally)

Public API (Phase 1):
    canonical_encode(obj) -> bytes
    canonical_decode(data: bytes) -> obj
"""

from __future__ import annotations


def canonical_encode(obj) -> bytes:
    """Encode `obj` to deterministic CBOR bytes (sorted keys, definite length)."""
    raise NotImplementedError


def canonical_decode(data: bytes):
    """Decode canonical CBOR bytes back to a Python object."""
    raise NotImplementedError
