"""Tests for roster.py — the genesis roster."""

from __future__ import annotations

import pytest

from arxdb.attestation.roster import Roster
from arxdb.storage.keys import generate_keypair


def _roster() -> Roster:
    _, skye_pub = generate_keypair()
    _, lark_pub = generate_keypair()
    return Roster(entries={"Skye": skye_pub, "Lark": lark_pub})


def test_roster_round_trip():
    r = _roster()
    r2 = Roster.from_bytes(r.roster_bytes())
    assert r2.entries == r.entries


def test_roster_content_addressed():
    _, skye_pub = generate_keypair()
    _, lark_pub = generate_keypair()
    r1 = Roster(entries={"Skye": skye_pub, "Lark": lark_pub})
    r2 = Roster(entries={"Skye": skye_pub, "Lark": lark_pub})
    assert r1.roster_hash() == r2.roster_hash()
    # Reorder -> different: order is meaningful (append-only rotation).
    r3 = Roster(entries={"Lark": lark_pub, "Skye": skye_pub})
    assert r3.roster_hash() != r1.roster_hash()


def test_resolve_identify():
    r = _roster()
    skye_pub = r.resolve("Skye")
    assert skye_pub is not None
    assert r.identify(skye_pub) == "Skye"


def test_unknown_agent():
    r = _roster()
    assert r.resolve("nobody") is None
    _, unknown_pub = generate_keypair()
    assert r.identify(unknown_pub) is None


def test_rejects_bad_pubkey_length():
    with pytest.raises(ValueError):
        Roster(entries={"Skye": b"short"})


def test_rejects_empty_agent_id():
    _, pub = generate_keypair()
    with pytest.raises(ValueError):
        Roster(entries={"": pub})
