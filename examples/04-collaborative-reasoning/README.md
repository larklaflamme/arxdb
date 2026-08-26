# 04 — Collaborative reasoning

Multiple named agents build on a shared reasoning graph, each signing their own
edges. Provenance resolves each edge to its *author*, not an anonymous key.

## The scenario

Three researchers — Alice, Bob, and Carol — collaborate on a shared reasoning
graph:

- **Alice** proposes an assumption.
- **Bob** builds a deduction on Alice's assumption.
- **Carol** cites an external result.

Each edge records who proposed it (`signer_pubkey`), and the roster resolves
that key to a name. Anyone can later ask "who claimed this, and is their
signature valid?"

## Run it

```bash
cd /home/ubuntu/arxdb
conda activate arxdb
python examples/04-collaborative-reasoning/collaborative.py
```

## Expected output

```
[alice] signer=alice ok=True
[bob] signer=bob ok=True
[carol] signer=carol ok=True
```

## Walkthrough

### Three keypairs, one roster

```python
alice_priv, alice_pub = generate_keypair()
bob_priv, bob_pub = generate_keypair()
carol_priv, carol_pub = generate_keypair()
roster = Roster(entries={"alice": alice_pub, "bob": bob_pub, "carol": carol_pub})
```

### A shared store

```python
store = Storage(Path(tmp), alice_priv, alice_pub)
```

One subtlety worth naming: the store's own keypair (Alice's, here) signs the
**append log** — the tamper-evident history. Each edge *separately* records who
proposed it via `signer_pubkey`. So the log is signed by one maintainer, while
edges are attributed to their individual authors.

### Each agent signs their own edge

```python
r_a = verify_and_commit(store, alice_pub, [], a, "assume", EdgeType.DEFINITION)
r_b = verify_and_commit(store, bob_pub, [a], b, "add 1", EdgeType.DEDUCTION)
r_c = verify_and_commit(store, carol_pub, [], c, "cite", EdgeType.CITATION)
```

The `signer_pubkey` argument is the *proposer's* key, embedded in the edge and
covered by its content address.

### Provenance

```python
att = verify_edge_attestation(r.edge, store, roster)
# att.signer_agent_id -> "alice" / "bob" / "carol"
```

## Handling scenarios

- **Key rotation** — append a new binding to the roster (`Roster` is
  insertion-ordered; `resolve` returns the latest, `identify` still attributes
  historical edges to the agent).
- **An unknown signer** — commit an edge with a key not in the roster:
  `signer_agent_id` is None, so provenance fails and `ok` is False.
- **Per-agent stores** — for a fully decentralized setup, give each agent their
  own `Storage` (own log, own keypair) and merge via a shared anchor (see
  example 06). The shared-store form here is the simplest collaborative model.
- **Attribution disputes** — combine with example 05: a refutation edge can
  attack another agent's edge, and the grounded extension decides who is IN.

## Key API

`generate_keypair`, `Roster`, `verify_and_commit` (with per-agent
`signer_pubkey`), `verify_edge_attestation`.
