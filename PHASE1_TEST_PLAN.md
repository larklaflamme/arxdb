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

## 2.5. `test_keys.py`

| Test | Assertion |
|------|-----------|
| `test_keypair_sizes` | `len(priv) == 32`; `len(pub) == 32` |
| `test_signature_size` | `len(sig) == 64` |
| `test_sign_verify_roundtrip` | `verify(pub, msg, sign(priv, msg)) is True` |
| `test_wrong_message_fails` | verify against a different message → `False` |
| `test_wrong_key_fails` | verify against a different pubkey → `False` |
| `test_tampered_signature_fails` | flip a signature bit → `False` |
| `test_deterministic_signature` | same key + message → byte-identical signature |
| `test_distinct_keys_distinct_pubkeys` | two keypairs → distinct priv and pub |
| `test_malformed_priv_raises` | `sign` with wrong-length priv → `ValueError` |
| `test_malformed_pub_raises` | `verify` with wrong-length pub → `ValueError` |
| `test_malformed_sig_raises` | `verify` with wrong-length sig → `ValueError` |

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
| `test_register_and_connectivity` | register nodes + edge, `get_connectivity(e)` returns `(premises, conclusion)` |
| `test_incoming_outgoing` | `incoming_edges(C)` and `outgoing_edges(A)`/`outgoing_edges(B)` include the edge (hyperedge multi-premise) |
| `test_premise_order_preserved` | premises `(A,B)` returned in exact order (non-commutative rules) |
| `test_unregistered_node_empty` | `incoming_edges`/`outgoing_edges` of an unregistered node are `[]` |
| `test_missing_edge` | `get_connectivity(unknown) is None` |
| `test_duplicate_node_no_error` | re-registering a node is an idempotent no-op |

## 5. `test_merkle.py`

| Test | Assertion |
|------|-----------|
| `test_empty_sentinel` | empty tree root == `BLAKE3(0x02 ‖ "")` |
| `test_single_leaf` | single-leaf root == `BLAKE3(0x00 ‖ leaf)` |
| `test_two_leaves` | root == `BLAKE3(0x01 ‖ leaf_node(0) ‖ leaf_node(1))` |
| `test_odd_count` | odd leaf count duplicates last node: `root([a,b,c]) == root([a,b,c,c])` |
| `test_root_deterministic` | same leaves → same root |
| `test_root_changes_on_append` | appending a leaf changes the root |
| `test_inclusion_proof_valid` | `verify_inclusion(proof, root)` is `True` for every index |
| `test_tamper_detected` | forged leaf hash → `verify_inclusion` is `False` |
| `test_second_preimage_resisted` | an internal node hash cannot be verified as an authentic leaf |

## 6. `test_append_log.py`

| Test | Assertion |
|------|-----------|
| `test_append_and_get` | first append → `seq == 0`; `get(0)` returns the appended `LogEntry` |
| `test_len` | `len()` tracks append count |
| `test_empty_state` | `len() == 0`; `get(0) is None`; `root_hash()` returns the deterministic sentinel |
| `test_genesis_prev_hash` | entry 0 has `prev_log_hash == b"\x00" * 34` |
| `test_hash_chain` | each entry's `prev_log_hash` == prior entry's `entry_hash` |
| `test_signature_valid` | `verify_entry(entry)` is `True` (signature over the full metadata tuple) |
| `test_bad_signature_rejected` | flipping a signature bit → `verify_entry` is `False` |
| `test_tampered_payload_rejected` | changing the payload → `verify_entry` is `False` (`entry_hash` mismatch) |
| `test_root_changes` | `root_hash()` changes after each append |
| `test_root_and_inclusion` | `verify_inclusion(get_inclusion_proof(seq))` is `True` for all seq |

## 7. `test_storage_tx.py` (the atomicity contract)

| Test | Assertion |
|------|-----------|
| `test_commit_roundtrip` | `commit_edge_tx` returns `(edge_hash, log_entry)`; edge retrievable from ObjectStore; connectivity registered; log entry present |
| `test_commit_with_proof` | proof bytes stored and retrievable by their own content hash |
| `test_atomic_on_failure` | graph-step failure (monkeypatched `register_edge`) → no edge, no log entry; object blob orphaned (harmless) |
| `test_atomic_on_log_failure` | log-step failure (monkeypatched `append`) → graph rolled back, no log entry |
| `test_crash_recovery` | 100 `commit_edge_tx`, `close()`, reopen → all objects, connections, log entries, and `root_hash` match exactly |

## Fault injection coverage (`test_storage_tx.py`)

Faults are injected via pytest `monkeypatch` (no built-in hooks in the storage
layer — Phase 1 keeps it dumb). The two transaction-step failures are covered
by `test_atomic_on_failure` (graph) and `test_atomic_on_log_failure` (log); the
crash case is covered by `test_crash_recovery` (close + reopen from disk).

| Fault | Injection | Expected |
|-------|-----------|----------|
| **Fault 1** | ObjectStore write failure (disk full / permission error) | no GraphIndex or LogEntry created (trivially — ObjectStore runs first) |
| **Fault 2** | Graph or log step raises mid-transaction | `ROLLBACK` → no edge, no log entry; object blob orphaned (harmless) |
| **Fault 3** | Simulated crash after SQLite write before return | state remains recoverable and non-corrupted (WAL durability) |

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
