# 03 — AI audit

Verify an AI's reasoning chain, then detect tampering. This is the "AI trust &
audit" use case: an AI produces reasoning, and an auditor can independently
reproduce and verify every step.

## The scenario

An AI assistant produces a multi-step reasoning chain. Each step is committed
as a signed edge with its **proof** (the reasoning trace) bound to it. An
auditor then verifies the three guarantees of the attestation layer:

1. **provenance** — who signed it (a *named* agent via the roster),
2. **integrity** — has it been altered (signature + hash chain),
3. **binding** — is the proof bound to this edge and intact.

Then we tamper with a proof blob and show the audit catches it.

## Run it

```bash
cd /home/ubuntu/arxdb
conda activate arxdb
python examples/03-ai-audit/audit.py
```

## Expected output

```
[step 1] signer=assistant-model signature_valid=True proof_bound=True proof_intact=True ok=True
[step 2] signer=assistant-model signature_valid=True proof_bound=True proof_intact=True ok=True
[tampered] proof_intact=False ok=False
```

## Walkthrough

### The AI's keypair and the roster

```python
ai_priv, ai_pub = generate_keypair()
roster = Roster(entries={"assistant-model": ai_pub})
```

The roster binds a public key to a *name*. Provenance is a named attribution,
not an anonymous 32-byte blob.

### Committing steps with proofs

```python
r1 = verify_and_commit(store, ai_pub, [a], b, "add 1", EdgeType.CITATION, proof_bytes=proof1)
```

Each step carries a `proof_bytes` blob (the model's reasoning trace). The edge
stores `proof_hash = hash(proof_bytes)`, binding the proof to this specific
edge. (We use `CITATION` here so the proof blob is stored without needing the
Lean checker; a `DEDUCTION` with `proof_bytes` dispatches to Lean — see
"Handling scenarios".)

### Auditing

```python
att = verify_edge_attestation(r.edge, store, roster)
```

Returns `signer_agent_id`, `signature_valid`, `proof_bound`, `proof_intact`,
and the combined `ok`. All three guarantees must hold for `ok=True`.

### Detecting tampering

```python
proof_path = store.objects._path(r1.edge.proof_hash)
proof_path.write_bytes(b"tampered proof")
att = verify_edge_attestation(r1.edge, store, roster)  # proof_intact=False
```

The object store is content-addressed: the file lives at the path derived from
its hash. Overwriting it with different bytes breaks the binding — the stored
bytes no longer hash to `proof_hash`, so `proof_intact` flips to False.

## Handling scenarios

- **Machine-checked steps** — use `EdgeType.DEDUCTION` *without* `proof_bytes`
  to run Z3 (κ3). With `proof_bytes`, the DEDUCTION dispatches to Lean, which
  requires the Lean toolchain (see `SETUP.md` §6).
- **Detect a forged signature** — commit an edge with a *different* signer's
  key not in the roster: `signer_agent_id` is None and `ok` is False.
- **Detect a broken hash chain** — `verify_history(store, trusted_root)` walks
  the whole log and returns False on any altered payload, broken link, or
  forged signature (see example 06).
- **Audit a whole model's output** — commit every step of a long chain, then
  run `verify_edge_attestation` over all of them in a loop; any single
  tampered step is caught.

## Key API

`Roster`, `verify_and_commit` (with `proof_bytes`), `verify_edge_attestation`,
`AttestationResult`.
