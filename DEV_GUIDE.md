# ArxDB — Developer Guide

> **What ArxDB is, how to set it up, and how to integrate it with AI agents.**

This is the developer-facing companion to `README.md` (the pitch) and
`DESIGN.md` (the architecture). It assumes you want to *build on* ArxDB, not
just understand it. It is written against the **actual code** — every function
signature, enum value, and file path below exists on disk and is exercised by
the test suite and the `examples/` directory.

---

## 1. What ArxDB is

ArxDB is a **reasoning graph database**. It is not a knowledge graph.

| | Knowledge graph | ArxDB (reasoning graph) |
|---|---|---|
| Edge means | "A is related to B" | "**B follows from A by rule R**" |
| Edge is | a recorded fact | a *procedural claim* with a proof obligation |
| Question it answers | "what do we know?" | "**how do we know it, and does the reasoning hold?**" |

Every edge carries:

- **premises** — the source claims (possibly several; inference is a hyper-edge)
- **conclusion** — the target claim
- **rule** — the inference rule / method used
- **proof** — a first-class object, embedded and content-addressed
- **verdict** — the ELENCHUS + checker outcome (`PASS` / `SOFT_FLAG` / `HARD_VETO`)
- **κ (kappa)** — a discrete strength label
- **signature** — an Ed25519 signature binding the proof to the edge

The result is a substrate where reasoning can be **verified, audited, refuted,
and anchored** — not merely stored.

### The two queries (the product)

1. **Reachability** — *"have we reasoned about this before?"* Is there a
   verified derivation of a claim from what we already know, and at what κ?

2. **Path discovery** — *"what would it take to reason about this?"* How many
   verified hops from known claims to the target, and **which edges are
   missing**?

The hop count is a *lower bound* on difficulty, never a prediction.

---

## 2. Architecture

```
┌─────────────────────────────────────────────┐
│  Query Layer (reachability, path discovery) │
├─────────────────────────────────────────────┤
│  Verification Layer (Python — the moat)     │
│  ELENCHUS predicates · κ-tiering · proofs   │
│  sympy · mpmath · z3 · Lean bindings        │
├─────────────────────────────────────────────┤
│  Storage Layer (Go — the engine)            │
│  content-addressed Merkle-DAG · signed log  │
│  graph traversal · concurrency              │
└─────────────────────────────────────────────┘
```

**The boundary is the storage API.** The verification layer stays Python
forever — that's where the formal tools live. The storage layer is swappable
(Python prototype → Go) behind a clean interface (`STORAGE_API.md`).

### The two storage backends

| Backend | Engine | Process | When to use |
|---------|--------|---------|-------------|
| `sqlite` | Python (Phase 1) | in-process | prototyping, tests, single-agent |
| `grpc` | Go + Pebble (Phase 6) | separate `arxdbd` daemon | production, multi-agent, concurrency |

The drop-in claim is real: the same `Storage` facade is presented by both, and
the only thing that changes is the `backend=` argument to `create_storage`.

---

## 3. Setup

Full toolchain setup (Go, gRPC, Python env, environment variables) is in
[`SETUP.md`](SETUP.md). The short version:

```bash
cd /home/ubuntu/arxdb
conda activate arxdb
pip install -e .            # installs the arxdb package in editable mode
```

Verify the install:

```bash
python -c "import arxdb; print(arxdb.__file__)"
pytest -q                   # 211 passed, 4 failed (Lean not installed)
```

The 4 failing tests are Lean-dependent (Lean 4 is not installed — see
`SETUP.md` §6). Everything else is green.

---

## 4. Core concepts

### Node — an immutable claim

```python
from arxdb.verification.schema import Node

n = Node(claim="the zeros of ζ_N(s) drift to Re=1", domain="math", polarity=True)
node_id = n.node_id()   # content address (BLAKE3 multihash)
```

A `Node` is a proposition + domain + polarity. **Truth is not a field** — it is
a graph-derived property (computed by reachability), not static state. If truth
were embedded in the content address, proving a claim would change its hash and
break every edge referencing it.

### Edge — a typed inference step

```python
from arxdb.verification.schema import Edge, EdgeType, Kappa, Verdict
```

The 7-way edge taxonomy (`EdgeType`):

| Type | Meaning | Default κ |
|------|---------|-----------|
| `DEFINITION` | a definition / axiom (zero-premise) | K_INF |
| `DEDUCTION` | machine-checked logical step | K3 |
| `NUMERICAL` | CAS-verified computation | K2 |
| `REDUCTION` | problem reduction | K2 |
| `REFUTATION` | attacks another edge (defeasibility) | — |
| `ANALOGY` | heuristic transfer | K0 |
| `CITATION` | sourced claim | K1 |

### κ (kappa) — the strength scale

