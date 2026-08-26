"""Shared pytest fixtures: temp storage roots and keypairs."""

from __future__ import annotations

import pytest

from arxdb.storage.keys import generate_keypair


@pytest.fixture
def keypair() -> tuple[bytes, bytes]:
    """A fresh Ed25519 keypair for each test."""
    return generate_keypair()


@pytest.fixture
def tmp_root(tmp_path):
    """A fresh storage root directory for each test."""
    return tmp_path / "arxdb"
