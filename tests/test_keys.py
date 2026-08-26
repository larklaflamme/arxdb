"""Tests for keys.py — Ed25519 keypairs, signing, verification."""

from __future__ import annotations

import pytest

from arxdb.storage.keys import (
    PRIVATE_KEY_SIZE,
    PUBLIC_KEY_SIZE,
    SIGNATURE_SIZE,
    generate_keypair,
    sign,
    verify,
)


def test_keypair_sizes():
    priv, pub = generate_keypair()
    assert len(priv) == PRIVATE_KEY_SIZE == 32
    assert len(pub) == PUBLIC_KEY_SIZE == 32


def test_signature_size():
    priv, _ = generate_keypair()
    sig = sign(priv, b"hello")
    assert len(sig) == SIGNATURE_SIZE == 64


def test_sign_verify_roundtrip():
    priv, pub = generate_keypair()
    msg = b"the quick brown fox"
    sig = sign(priv, msg)
    assert verify(pub, msg, sig) is True


def test_wrong_message_fails():
    priv, pub = generate_keypair()
    sig = sign(priv, b"original")
    assert verify(pub, b"tampered", sig) is False


def test_wrong_key_fails():
    priv, _ = generate_keypair()
    _, other_pub = generate_keypair()
    sig = sign(priv, b"msg")
    assert verify(other_pub, b"msg", sig) is False


def test_tampered_signature_fails():
    priv, pub = generate_keypair()
    sig = bytearray(sign(priv, b"msg"))
    sig[0] ^= 0xFF  # flip a bit
    assert verify(pub, b"msg", bytes(sig)) is False


def test_deterministic_signature():
    """Ed25519 is deterministic: same key + message -> same signature."""
    priv, pub = generate_keypair()
    assert sign(priv, b"msg") == sign(priv, b"msg")


def test_distinct_keys_distinct_pubkeys():
    priv1, pub1 = generate_keypair()
    priv2, pub2 = generate_keypair()
    assert pub1 != pub2
    assert priv1 != priv2


def test_malformed_priv_raises():
    with pytest.raises(ValueError):
        sign(b"short", b"msg")


def test_malformed_pub_raises():
    with pytest.raises(ValueError):
        verify(b"short", b"msg", b"\x00" * SIGNATURE_SIZE)


def test_malformed_sig_raises():
    _, pub = generate_keypair()
    with pytest.raises(ValueError):
        verify(pub, b"msg", b"short")
