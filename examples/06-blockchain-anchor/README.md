# 06 — Blockchain anchor

Commit a single trust anchor, then verify the entire history from *only* that
anchor — no trust in the local database.

## The scenario

You have a reasoning graph you want to make tamper-evident and publicly
verifiable. You commit a single self-describing **anchor record** (Merkle root
+ entry count + timestamp + roster hash) to a blockchain. From that one record,
anyone can later verify the whole history: every signature, every hash-chain
link, and the Merkle root over all entries.

## Run it

```bash
cd /home/ubuntu/arxdb
conda activate arxdb
python examples/06-blockchain-anchor/anchor.py
```

## Expected output

```
[anchor] root_hash=1e20ec0c25ec44d2... entries=2 roster_hash=1e20d7df14f79f6e...
[verify]  correct root -> True
[verify]  forged root  -> False
```

## Walkthrough

### 1. Commit the roster as the genesis entry

```python
commit_roster(store, roster)
```

The roster is committed as log entry 0, so the Merkle root transitively
commits to the roster. Trusting the anchor's root means trusting the roster —
no separate "founder signs the roster" ceremony.

### 2. Commit reasoning

```python
verify_and_commit(store, pub, [a], b, "add 1", EdgeType.DEDUCTION)
```

Each commit appends a signed log entry and extends the Merkle tree.

### 3. Build the anchor

```python
rec = anchor(store, roster)
# rec.root_hash, rec.entry_count, rec.timestamp_ns, rec.roster_hash
```

`AnchorRecord` is the single self-describing record to put on a blockchain. It
carries everything an external party needs to verify the whole history.

### 4. Verify from only the root

```python
verify_history(store, rec.root_hash)   # True
verify_history(store, hash_bytes(b"a forged root"))  # False
```

`verify_history` walks seq 0..N and checks, for every entry: the signature
verifies, the `prev_log_hash` links to the previous entry, and the Merkle root
over all entry hashes equals the trusted root. Any tampering — altered payload,
broken link, forged signature — makes it return False.

## Handling scenarios

- **Publish the anchor** — write `rec.anchor_bytes()` (deterministic CBOR) to a
  blockchain transaction or a public timestamping service. The `anchor_hash()`
  is its content address.
- **Audit a third party's history** — give them only `rec.root_hash`; they run
  `verify_history` against their copy of the data. No shared secret, no trust.
- **Detect any tampering** — flip a single byte in the log (via raw SQL, as
  `tests/test_attest.py` does) and `verify_history` returns False.
- **Anchor periodically** — re-anchor after each batch of commits; each anchor
  is a checkpoint that pins the history up to that point.

## Key API

`commit_roster`, `anchor`, `AnchorRecord`, `verify_history`, `Roster`.
