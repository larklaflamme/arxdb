# 🧠 ArxDB

> **A reasoning graph database.** Claims as nodes. Verified inference steps as edges. Proofs embedded, cryptographically signed, tamper-evident.

[![Status](https://img.shields.io/badge/status-prototype-yellow)](https://github.com)
[![Language](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
[![Storage](https://img.shields.io/badge/storage-Go%20(planned)-00ADD8.svg)](https://go.dev)
[![License](https://img.shields.io/badge/license-TBD-lightgrey.svg)]()

---

## ✨ What is ArxDB?

A **knowledge graph** stores *asserted* facts — "A —is-a→ B." The edge is a recorded relation, true or false on its own.

A **reasoning graph** stores *derived* claims. An edge "A → B" means:

> **B follows from A by rule R.**

Every edge carries a **proof obligation** — a claim that can be checked, refuted, or found to be a non-sequitur. Edges are *procedural*: they tell you *how* to reach a node, and whether that move is valid.

ArxDB is the second kind. It doesn't just remember what we know — it remembers **how we know it, and whether the reasoning holds.**

---

## 🎯 The Two Queries

| Query | Question | What it gives you |
|-------|----------|-------------------|
| 🔍 **Reachability** | *"Have we reasoned about this before?"* | Is there a verified path to this claim from what we already know? |
| 🧭 **Path discovery** | *"What would it take to reason about this?"* | How many verified hops from known claims to the target — and **which edges are missing**? |

The hop count is a **lower bound** on difficulty, never a prediction. It tells you the *minimum* reasoning work, not the actual difficulty.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│  Query Layer (reachability, path discovery)     │
├─────────────────────────────────────────────────┤
│  Verification Layer (Python — the moat)         │
│  ELENCHUS predicates · κ-tiering · proof checks │
│  sympy · mpmath · z3 · Lean bindings            │
├─────────────────────────────────────────────────┤
│  Storage Layer (Go — the engine)                │
│  content-addressed Merkle-DAG · signed log      │
│  graph traversal · concurrency                  │
└─────────────────────────────────────────────────┘
```

**The boundary is the storage API.** The verification layer stays Python forever — that's where the formal tools live. The storage layer is swappable (Python prototype → Go) behind a clean interface.

---

## 🔐 The Attestation Layer

The proof is a **first-class object embedded in the edge**, and the signature binds the proof to the edge. This gives you three guarantees:

1. **Access** — the proof is *there*, in the edge, not a pointer to somewhere else.
2. **Integrity** — the signature guarantees the proof hasn't been mangled.
3. **Provenance** — you know *who* verified it, and *when*.

The substrate is a **blockchain-anchorable signed Merkle-DAG**. Commit the root hash to a chain, and the entire history becomes trustlessly verifiable — no rebuild required.

---

## 🚀 Why it matters

- **🤖 AI Trust & Audit** — every reasoning step carries a reproducible cryptographic proof. Trust becomes *checkable*, not *claimed*.
- **🔬 Research provenance** — a proof verified once is verified *forever*. Every new contributor inherits every prior proof for free. The longer the graph, the more verified knowledge compounds.
- **🧮 Frontier visibility** — for hard open problems (like the Riemann Hypothesis), the graph shows you *exactly* which edges are missing between what you know and what you're trying to prove.

---

## 🧪 Quickstart

```bash
# (prototype — coming soon)
conda activate arxdb
python -m arxdb
```

---

## 📚 Documentation

| File | What it covers |
|------|----------------|
| [`DESIGN.md`](DESIGN.md) | Core concept, layers, tech mappings, MVP scope |
| [`DECISIONS.md`](DECISIONS.md) | Architecture decision records (ADRs) |
| [`STORAGE_API.md`](STORAGE_API.md) | The interface that makes the Python→Go swap a drop-in |

---

## 🧭 Status

**Prototype.** The design is settled; the Python storage layer and edge schema are next. The Go storage engine follows once the interface is proven.

---

*Built by Skye Laflamme & Lark — a reasoning graph for a world that needs to know not just what it thinks, but whether it's right.*
