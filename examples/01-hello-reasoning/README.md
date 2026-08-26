# 01 — Hello, reasoning

The minimal end-to-end ArxDB program. If you read one example, read this one:
it exercises the whole pipeline in ~40 lines.

## The scenario

You want to record a small piece of reasoning and then ask a question about it.
Specifically:

1. You assert an **axiom** ("for all x, x = x").
2. You make a **deduction** ("x > 0" implies "x + 1 > 0").
3. You record a **citation** ("the Riemann hypothesis is unproven").
4. You **query** whether the axiom is established, and at what strength.
5. You **resolve** a content address back to its human-readable claim.

## Run it

```bash
cd /home/ubuntu/arxdb
conda activate arxdb
python examples/01-hello-reasoning/hello.py
```

## Expected output

```
[axiom]     verdict=PASS       kappa=K_INF
[deduction] verdict=PASS       kappa=K3
[citation]  verdict=PASS       kappa=K1
[reachable] axiom established=True kappa=K_INF depth=0
[resolve]   'for all x, x = x' (domain=math)
```

## Walkthrough

### 1. A keypair

```python
priv, pub = generate_keypair()
```

Every agent holds an Ed25519 keypair. The private key signs the append log;
the public key is embedded in every edge as "who proposed this".

### 2. Storage

```python
store = Storage(Path(tmp), priv, pub)
```

`Storage` is the unified facade: ObjectStore + GraphIndex + AppendLog. It is
backed by SQLite in-process (see example 07 for the Go/gRPC backend).

### 3. Verify-and-commit

```python
r_axiom = verify_and_commit(store, pub, [], axiom, "reflexivity", EdgeType.DEFINITION)
```

`verify_and_commit` runs the κ-tiering pipeline (ELENCHUS sanity filter, then a
type-appropriate checker) and either stores the edge or rejects it. The axiom
earns **κ∞** because "for all x, x = x" is in the curated roster of accepted
system ground.

The deduction earns **κ3** because it is machine-checked by Z3 (no proof blob
means Z3 runs; a proof blob would dispatch to Lean instead). The citation earns
**κ1** — taken on authority, no checker.

### 4. Query

```python
q = reachable(axiom.node_id(), store)
```

`reachable` answers "have we reasoned about this before?" via AND-OR hyperpath
traversal with κ-propagation. The axiom is established at κ∞, depth 0 (it is a
zero-premise definition).

### 5. Resolve

```python
node = resolve_node(axiom.node_id(), store)
```

Turns a content address back into the human-readable `Node` record.

## Handling scenarios

- **Reject an edge** — propose a deduction whose conclusion introduces a novel
  concept (e.g. premise "x > 0", conclusion "y > 0"): ELENCHUS fires a
  `non_sequitur` HARD_VETO and nothing is stored (`result.rejected` is True).
- **Use a different backend** — swap `Storage(...)` for
  `create_storage(..., backend="grpc", socket_path=...)` (see example 07).
- **Persist instead of a temp dir** — pass a real `Path` instead of
  `TemporaryDirectory()`; the store survives across processes.

## Key API

`generate_keypair`, `Storage`, `verify_and_commit`, `reachable`, `resolve_node`,
`Node`, `EdgeType`.