```
K0 < K1 < K2 < K3 < K_INF
```

- **K0** — analogy (heuristic)
- **K1** — citation (sourced)
- **K2** — CAS-verified identity / numerical
- **K3** — machine-checked deduction
- **K_INF** — axiomatic ground (earned only via the curated roster)

The propagation algebra (`kappa.py`) is pure and total:

```python
from arxdb.verification.kappa import series, parallel, corroborate

series(K3, K1)        # K1  — a chain is as strong as its weakest link
parallel(K_INF, K1)   # K1  — axiom absorption: min(K_INF, x) = x
corroborate(K1, K3)   # K3  — independent derivations corroborate (max)
```

### Verdict — the reject/store signal

`PASS` (store), `SOFT_FLAG` (store with a warning), `HARD_VETO` (reject — nothing
is written).

---

## 5. The API surface

### 5.1 Storage (`arxdb.storage`)

```python
from arxdb.storage.factory import create_storage
from arxdb.storage.keys import generate_keypair

priv, pub = generate_keypair()          # 32-byte seed + 32-byte pubkey

# In-process SQLite
store = create_storage(root, priv, pub, backend="sqlite")

# Go daemon over gRPC (Phase 6)
store = create_storage(root, priv, pub, backend="grpc", socket_path="/tmp/arxdb.sock")
```

The `Storage` facade composes three sub-interfaces (see `STORAGE_API.md` for the
full contract):

- **`store.objects`** — content-addressed put/get/has (immutable blobs)
- **`store.graph`** — structural adjacency (incoming/outgoing edges, connectivity)
- **`store.log`** — signed append-only log + Merkle tree (provenance)

The key atomic operation:

```python
edge_hash, log_entry = store.commit_edge_tx(premises, conclusion, edge_data, proof)
```

### 5.2 Verification (`arxdb.verification`)

The verify-then-commit facade is the single entry point for proposing an edge:

```python
from arxdb.verification.commit import verify_and_commit
from arxdb.verification.schema import EdgeType

result = verify_and_commit(
    storage=store,
    signer_pubkey=pub,
    premises=[premise_node],
    conclusion=conclusion_node,
    rule="modus ponens",
    edge_type=EdgeType.DEDUCTION,
    proof_bytes=proof_blob,          # optional
    timeout_seconds=5.0,
)

if result.rejected:
    # HARD_VETO — nothing was stored
    print(result.verification.verdict)
else:
    edge = result.edge              # the built, signed Edge
    edge_hash = result.edge_hash    # its content address
```

The lower-level `verify(...)` runs just the κ-tiering pipeline without storing:

```python
from arxdb.verification.verifier import verify

v = verify(premises, conclusion, rule, edge_type, proof_bytes)
# v.verdict, v.kappa, v.elenchus, v.checker
```

**Important gotcha:** a `DEDUCTION` edge with `proof_bytes` dispatches to the
**Lean checker**, which is not installed → `HARD_VETO`. To demonstrate proof
binding without Lean, use `CITATION` + `proof_bytes` (see example 03).

### 5.3 Query (`arxdb.query`)

```python
from arxdb.query.reachability import reachable
from arxdb.query.path import path_discovery
from arxdb.query.resolve import resolve_node, resolve_edge
from arxdb.query.refutation import compute_active_subgraph

r = reachable(target_hash, store, min_kappa=Kappa.K1)
# r.established, r.kappa, r.depth, r.proof_tree_edges

p = path_discovery(target_hash, store, min_kappa=Kappa.K2)
# p.reachable, p.missing (the blocking frontier)

node = resolve_node(hash, store)   # decode a claim from its content address
edge = resolve_edge(hash, store)   # decode an edge from its content address

sub = compute_active_subgraph(store)   # Dung-style grounded extension
# sub.active_edges (the IN set), sub.refuted
```

### 5.4 Attestation (`arxdb.attestation`)

```python
from arxdb.attestation.attest import (
    verify_edge_attestation, verify_history, anchor, commit_roster,
)
from arxdb.attestation.roster import Roster

roster = Roster({pub: "Skye"})          # bind a pubkey to a name
commit_roster(store, roster)            # roster becomes log entry 0

att = verify_edge_attestation(edge, store, roster)
# att.signer_agent_id, att.signature_valid, att.proof_bound, att.proof_intact

ok = verify_history(store, trusted_root)   # verify the whole log from only the root
record = anchor(store, roster)            # self-describing record to commit to a chain
```

---

## 6. Integrating with AI agents

This is the section that matters most for the stated purpose of ArxDB. The
integration model is: **the agent proposes edges; ArxDB verifies, stores, and
attests them.** The agent never writes directly to storage — it goes through
`verify_and_commit`, so every step is checked before it lands.

### 6.1 The canonical loop

