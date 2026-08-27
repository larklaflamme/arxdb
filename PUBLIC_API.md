# ArxDB — Public HTTP API (v0.1)

The public interface to ArxDB: a plain JSON HTTP API over the two queries
(reachability, path discovery) plus the **reproduce-the-proof** story that is
the heart of the AI Trust & Audit product.

> **Status:** Phase 7 (productization). Single-threaded, localhost by default.
> No authentication in v0.1 — see [Limitations](#limitations).

---

## 1. What this API gives you

ArxDB is a *reasoning* graph: claims are nodes, and every edge is a verified
inference step ("B follows from A by rule R") carrying a proof obligation, a
κ-strength, and a cryptographic signature. The API lets an external party:

1. **Query** — ask "have we reasoned about this before?" (reachability) and
   "what would it take?" (path discovery).
2. **Reproduce** — take any edge, re-run its proof check, and confirm the
   recorded verdict and κ are honest.
3. **Attest** — confirm *who* signed an edge, that it is unaltered, and that
   its proof is bound and intact.
4. **Anchor** — obtain the single trust anchor (a Merkle root) and verify the
   entire history from it, trustlessly.

The one-line value proposition: **you can independently confirm that a
reasoning step actually holds, without trusting whoever recorded it.**

---

## 2. Starting the server

```bash
# from the repo root, with the arxdb conda env active
python scripts/arxdb_serve.py --root data --host 127.0.0.1 --port 8080
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--root` | `data` | data directory (keypair, roster, SQLite DB, objects) |
| `--host` | `127.0.0.1` | bind address |
| `--port` | `8080` | bind port |
| `--backend` | `sqlite` | `sqlite` (in-process) or `grpc` (Go daemon) |
| `--socket` | `/tmp/arxdb.sock` | gRPC socket (only for `--backend grpc`) |

On first run the server generates a keypair and a genesis roster (binding the
server's key to the agent name `arxdb-server`) under `--root`. Re-running with
the same `--root` reuses them, so edge content addresses are stable.

To serve the seeded phaser-thread corpus, seed first, then serve:

```bash
python scripts/seed_phaser.py --root data
python scripts/arxdb_serve.py --root data --port 8080
```

---

## 3. Endpoint reference

All responses are JSON. Errors are `{"error": "..."}` with an appropriate
status code (400 bad request, 404 not found, 500 internal).

### `GET /health`

Liveness. Returns `{"status": "ok", "version": "0.1.0"}`.

### `POST /query/reachable`

"Have we reasoned about this before?"

```json
{ "claim": "x + 1 > 0", "domain": "math", "polarity": true, "min_kappa": "K0" }
```

`min_kappa` is optional (default `K0`); it is the strength threshold — a claim
derived only below the threshold is reported `established: false`.

Response: `target`, `min_kappa`, `established` (bool), `kappa` (the strongest
derivation, or null), `depth` (minimum proof-tree depth), `proof_tree_edges`
(the edge hashes in the best derivation).

### `POST /query/path`

"What would it take to reason about this?" Same request shape. Response adds
`missing_edges` — the goal-specific frontier: the unestablished premises in
the target's dependency cone, each with its `conclusion`, `premises`,
`blocking_nodes`, and `rule`. A leaf (no incoming edge at all) is reported
with empty premises — the signal that it needs a definition/axiom.

### `GET /query/graph`

The whole reasoning graph — every node and every edge. The visualizer's data
source. No request body.

Response: `nodes` (each with `claim`, `domain`, `polarity`, `node_id`) and
`edges` (each with `type`, `premises`, `conclusion`, `rule`, `verdict`,
`kappa`, `edge_hash`).

### `POST /reproduce`

**The core story.** Re-verify a reasoning step independently.

```json
{ "edge_hash": "1e20bf7a..." }
```

Response: the full edge record, the resolved premises and conclusion (with
claim text), the rule, the proof (base64, or null), the `embedded` verdict/κ,
the `re_verified` verdict/κ, `verdict_match`, `kappa_match`, the `attestation`
block, and `reproduced` (true iff verdict and κ match *and* attestation holds).

### `POST /attest`

Provenance, integrity, binding for one edge.

```json
{ "edge_hash": "1e20bf7a..." }
```

Response: `signer_agent_id` (the named agent, or null), `signature_valid`,
`proof_bound`, `proof_intact`, `ok`.

### `GET /anchor`

The single trust anchor. Response: `root_hash` (Merkle root over the log),
`entry_count`, `timestamp_ns`, `roster_hash`. Commit this record to a
blockchain (or publish it) and anyone can verify the whole history from it.

### `POST /verify_history`

Trustless whole-history verification from a root.

```json
{ "root_hash": "1e2003fb..." }
```

Response: `{ "root_hash": "...", "valid": true }`. `valid` is true only if
every entry's signature verifies, the hash chain links, and the Merkle root
matches — no trust in the local DB.

### `POST /commit`

Author an edge (verify-then-commit).

```json
{
  "premises": [ { "claim": "x > 0", "domain": "math" } ],
  "conclusion": { "claim": "x + 1 > 0", "domain": "math" },
  "rule": "monotonicity of addition",
  "edge_type": "deduction",
  "proof": "<base64, optional>",
  "signer_pubkey": "<hex, optional>",
  "timeout_seconds": 5.0
}
```

`edge_type` is one of `definition`, `deduction`, `numerical`, `reduction`,
`refutation`, `analogy`, `citation`. `signer_pubkey` defaults to the server's
key; pass your own 32-byte Ed25519 public key (hex) to record *your* identity
as the proposer. Response: `rejected`, `verification` (verdict/κ), `edge`,
`edge_hash`.

---

## 4. The κ-strength scale

Every edge carries a discrete strength label, and reachability propagates it
as a max-min semiring (a chain is only as strong as its weakest step):

| κ | Meaning | Earned by |
|---|---------|-----------|
| `K0` | conjecture / heuristic | analogy, or a rejected edge |
| `K1` | cited / ELENCHUS-vetted | citation, reduction, refutation, unlisted definition |
| `K2` | numerically verified | CAS identity check |
| `K3` | formally verified | Z3 (or Lean, when a proof is supplied) |
| `K_INF` | axiomatic ground | a roster-curated axiom |

---

## 5. The AI Trust & Audit use case

The canonical scenario: an AI agent produces a chain of reasoning, and a
downstream party must be able to *audit* it — to confirm each step actually
holds, was signed by the agent that produced it, and has not been altered.

1. The agent proposes each step through `POST /commit` (with its own
   `signer_pubkey`). ArxDB verifies before storing; a step that fails is
   rejected, not recorded as "verified".
2. The auditor queries `POST /query/reachable` to see what is established, and
   `POST /query/path` to see what is missing.
3. For any step, the auditor calls `POST /reproduce` to re-run the proof check
   and `POST /attest` to confirm provenance/integrity/binding.
4. The auditor pins `GET /anchor` and can later call `POST /verify_history` to
   confirm nothing in the whole history was tampered with.

The guarantee is not "the AI is right" — it is **"the AI's reasoning is
reproducible, attributable, and tamper-evident."**

---

## 6. Limitations (v0.1, stated honestly)

- **Single-threaded.** The server is `HTTPServer`, not threaded. The storage
  layer's SQLite connection and the checkers' `SIGALRM` timeout are both
  main-thread-bound, so requests are served sequentially. Fine for an audit
  API; concurrency is future work.
- **No authentication.** Anyone who can reach the port can read and commit.
  Bind to `127.0.0.1` (the default) or put it behind a reverse proxy with auth.
- **No TLS.** Terminate TLS at a reverse proxy (nginx/caddy) in front of it.
- **Lean not installed.** A `deduction` with a `proof` blob dispatches to the
  Lean checker, which is not installed in the default setup — such an edge is
  rejected. Use Z3 (omit `proof`) for deductions, or install Lean (see
  `SETUP.md` §6).
- **O(N) log walk.** Attestation finds an edge's log entry by a linear scan.
  Fine for v0.1; an index is future work.

---

## 7. Document map

- `README.md` — the pitch.
- `DESIGN.md` — the architecture (three layers, two queries).
- `DEV_GUIDE.md` — how to build on ArxDB (including AI-agent integration).
- `SETUP.md` — the toolchain.
- `STORAGE_API.md` — the storage boundary (the Go swap contract).
- `examples/` — runnable use cases; `08-public-api` is this API end-to-end.
