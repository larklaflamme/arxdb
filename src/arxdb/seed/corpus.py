"""corpus.py — the phaser-thread seed corpus (declarative data).

Phase 4's first deliverable: our own RH reasoning, imported as nodes and
edges, to prove the tool on real material instead of toy axioms.

This module is *data*, not code. It contains no `verify_and_commit` calls, no
storage, no I/O — just frozen dataclasses enumerating the claims (nodes) and
the inference steps (edges) with their declared edge type, expected κ, and
source. The only imperative part of Phase 4 is `scripts/seed_phaser.py`,
which ingests this data through the public pipeline.

The corpus is deliberately small (9 nodes, 9 edges): the point is correctness
of *classification*, not volume. It is drawn from the phaser-thread stocktake
(`data/experiments/2026-08-25/phaser-thread-stocktake/STOCKTAKE.md`).

### The central finding this corpus is designed to surface

Our RH material is a map of a *wall*, not a pile of proven theorems. Almost
none of it is Z3/Lean-checkable — analytic number theory is not first-order
arithmetic. So the honest κ for nearly every edge is κ1 (citation), with one
κ0 conjecture (RH itself) and zero κ3 deductions. The tool must report this
truthfully rather than inflate it.

### v0.3 addition (N9/E9, Option B)

To make Query B actually "name the wall", the corpus gains N9 (the
Hilbert-Polya operator claim) and E9 (`N9 -> N7`, CITATION, kappa1). N9 is a
leaf (no incoming edge), so `path_discovery(N7, min_kappa=K1)` reports
`reachable=False` with N9 in the goal-specific frontier -- the tool names the
exact object we have been chasing.

### v0.2 correction (E6)

The plan's v0.1 tagged E6 (Platt 2019, "10¹³ zeros on the line") as NUMERICAL
→ κ2. That was wrong: the CasChecker only verifies *symbolic identities*
("lhs = rhs" parseable by sympy), and "the first 10¹³ zeros lie on the
critical line" is not an identity — it is a cited numerical computation. As
NUMERICAL it would be HARD_VETO'd and rejected outright. The honest
classification is CITATION → κ1. This is itself a finding: the κ system has
no checker for the kind of numerical evidence (zero-counting, zero
verification) that is actually relevant to RH.
"""

from __future__ import annotations

from dataclasses import dataclass

from arxdb.verification.schema import EdgeType, Kappa


@dataclass(frozen=True)
class CorpusNode:
    """A claim to be imported as a `Node`.

    `key` is the corpus-internal identifier (N1..N8); `claim` is the
    proposition text; `domain` and `polarity` map directly onto `Node`.
    """

    key: str
    claim: str
    domain: str = "math"
    polarity: bool = True


@dataclass(frozen=True)
class CorpusEdge:
    """An inference step to be imported through `verify_and_commit`.

    `premise_keys` references `CorpusNode.key` values (empty for zero-premise
    edges: definitions, citations, the conjecture). `expected_kappa` is what
    the plan predicts the pipeline will assign — the seed script reports any
    mismatch. `source` is the provenance (NOEMA id / file path / paper).
    """

    key: str
    edge_type: EdgeType
    premise_keys: tuple[str, ...]
    conclusion_key: str
    rule: str
    expected_kappa: Kappa
    source: str
    proof_bytes: bytes | None = None


# --- nodes ------------------------------------------------------------------

CORPUS_NODES: tuple[CorpusNode, ...] = (
    CorpusNode(
        key="N1",
        claim=(
            "the scaling flow phi_t on the adele class space has closed "
            "orbits equal to the primes, with length log p"
        ),
    ),
    CorpusNode(
        key="N2",
        claim=(
            "S(T) = (1/pi) arg zeta(1/2+iT) = "
            "-(1/pi) sum_p sum_k p^(-k/2) sin(k T log p)/k"
        ),
    ),
    CorpusNode(
        key="N3",
        claim="N(T) = theta(T)/pi + 1 + S(T)",
    ),
    CorpusNode(
        key="N4",
        claim="H_BK = -i(x d/dx + 1/2) has purely continuous spectrum",
    ),
    CorpusNode(
        key="N5",
        claim="no self-adjoint realization of H_BK yields the Riemann zeros",
    ),
    CorpusNode(
        key="N6",
        claim="the first 10^13 nontrivial zeros of zeta lie on the critical line",
    ),
    CorpusNode(
        key="N7",
        claim="RH is true",
    ),
    CorpusNode(
        key="N8",
        claim="the Selberg zeta zeros obey RH",
    ),
    CorpusNode(
        key="N9",
        claim=(
            "there exists a self-adjoint operator whose eigenvalues are the "
            "imaginary parts of the nontrivial zeros of zeta"
        ),
    ),
)


# --- edges ------------------------------------------------------------------

CORPUS_EDGES: tuple[CorpusEdge, ...] = (
    CorpusEdge(
        key="E1",
        edge_type=EdgeType.DEFINITION,
        premise_keys=(),
        conclusion_key="N1",
        rule="solenoid scaling flow",
        expected_kappa=Kappa.K1,
        source="solenoid-scaling-flow/results.md, NOEMA 9db25d9aa15e",
    ),
    CorpusEdge(
        key="E2",
        edge_type=EdgeType.CITATION,
        premise_keys=(),
        conclusion_key="N2",
        rule="Euler product + explicit formula",
        expected_kappa=Kappa.K1,
        source="phase-is-the-valve/results.md, NOEMA a1f3c9d2b7e4",
    ),
    CorpusEdge(
        key="E3",
        edge_type=EdgeType.CITATION,
        premise_keys=("N2",),
        conclusion_key="N3",
        rule="phase-is-the-valve",
        expected_kappa=Kappa.K1,
        source="phase-is-the-valve/results.md, NOEMA a1f3c9d2b7e4",
    ),
    CorpusEdge(
        key="E4",
        edge_type=EdgeType.CITATION,
        premise_keys=(),
        conclusion_key="N4",
        rule="Endres-Steiner 2010",
        expected_kappa=Kappa.K1,
        source="Endres-Steiner 2010, arXiv:0912.3183",
    ),
    CorpusEdge(
        key="E5",
        edge_type=EdgeType.CITATION,
        premise_keys=("N4",),
        conclusion_key="N5",
        rule="phaser uniqueness theorem",
        expected_kappa=Kappa.K1,
        source="phaser-uniqueness/results.md, NOEMA e07bfe33ea59",
    ),
    CorpusEdge(
        key="E6",
        edge_type=EdgeType.CITATION,
        premise_keys=(),
        conclusion_key="N6",
        rule="Platt 2019 zeros bound",
        expected_kappa=Kappa.K1,
        source="Platt 2019",
    ),
    CorpusEdge(
        key="E7",
        edge_type=EdgeType.CITATION,
        premise_keys=(),
        conclusion_key="N8",
        rule="Selberg trace formula",
        expected_kappa=Kappa.K1,
        source="Selberg trace formula (standard)",
    ),
    CorpusEdge(
        key="E8",
        edge_type=EdgeType.ANALOGY,
        premise_keys=(),
        conclusion_key="N7",
        rule="Riemann Hypothesis",
        expected_kappa=Kappa.K0,
        source="the conjecture itself",
    ),
    CorpusEdge(
        key="E9",
        edge_type=EdgeType.CITATION,
        premise_keys=("N9",),
        conclusion_key="N7",
        rule="Hilbert-Polya operator",
        expected_kappa=Kappa.K1,
        source="Hilbert-Polya program (standard)",
    ),
)
