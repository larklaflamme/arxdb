# Ontology bridges: connecting the RH corpus into a single component

Date: 2026-08-27
Task: connect the 23-node RH seed corpus into a single interconnected ontology.

## Before

23 nodes, 23 edges, **12 disconnected components**, 5 fully isolated nodes
(N1, N6, N8, N17, N21), zero cross-thread edges. Five separate chains plus
five orphans.

## What was added

### 3 hub nodes (synthesis claims)
- N24: "positivity is the missing structure" (unifies N9, N13, N16, N23)
- N25: "the primes are the spectrum (input)" (unifies N1, N10, N21)
- N26: "the critical line is a balance point" (unifies N12, N20, N21)

### 22 cross-thread / hub edges (E24-E45)
- 2 CITATION (K1): N2->N17, N2->N18 (S(T) formula -> Selberg CLT / Omega-theorem)
- 20 ANALOGY (K0): the cross-thread bridges and hub connections

## After

- **26 nodes, 45 edges**
- **1 connected component** (was 12)
- Honest kappa: **K1 = 18, K0 = 27** (no K3, no inflation)

## Verification

- corpus.py imports clean, all premise/conclusion references valid
- test_seed.py: 12/12 pass (counts updated to 26/45)
- test_seed_grpc.py: 2/2 pass (45 edges over gRPC, kappa 18/27)
- full suite: 227 passed, 4 failed (4 pre-existing Lean-toolchain failures, untouched)
- live gRPC seed: 45 edges all MATCH, all resolve to "Skye", entry_count=46
- live /query/graph: 26 nodes, 45 edges, kappa K1:18 / K0:27
- Query B (path to RH at K1) still reports reachable=False, N9 still the frontier

## The one extra edge beyond the original 11-edge proposal

E45 (N5 -> N9): the Berry-Keating negative result (N4/N5) was the last
disconnected component. It connects to the main graph via N9 (the
Hilbert-Polya operator): the failure of the naive operator is what makes the
correct operator a genuine open problem. This is what took the graph from 2
components to 1.
