"""Keys — Ed25519 keypairs, signing, verification.

Each agent holds an Ed25519 keypair. The append log is signed so that every
entry is attributable to the agent that produced it.

Public API (Phase 1):
    generate_keypair() -> (priv_bytes, pub_bytes)
    sign(priv_bytes, message: bytes) -> sig_bytes
    verify(pub_bytes, message: bytes, sig_bytes) -> bool
"""

from __future__ import annotations


def generate_keypair() -> tuple[bytes, bytes]:
    """Return (private_key, public_key) as raw Ed25519 bytes."""
    raise NotImplementedError


def sign(priv: bytes, message: bytes) -> bytes:
    """Sign `message` with `priv`, returning the 64-byte signature."""
    raise NotImplementedError


def verify(pub: bytes, message: bytes, sig: bytes) -> bool:
    """Verify `sig` over `message` against `pub`. Raises on malformed input."""
    raise NotImplementedError
