# ArxDB Examples

Runnable, end-to-end examples showing how to use ArxDB in real life. Each
example is a self-contained Python script plus an extensive README that walks
through the scenario, the code, the expected output, and how to adapt it.

ArxDB is a **reasoning graph** — a knowledge graph where the edges are not
"related to" but *"B follows from A by rule R"*. Every edge carries a proof
obligation, is cryptographically signed, and is content-addressed. The result
is a substrate where reasoning can be **verified, audited, refuted, and
anchored** — not just stored.

## The examples

| # | Example | What it demonstrates |
|---|---------|---------------------|
| 01 | [Hello, reasoning](01-hello-reasoning/README.md) | The minimal end-to-end pipeline: keypair → storage → verify-and-commit → query → resolve |
| 02 | [Research provenance](02-research-provenance/README.md) | The κ-strength scale (κ∞ → κ0) maps onto real research artifacts; path discovery names the "wall" |
| 03 | [AI audit](03-ai-audit/README.md) | Verify an AI's reasoning chain (provenance + integrity + binding), then detect tampering |
| 04 | [Collaborative reasoning](04-collaborative-reasoning/README.md) | Multiple named agents, each signing their own edges; provenance resolves to a name |
| 05 | [Refutation](05-refutation/README.md) | Attack and defend edges; the grounded active subgraph (Dung's extension) |
| 06 | [Blockchain anchor](06-blockchain-anchor/README.md) | Commit a trust anchor; verify the whole history from only the root |
| 07 | [Go gRPC backend](07-go-grpc-backend/README.md) | The drop-in swap: same facade, Go/Pebble engine over gRPC |

## Running the examples

All examples run from the repo root with the `arxdb` conda environment active:

```bash
cd /home/ubuntu/arxdb
conda activate arxdb
python examples/01-hello-reasoning/hello.py
```

Example 07 additionally needs the Go toolchain (see `SETUP.md` §3) and builds
the `arxdbd` daemon on first run.

## The core concepts, in one breath

- **Node** — an immutable claim (proposition + domain + polarity). Content-addressed.
- **Edge** — a typed inference step: `premises → conclusion` by `rule`, carrying
  its verdict, κ-strength, and a content-addressed `proof_hash`.
- **κ (kappa)** — a discrete strength label, `K0 < K1 < K2 < K3 < K_INF`:
  analogy (κ0), citation (κ1), CAS-verified identity (κ2), machine-checked
  deduction (κ3), axiomatic ground (κ∞).
- **verify_and_commit** — propose an edge → verify → reject-or-store, atomically.
- **Reachability** — "have we reasoned about this before?" (AND-OR hyperpath
  traversal with κ-propagation).
- **Path discovery** — "what would it take?" (the goal-specific missing frontier).
- **Attestation** — provenance (who), integrity (unaltered), binding (proof
  bound to edge).
- **Anchor** — a single self-describing record to commit to a blockchain.

See `DESIGN.md` for the full architecture and `STORAGE_API.md` for the storage
contract.
