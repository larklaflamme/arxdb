"""Generate the frozen cross-language parity test-vector corpus.

This is the reference implementation (Python) producing the *expected* outputs
that the Go side must match byte-for-byte. The discipline (PHASE6_PLAN.md §4)
is: freeze a corpus and assert byte-equality — do not trust the libraries.

Output: tests/parity_vectors.json

Tag scheme for CBOR inputs (so both Python and Go can reconstruct the value
exactly — JSON numbers are float64 and would silently round large integers):
    {"$b": "hex"}          -> bytes
    {"$i": "decimal"}      -> int   (decimal string, exact — avoids float64 rounding)
    {"$f": number}         -> float (JSON number == float64 == Python float)
    plain string           -> str
    plain bool             -> bool
    null                   -> None / nil
    plain array            -> list
    plain object           -> map (string keys only — matches the data model)
"""

from __future__ import annotations

import json

import blake3
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from arxdb.storage.hashing import hash_bytes
from arxdb.storage.merkle import root_hash
from arxdb.storage.serialization import canonical_encode

# --- Fixed Ed25519 keypair (deterministic seed) ---------------------------
SEED = bytes(range(32))
_priv = Ed25519PrivateKey.from_private_bytes(SEED)
PUBLIC_KEY = _priv.public_key().public_bytes_raw()

# A fixed nanosecond timestamp (deterministic, plausible magnitude).
FIXED_TS_NS = 1700000000000000000


def to_json_tagged(obj):
    """Convert a Python value to its tagged JSON form."""
    if isinstance(obj, bytes):
        return {"$b": obj.hex()}
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, int):
        return {"$i": str(obj)}
    if isinstance(obj, float):
        return {"$f": obj}
    if isinstance(obj, str):
        return obj
    if isinstance(obj, (list, tuple)):
        return [to_json_tagged(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_json_tagged(v) for k, v in obj.items()}
    if obj is None:
        return None
    raise TypeError(f"unhandled type {type(obj)}")


# --- CBOR vectors ---------------------------------------------------------
# A 34-byte Hash (0x1e 0x20 + 32-byte digest).
HASH_ZERO = bytes([0x1E, 0x20]) + b"\x00" * 32
HASH_FF = bytes([0x1E, 0x20]) + b"\xff" * 32

# The exact shape of the append-log signature message (5-tuple).
SIG_MSG = [
    0,                          # seq
    FIXED_TS_NS,                # timestamp_ns
    PUBLIC_KEY,                 # signer_pubkey
    HASH_ZERO,                  # entry_hash
    HASH_ZERO,                  # prev_log_hash
]

# A realistic edge payload (dict with string keys, matching schema.py shape).
EDGE_PAYLOAD = {
    "type": "citation",
    "rule": "Euler product + explicit formula",
    "premises": [HASH_ZERO.hex(), HASH_FF.hex()],
    "conclusion": HASH_ZERO.hex(),
    "kappa": "K1",
    "domain": "number_theory",
}

cbor_cases = [
    ("empty_bytes", b""),
    ("single_zero_byte", b"\x00"),
    ("hash_zeros", HASH_ZERO),
    ("hash_ff", HASH_FF),
    ("empty_string", ""),
    ("ascii_string", "hello world"),
    ("unicode_string", "héllo wörld 你好"),
    ("int_0", 0),
    ("int_23", 23),
    ("int_24", 24),
    ("int_255", 255),
    ("int_256", 256),
    ("int_65535", 65535),
    ("int_65536", 65536),
    ("int_2pow32", 2**32),
    ("int_max_int64", 2**63 - 1),
    ("int_neg1", -1),
    ("int_neg24", -24),
    ("int_neg25", -25),
    ("int_min_int64", -(2**63)),
    ("float_0", 0.0),
    ("float_1", 1.0),
    ("float_half", 0.5),
    ("float_1p5", 1.5),
    ("float_pi", 3.14),
    ("float_neg2p5", -2.5),
    ("float_1e300", 1e300),
    ("true", True),
    ("false", False),
    ("null", None),
    ("empty_list", []),
    ("list_ints", [1, 2, 3]),
    ("nested_list", [[1, 2], [3, [4, 5]]]),
    ("empty_map", {}),
    ("map_str_keys", {"b": 1, "a": 2, "aa": 3}),
    ("nested_map", {"a": [1, {"b": 2}], "c": None}),
    ("signature_message", SIG_MSG),
    ("edge_payload", EDGE_PAYLOAD),
]

cbor_vectors = []
for name, value in cbor_cases:
    cbor_vectors.append({
        "name": name,
        "input": to_json_tagged(value),
        "expected": canonical_encode(value).hex(),
    })

# --- BLAKE3 vectors (input is always bytes) ------------------------------
blake3_cases = [
    ("empty", b""),
    ("hello", b"hello"),
    ("zeros_32", b"\x00" * 32),
    ("unicode", "héllo wörld 你好".encode()),
    ("bytes_0_255", bytes(range(256))),
    ("edge_payload_cbor", canonical_encode(EDGE_PAYLOAD)),
]

blake3_vectors = []
for name, data in blake3_cases:
    blake3_vectors.append({
        "name": name,
        "input_hex": data.hex(),
        "expected": hash_bytes(data).hex(),
    })

# --- Ed25519 vectors (fixed seed) ----------------------------------------
ed25519_cases = [
    ("empty", b""),
    ("hello", b"hello"),
    ("quick_brown_fox", b"the quick brown fox"),
    ("signature_message", canonical_encode(SIG_MSG)),
]

ed25519_vectors = []
for name, msg in ed25519_cases:
    ed25519_vectors.append({
        "name": name,
        "message_hex": msg.hex(),
        "expected": _priv.sign(msg).hex(),
    })

# --- Merkle vectors (root_hash over leaf hashes) -------------------------
def leaf(i: int) -> bytes:
    return hash_bytes(f"leaf-{i}".encode())

merkle_cases = [
    ("empty", []),
    ("single", [leaf(0)]),
    ("two", [leaf(0), leaf(1)]),
    ("three", [leaf(0), leaf(1), leaf(2)]),
    ("five", [leaf(0), leaf(1), leaf(2), leaf(3), leaf(4)]),
]

merkle_vectors = []
for name, leaves in merkle_cases:
    merkle_vectors.append({
        "name": name,
        "leaf_hexes": [l.hex() for l in leaves],
        "expected": root_hash(leaves).hex(),
    })

# --- Assemble -------------------------------------------------------------
corpus = {
    "meta": {
        "generator": "python",
        "cbor2": "6.1.4",
        "blake3": "1.0.9",
        "cryptography": "50.0.1",
        "seed_hex": SEED.hex(),
        "public_key_hex": PUBLIC_KEY.hex(),
        "fixed_timestamp_ns": FIXED_TS_NS,
    },
    "cbor": cbor_vectors,
    "blake3": blake3_vectors,
    "ed25519": ed25519_vectors,
    "merkle": merkle_vectors,
}

out = "tests/parity_vectors.json"
with open(out, "w") as f:
    json.dump(corpus, f, indent=2, ensure_ascii=False)
    f.write("\n")

print(f"wrote {out}")
print(f"  cbor:    {len(cbor_vectors)} vectors")
print(f"  blake3:  {len(blake3_vectors)} vectors")
print(f"  ed25519: {len(ed25519_vectors)} vectors")
print(f"  merkle:  {len(merkle_vectors)} vectors")
