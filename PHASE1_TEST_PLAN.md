# ArxDB — Phase 1 Test Plan

**Framework:** `pytest`. **Property tests:** `hypothesis` (dev dependency).
**Fixtures:** `tests/conftest.py` provides a temp-dir store and a fresh Ed25519
keypair per test.

**Definition of done:** every test below passes, no skips, no xfails.

---

## 1. `test_hashing.py`

| Test | Assertion |
|------|-----------|
| `test_deterministic` | `hash_bytes(x) == hash_bytes(x)` |
| `test_distinct` | `hash_bytes(b"a") != hash_bytes(b"b")` |
| `test_hex_roundtrip` | `from_hex(to_hex(h)) == h` |
| `test_known_vector` | BLAKE3 of `b""` equals the published empty-input digest |
| `test_multihash_format` | `len(h) == 34`; `h[0] == 0x1e`; `h[1] == 0x20` |

## 2. `test_serialization.py`

| Test | Assertion |
|------|-----------|
| `test_roundtrip` | `canonical_decode(canonical_encode(x)) == x` |
| `test_canonical_key_order` | `encode({"a":1,"b":2}) == encode({"b":2,"a":1})` |
| `test_bytes_stable` | same object → byte-identical output across calls |
| `test_distinct_objects` | different objects → different bytes |
| `test_set_sorted` | `encode({1,2,3}) == encode({3,2,1})` (sets sorted before encoding) |

## 3. `test_object_store.py`

| Test | Assertion |
|------|-----------|
| `test_put_get_roundtrip` | `get(put(x)) == x` |
| `test_idempotent` | `put(x) == put(x)` (same hash, no duplicate file) |
| `test_get_missing` | `get(unknown_hash) is None` |
| `test_has` | `has(put(x))` is `True`; `has(unknown)` is `False` |
| `test_batch` | `get_batch(put_batch(xs)) == xs` |
| `test_empty_batch` | `get_batch([]) == []` |
| `test_persistence` | put, close, reopen → `get` still returns `x` |
| `test_immutable` | re-`put` different bytes → different hash, old object intact |
| `test_sharding` | object stored at `objects/{hash[:2]}/{hash[2:]}` |

## 4. `test_graph_index.py`

| Test | Assertion |
|------|-----------|
| `test_add_node` | node registered, no error on duplicate |
| `test_add_edge_connectivity` | `get_connectivity(e)` returns `(premises, conclusion)` |
| `test_incoming_edges` | `incoming_edges(C)` includes edge whose conclusion is C |
| `test_outgoing_edges` | `outgoing_edges(A)` includes edge whose premises contain A |
| `test_hyperedge_multi_premise` | edge with premises `(A,B)` appears in both `outgoing_edges(A)` and `outgoing_edges(B)` |
| `test_missing_edge` | `get_connectivity(unknown) is None` |
| `test_unregistered_node` | `incoming_edges(unregistered_node) == []` |
| `test_premise_order_preserved` | premises `(A,B)` returned in exact order (non-commutative rules) |

## 5. `test_merkle.py`

| Test | Assertion |
|------|-----------|
| `test_single_leaf` | root == leaf hash |
| `test_two_leaves` | root == `hash(0x01 ‖ leaf0 ‖ leaf1)` |
| `test_odd_count` | odd leaf count duplicates last node (documented behavior) |
| `test_inclusion_proof_valid` | `verify_inclusion(proof, root)` is `True` |
| `test_tamper_detected` | flip a leaf → `verify_inclusion` is `False` |
| `test_root_deterministic` | same leaves → same root |
| `test_second_preimage_resisted` | an internal node hash cannot be verified as an authentic leaf |
| `test_empty_sentinel` | empty tree root == `BLAKE3(0x02 ‖ "")` |

## 6. `test_append_log.py`

| Test | Assertion |
|------|-----------|
| `test_append_seq` | first append → `seq == 0`; second → `seq == 1` |
| `test_get_roundtrip` | `get(seq)` returns the appended `LogEntry` |
| `test_len` | `len()` tracks append count |
| `test_empty_state` | `len() == 0`; `get(0) is None`; `root_hash()` returns the deterministic sentinel |
| `test_prev_hash_chain` | each entry's `prev_log_hash` == prior entry's hash |
| `test_genesis_prev_hash` | entry 0 has `prev_log_hash == b"\x00" * 34` |
| `test_signature_valid` | `verify(pub, entry_hash, signature)` is `True` |
| `test_bad_signature_rejected` | append with wrong signature raises |
| `test_root_changes` | `root_hash()` changes after each append |
| `test_inclusion_proof` | `verify_inclusion(get_inclusion_proof(seq))` is `True` for all seq |

## 7. `test_storage_tx.py` (the atomicity contract)

| Test | Assertion |
|------|-----------|
| `test_commit_roundtrip` | `commit_edge_tx` returns `(edge_hash, log_entry)`; edge retrievable from ObjectStore; connectivity registered; log entry present |
| `test_commit_with_proof` | proof bytes stored and retrievable |
| `test_atomic_on_failure` | inject failure at step 2 → no partial state (no half-registered edge, no log entry) |
| `test_atomic_on_log_failure` | inject failure at step 3 → graph rolled back, no log entry |
| `test_crash_recovery` | 100 `commit_edge_tx`, close, reopen → all objects, connections, log entries, and `root_hash` match exactly |

## Fault injection coverage (`test_storage_tx.py`)

| Fault | Injection | Expected |
|-------|-----------|----------|
| **Fault 1** | ObjectStore write failure (disk full / permission error) | no GraphIndex or LogEntry created |
| **Fault 2** | Signature verification failure | transaction rejected, no GraphIndex or LogEntry committed |
| **Fault 3** | Simulated crash after SQLite write before return | state remains recoverable and non-corrupted |

## Property-based tests (`hypothesis`)

- `test_put_get_roundtrip_property`: for arbitrary `bytes`, `get(put(x)) == x`.
- `test_idempotent_property`: for arbitrary `bytes`, `put(x) == put(x)`.
- `test_serialization_roundtrip_property`: for arbitrary nested dict/list/bytes,
  `decode(encode(x)) == x`.

## How to run

```bash
cd /home/ubuntu/arxdb
conda activate arxdb
pytest -v
```

**Sign-off gate:** Lark reviews the green test run, then we commit and proceed
to Phase 2 (edge schema + verification) — *not before*.
