"""Keys — Ed25519 keypairs, signing, verification.

Each agent holds an Ed25519 keypair. The append log is signed so that every
entry is attributable to the agent that produced it.

Invariants (Phase 1):
    - public key is exactly 32 bytes
    - signature is exactly 64 bytes
    - raw byte exports via `public_bytes_raw()` / `private_bytes_raw()`

Public API (Phase 1):
    generate_keypair() -> (priv_bytes, pub_bytes)
    sign(priv_bytes, message: bytes) -> sig_bytes
    verify(pub_bytes, message: bytes, sig_bytes) -> bool
"""

from __future__ import annotations

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

PUBLIC_KEY_SIZE = 32
PRIVATE_KEY_SIZE = 32
SIGNATURE_SIZE = 64


def generate_keypair() -> tuple[bytes, bytes]:
    """Return (private_key, public_key) as raw Ed25519 bytes.

    The private key is the 32-byte seed (Ed25519's canonical private form);
    the public key is the 32-byte compressed point.
    """
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    return (
        priv.private_bytes_raw(),
        pub.public_bytes_raw(),
    )


def sign(priv: bytes, message: bytes) -> bytes:
    """Sign `message` with `priv`, returning the 64-byte signature.

    `priv` must be the 32-byte seed produced by `generate_keypair`.
    """
    if len(priv) != PRIVATE_KEY_SIZE:
        raise ValueError(
            f"private key must be {PRIVATE_KEY_SIZE} bytes, got {len(priv)}"
        )
    key = Ed25519PrivateKey.from_private_bytes(priv)
    return key.sign(message)


def verify(pub: bytes, message: bytes, sig: bytes) -> bool:
    """Verify `sig` over `message` against `pub`.

    Returns True iff the signature is valid. A malformed public key or
    signature (wrong length) raises `ValueError`; a well-formed but incorrect
    signature returns False.
    """
    if len(pub) != PUBLIC_KEY_SIZE:
        raise ValueError(
            f"public key must be {PUBLIC_KEY_SIZE} bytes, got {len(pub)}"
        )
    if len(sig) != SIGNATURE_SIZE:
        raise ValueError(
            f"signature must be {SIGNATURE_SIZE} bytes, got {len(sig)}"
        )
    key = Ed25519PublicKey.from_public_bytes(pub)
    try:
        key.verify(sig, message)
    except InvalidSignature:
        return False
    return True
