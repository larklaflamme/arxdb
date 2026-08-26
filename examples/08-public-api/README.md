# 08 — The public API (reproduce the proof)

The Phase 7 example: **ArxDB as a service**. It shows an external user driving
the whole product over plain HTTP — authoring edges, querying reachability,
and — the heart of the AI Trust & Audit story — *independently re-verifying a
reasoning step and confirming its attestation*, with nothing but stdlib HTTP.

## What this demonstrates

| Step | Endpoint | What it proves |
|------|----------|----------------|
| Health | `GET /health` | the server is up |
| Author a definition | `POST /commit` | a zero-premise edge grounds a claim |
| Author a deduction | `POST /commit` | Z3 verifies `x > 0 ⇒ x + 1 > 0` at κ3 |
| Author a citation | `POST /commit` | a proof blob is bound to the edge (`proof_hash`) |
| Query | `POST /query/reachable` | "have we reasoned about this before?" |
| Query | `POST /query/path` | "what would it take?" |
| **Reproduce** | `POST /reproduce` | re-run the checker, confirm verdict + κ + attestation |
| Attest | `POST /attest` | provenance, integrity, binding |
| Anchor | `GET /anchor` | the single trust anchor (root hash) |
| Verify history | `POST /verify_history` | trustless whole-history check from the root |

## Run it

From the repo root, with the `arxdb` conda environment active:

```bash
python examples/08-public-api/client.py
```

The script starts its own server on a throwaway data directory and a fixed
port (`127.0.0.1:8098`), so it is fully self-contained — no manual server
setup needed. It prints each request/response pair as it goes.

## The reproduce-the-proof story, explained

This is the one thing that makes ArxDB a *reasoning* graph rather than a
knowledge graph, and it is the whole point of Phase 7. Here is what
`POST /reproduce` actually does, step by step:

1. **Resolve the edge** — the client sends an `edge_hash`; the server decodes
   the edge record (premises, conclusion, rule, type, `proof_hash`, embedded
   verdict + κ).
2. **Resolve the claims** — each premise hash and the conclusion hash are
   decoded back to their human-readable claim text (the node payloads were
   persisted at commit time).
3. **Retrieve the proof** — the proof blob is fetched by its content address
   (`proof_hash`), so the client can see *exactly* what was verified.
4. **Re-run the checker** — the server runs the *same* verification pipeline
   (`verify`) on the resolved premises/conclusion/rule/proof.
5. **Compare** — the re-run verdict and κ are compared to the values embedded
   in the edge. A mismatch means the edge's recorded strength is not
   reproducible.
6. **Attest** — provenance (who signed it), integrity (signature valid),
   binding (proof intact) are all checked.

The response's `reproduced` field is `true` only when the re-run verdict and κ
match the embedded values *and* the attestation holds. That is the guarantee:
**an external party can confirm, without trusting us, that a reasoning step
actually holds.**

## The κ propagation you'll see

The deduction earns κ3 (Z3 verified it), but the conclusion `x + 1 > 0` is
reported as **established at κ1**, not κ3. That is correct, not a bug: the
conclusion's strength is the *weakest link* of its derivation — `min(κ1, κ3)`
— because its premise `x > 0` was only grounded as an unlisted definition
(κ1), not a roster axiom (κ∞). This is the max-min semiring propagation doing
exactly what it is designed to do: a chain is only as strong as its weakest
step.

## Adapting it

- **Point it at a real server** — replace the subprocess bootstrap with a
  running server: `python scripts/arxdb_serve.py --root data --port 8080`,
  then set `BASE` to `http://127.0.0.1:8080`.
- **Use the seeded corpus** — run `python scripts/seed_phaser.py --root data`
  first, then query the phaser-thread claims (e.g. the RH conjecture) over the
  API instead of the toy arithmetic here.
- **Go backend** — start the daemon (`go run ./cmd/arxdbd`), then serve with
  `--backend grpc --socket /tmp/arxdb.sock`; the API surface is identical.
