"""Hashing — BLAKE3 multihash and the `Hash` type.

A `Hash` is a 34-byte multihash: `0x1e` (BLAKE3 code) ‖ `0x20` (32-byte length)
‖ 32-byte BLAKE3 digest. The multihash prefix makes the hash algorithm
self-describing, so a future algorithm migration does not break stored objects.

Public API (Phase 1):
    Hash            — bytes subclass carrying the 34-byte multihash
    hash_bytes(data: bytes) -> Hash
    hash_hex(data: bytes) -> str
    from_hex(hexstr: str) -> Hash
    is_valid_hash(h: bytes) -> bool
"""

from __future__ import annotations

import blake3

# Multihash constants
BLAKE3_CODE = 0x1E
BLAKE3_LEN = 0x20
HASH_SIZE = 34  # 1 (code) + 1 (len) + 32 (digest)


class Hash(bytes):
    """A 34-byte multihash (BLAKE3). Subclasses bytes for zero-copy interop."""

    def __new__(cls, raw: bytes) -> "Hash":
        if len(raw) != HASH_SIZE:
            raise ValueError(f"Hash must be {HASH_SIZE} bytes, got {len(raw)}")
        return super().__new__(cls, raw)

    def hex(self) -> str:
        return bytes(self).hex()


def hash_bytes(data: bytes) -> Hash:
    """Return the 34-byte BLAKE3 multihash of `data`."""
    digest = blake3.blake3(data).digest()
    return Hash(bytes([BLAKE3_CODE, BLAKE3_LEN]) + digest)


def hash_hex(data: bytes) -> str:
    """Return the hex string of the multihash of `data`."""
    return hash_bytes(data).hex()


def from_hex(hexstr: str) -> Hash:
    """Reconstruct a Hash from its hex string."""
    return Hash(bytes.fromhex(hexstr))


def is_valid_hash(h: bytes) -> bool:
    """True iff `h` is a well-formed 34-byte BLAKE3 multihash."""
    return (
        len(h) == HASH_SIZE
        and h[0] == BLAKE3_CODE
        and h[1] == BLAKE3_LEN
    )