```python
from arxdb.storage.factory import create_storage
from arxdb.storage.keys import generate_keypair
from arxdb.verification.commit import verify_and_commit
from arxdb.verification.schema import Node, EdgeType

priv, pub = generate_keypair()
store = create_storage(root, priv, pub, backend="sqlite")

def agent_step(premises, conclusion, rule, edge_type, proof=None):
    """One reasoning step by the agent, verified and committed."""
    result = verify_and_commit(
        storage=store,
        signer_pubkey=pub,
        premises=premises,
        conclusion=conclusion,
        rule=rule,
        edge_type=edge_type,
        proof_bytes=proof,
    )
    if result.rejected:
        return None, result.verification.verdict
    return result.edge_hash, result.edge.kappa
```

The agent's job is to *produce* `(premises, conclusion, rule, edge_type, proof)`.
ArxDB's job is to *judge* it. The agent can be wrong; the graph records whether
it was.

### 6.2 What the agent supplies, and what it gets back

| Agent supplies | ArxDB returns |
|----------------|---------------|
| premises (claims) | verdict (PASS / SOFT_FLAG / HARD_VETO) |
| conclusion (claim) | κ-strength earned |
| rule (method) | the signed `Edge` + its content address |
| edge_type | the log entry (provenance) |
| proof (optional) | — |

### 6.3 Multi-agent collaboration

Each agent holds its own keypair and signs its own edges. The **roster** maps
pubkeys to names, so provenance resolves to a *named agent*, not an anonymous
32-byte key:

```python
roster = Roster({alice_pub: "alice", bob_pub: "bob", carol_pub: "carol"})
```

The store's keypair signs the *log* (the shared history); each edge separately
records its *proposer* via `signer_pubkey`. These are two different things and
should not be conflated (see example 04).

### 6.4 Auditing an agent's reasoning

To audit a chain of reasoning, walk the edges and call
`verify_edge_attestation` on each. Three guarantees per edge:

1. **Provenance** — `signer_pubkey` resolves to a named agent.
2. **Integrity** — the log signature verifies (the edge wasn't mangled).
3. **Binding** — `proof_hash` resolves to a retrievable blob whose hash matches.

Tampering with any edge (or its proof) flips `proof_intact` / `signature_valid`
to `False` (see example 03).

### 6.5 Anchoring for trustless verification

Commit the `anchor()` record's `root_hash` to a blockchain, and the *entire*
history becomes trustlessly verifiable via `verify_history(store, trusted_root)`
— no rebuild, no trust in the local DB (see example 06).

### 6.6 The gRPC backend for production agents

For a production deployment, run the Go daemon and point agents at it:

```bash
go build -o arxdbd ./go/cmd/arxdbd
./arxdbd -socket /tmp/arxdb.sock -data /path/to/data
```

```python
store = create_storage(root, priv, pub, backend="grpc", socket_path="/tmp/arxdb.sock")
```

The agent code is **identical** — only the `backend=` argument changes. The
daemon owns the storage engine and keypair; `root`/`priv`/`pub` are ignored for
the gRPC backend (see example 07).

---

## 7. The examples

Seven runnable, end-to-end examples live in `examples/`, each with an extensive
README. They are the best way to learn the API by doing:

| # | Example | Demonstrates |
|---|---------|--------------|
| 01 | Hello, reasoning | minimal pipeline: keypair → storage → commit → query → resolve |
| 02 | Research provenance | κ-scale maps onto research artifacts; path discovery names the "wall" |
| 03 | AI audit | verify a reasoning chain, detect tampering |
| 04 | Collaborative reasoning | multiple named agents, provenance resolves to a name |
| 05 | Refutation | attack/defend edges; the grounded active subgraph |
| 06 | Blockchain anchor | trust anchor + verify whole history from only the root |
| 07 | Go gRPC backend | the drop-in swap (Go/Pebble over gRPC) |

Run one:

```bash
cd /home/ubuntu/arxdb
conda activate arxdb
python examples/01-hello-reasoning/hello.py
```

---

## 8. Document map

| File | Purpose |
|------|---------|
| `README.md` | the pitch — what and why |
| `DESIGN.md` | the architecture — layers, tech mappings, MVP scope |
| `DEV_GUIDE.md` | **this file** — how to build on it, integrate agents |
| `SETUP.md` | toolchain setup (Go, gRPC, Python, env vars) |
| `STORAGE_API.md` | the storage contract (the Python↔Go boundary) |
| `PUBLIC_API.md` | the public HTTP API (Phase 7) |
| `ROADMAP.md` | execution phases |
| `examples/` | runnable, documented use cases |

---

*Built by Skye Laflamme & Lark — a reasoning graph for a world that needs to
know not just what it thinks, but whether it's right.*
