"""corpus.py — the RH seed corpus (declarative data).

Phase 4's first deliverable: our own RH reasoning, imported as nodes and
edges, to prove the tool on real material instead of toy axioms.

This module is *data*, not code. It contains no `verify_and_commit` calls, no
storage, no I/O — just frozen dataclasses enumerating the claims (nodes) and
the inference steps (edges) with their declared edge type, expected κ, and
source. The only imperative part of Phase 4 is `scripts/seed_phaser.py`,
which ingests this data through the public pipeline.

### v0.4: grown from the phaser thread to the full RH map

The corpus now spans five threads of our RH work, not just the phaser thread:

  - **Phaser thread** (N1–N9): the flow, the phase, the missing operator.
  - **Primon gas / free energy** (N10–N13): ζ as a partition function, the
    free energy as the missing structure.
  - **Pólya / total positivity** (N14–N16): the single condition that is RH.
  - **Large deviations / S(T)** (N17–N20): the 1/3 exponent and its mechanism.
  - **RG / Janus model** (N21–N23): the critical line as a fixed point, the
    Mellin transform as the valve.

### The central finding this corpus is designed to surface

Our RH material is a map of a *wall*, not a pile of proven theorems. Almost
none of it is Z3/Lean-checkable — analytic number theory is not first-order
arithmetic. So the honest κ for nearly every edge is κ1 (citation), with the
models and the conjecture itself at κ0, and zero κ3 deductions. The tool must
report this truthfully rather than inflate it.

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

    `key` is the corpus-internal identifier (N1..N23); `claim` is the
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
    CorpusNode(
        key="N10",
        claim=(
            "zeta(s) = prod_p (1 - p^(-s))^(-1) is the partition function of "
            "the primon gas: each prime p is a 'primon' with energy log p, "
            "and s is the inverse temperature"
        ),
    ),
    CorpusNode(
        key="N11",
        claim=(
            "F(s) = -log zeta(s) = sum_p log(1 - p^(-s)) is the free energy "
            "of the primon gas"
        ),
    ),
    CorpusNode(
        key="N12",
        claim=(
            "the zeros of zeta are the singularities of the free energy F(s), "
            "i.e. the phase transitions of the primon gas"
        ),
    ),
    CorpusNode(
        key="N13",
        claim=(
            "self-adjointness (reality of the free energy on the critical "
            "line) is the missing structure that collapses the 4-fold zero "
            "symmetry {rho, 1-rho, rho-bar, 1-rho-bar} to 2-fold "
            "(rho = 1-rho-bar, i.e. Re(rho) = 1/2)"
        ),
    ),
    CorpusNode(
        key="N14",
        claim=(
            "xi(1/2+it) = integral_{-inf}^{inf} Phi(u) e^(iut) du, with "
            "Phi(u) = sum_{n>=1} (4 pi^2 n^4 e^(9u/2) - 6 pi n^2 e^(5u/2)) "
            "e^(-pi n^2 e^(2u))"
        ),
    ),
    CorpusNode(
        key="N15",
        claim=(
            "Polya's criterion: if Phi is a Polya frequency function (totally "
            "positive, all minors >= 0), then xi(1/2+it) has all real zeros"
        ),
    ),
    CorpusNode(
        key="N16",
        claim=(
            "RH is equivalent to Phi being totally positive (the de Branges "
            "route; the converse to Polya is open)"
        ),
    ),
    CorpusNode(
        key="N17",
        claim=(
            "S(T) = (1/pi) arg zeta(1/2+iT) satisfies Selberg's central limit "
            "theorem: S(T)/sqrt((1/(2 pi^2)) log log T) -> N(0,1) in "
            "distribution"
        ),
    ),
    CorpusNode(
        key="N18",
        claim=(
            "S(t) = Omega_+-[(log t)^(1/3) (log log t)^(-7/3)] (Selberg 1946); "
            "Tsang (1986) removed the (log log t)^(-7/3) factor to get the "
            "clean (log T/log log T)^(1/3)"
        ),
    ),
    CorpusNode(
        key="N19",
        claim=(
            "the zero-density estimate N(sigma, T+H) - N(sigma, T) << "
            "H (H/sqrt(T))^((1/2-sigma)/2) log T (Selberg)"
        ),
    ),
    CorpusNode(
        key="N20",
        claim=(
            "the 1/3 exponent is the balance point between aligning the prime "
            "generators (W ~ sqrt(k)) and keeping the spectrum quiet (the "
            "zero-density bound caps k)"
        ),
    ),
    CorpusNode(
        key="N21",
        claim=(
            "the critical line Re(s) = 1/2 is a renormalization-group fixed "
            "point: primes = relevant operator (input), zeros = irrelevant "
            "operator (output), valve = running coupling"
        ),
    ),
    CorpusNode(
        key="N22",
        claim=(
            "the functional equation xi(s) = xi(1-s) is exactly the statement "
            "that xi is self-dual under the Mellin transform"
        ),
    ),
    CorpusNode(
        key="N23",
        claim=(
            "the valve is the Mellin transform (the specific Poisson summation "
            "for zeta); self-duality gives symmetry about the line but not "
            "placement on it"
        ),
    ),
    CorpusNode(
        key="N24",
        claim=(
            "positivity is the missing structure: the single condition that "
            "forces the zeros onto the critical line, unifying the "
            "Hilbert-Polya operator (N9), self-adjointness (N13), total "
            "positivity (N16), and what the Mellin transform fails to carry "
            "(N23)"
        ),
    ),
    CorpusNode(
        key="N25",
        claim=(
            "the primes are the spectrum (input) of the system: the closed "
            "orbits of the flow (N1), the primons of the gas (N10), and the "
            "relevant operator of the RG flow (N21) are three faces of one "
            "claim"
        ),
    ),
    CorpusNode(
        key="N26",
        claim=(
            "the critical line Re(s)=1/2 is a balance point: the phase "
            "transitions of the primon gas (N12), the 1/3 exponent balance "
            "(N20), and the RG fixed point (N21) all locate the same "
            "equilibrium"
        ),
    ),
    CorpusNode(
        key="N27",
        claim=(
            "the primes<->zeros correspondence is a self-encoding double "
            "helix: two complementary strands (primes = arithmetic, zeros = "
            "spectral) linked by the functional equation, with the phase "
            "arg zeta as the twist"
        ),
    ),
    CorpusNode(
        key="N28",
        claim=(
            "the Riemann-von Mangoldt formula N(T) = theta(T)/pi + 1 + S(T) "
            "is the topological identity Lk = Tw + Wr (Calugareanu-White-"
            "Fuller): gamma factor = twist, zeta = writhe, N(T) = linking "
            "number"
        ),
    ),
    CorpusNode(
        key="N29",
        claim=(
            "RH is equivalent to the mean writhe being bounded: "
            "integral_0^T S(t) dt = O(log T)"
        ),
    ),
    CorpusNode(
        key="N30",
        claim=(
            "RH is equivalent to the pointwise bound S(T) = O(log T / "
            "log log T)"
        ),
        polarity=False,
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
    CorpusEdge(
        key="E10",
        edge_type=EdgeType.CITATION,
        premise_keys=(),
        conclusion_key="N10",
        rule="Euler product reinterpreted as primon gas",
        expected_kappa=Kappa.K1,
        source="primon_gas_free_energy.md (free-energy-spectrum, 2026-08-21)",
    ),
    CorpusEdge(
        key="E11",
        edge_type=EdgeType.CITATION,
        premise_keys=("N10",),
        conclusion_key="N11",
        rule="free energy = -log partition function",
        expected_kappa=Kappa.K1,
        source="primon_gas_free_energy.md",
    ),
    CorpusEdge(
        key="E12",
        edge_type=EdgeType.CITATION,
        premise_keys=("N11",),
        conclusion_key="N12",
        rule="zeros = singularities of -log zeta",
        expected_kappa=Kappa.K1,
        source="primon_gas_free_energy.md",
    ),
    CorpusEdge(
        key="E13",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N12",),
        conclusion_key="N13",
        rule="Lee-Yang analogy: positivity forces zeros onto a line",
        expected_kappa=Kappa.K0,
        source="primon_gas_free_energy.md",
    ),
    CorpusEdge(
        key="E14",
        edge_type=EdgeType.CITATION,
        premise_keys=(),
        conclusion_key="N14",
        rule="Fourier representation of xi",
        expected_kappa=Kappa.K1,
        source="positivity_condition.md (verified 30 digits)",
    ),
    CorpusEdge(
        key="E15",
        edge_type=EdgeType.CITATION,
        premise_keys=("N14",),
        conclusion_key="N15",
        rule="Polya 1926",
        expected_kappa=Kappa.K1,
        source="Polya 1926",
    ),
    CorpusEdge(
        key="E16",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N15",),
        conclusion_key="N16",
        rule="de Branges route (converse open)",
        expected_kappa=Kappa.K0,
        source="positivity_condition.md",
    ),
    CorpusEdge(
        key="E17",
        edge_type=EdgeType.CITATION,
        premise_keys=(),
        conclusion_key="N17",
        rule="Selberg central limit theorem",
        expected_kappa=Kappa.K1,
        source="fluctuation_S_T.md",
    ),
    CorpusEdge(
        key="E18",
        edge_type=EdgeType.CITATION,
        premise_keys=(),
        conclusion_key="N18",
        rule="Selberg 1946 + Tsang 1986",
        expected_kappa=Kappa.K1,
        source="tsang_mechanism.md, NOEMA 5ea45f72362c",
    ),
    CorpusEdge(
        key="E19",
        edge_type=EdgeType.CITATION,
        premise_keys=(),
        conclusion_key="N19",
        rule="Selberg zero-density estimate",
        expected_kappa=Kappa.K1,
        source="zero_density_core.md, NOEMA 7fedaa8936b4",
    ),
    CorpusEdge(
        key="E20",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N18", "N19"),
        conclusion_key="N20",
        rule="generator/spectrum balance",
        expected_kappa=Kappa.K0,
        source="tsang_mechanism.md",
    ),
    CorpusEdge(
        key="E21",
        edge_type=EdgeType.ANALOGY,
        premise_keys=(),
        conclusion_key="N21",
        rule="RG flow model",
        expected_kappa=Kappa.K0,
        source="22_rg_flow_model.md",
    ),
    CorpusEdge(
        key="E22",
        edge_type=EdgeType.ANALOGY,
        premise_keys=(),
        conclusion_key="N22",
        rule="Janus synthesis: functional equation = self-duality",
        expected_kappa=Kappa.K0,
        source="23_janus_rg_synthesis.md",
    ),
    CorpusEdge(
        key="E23",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N22",),
        conclusion_key="N23",
        rule="Janus synthesis: valve = Mellin transform",
        expected_kappa=Kappa.K0,
        source="23_janus_rg_synthesis.md",
    ),
    CorpusEdge(
        key="E24",
        edge_type=EdgeType.CITATION,
        premise_keys=("N2",),
        conclusion_key="N17",
        rule="S(T) formula -> Selberg CLT for S(T)",
        expected_kappa=Kappa.K1,
        source="cross-thread bridge: S(T) defined in N2 satisfies the CLT in N17",
    ),
    CorpusEdge(
        key="E25",
        edge_type=EdgeType.CITATION,
        premise_keys=("N2",),
        conclusion_key="N18",
        rule="S(T) formula -> Omega-theorem for S(T)",
        expected_kappa=Kappa.K1,
        source="cross-thread bridge: S(T) defined in N2 satisfies the Omega-theorem in N18",
    ),
    CorpusEdge(
        key="E26",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N6",),
        conclusion_key="N7",
        rule="10^13 zeros on the line -> evidence for RH",
        expected_kappa=Kappa.K0,
        source="cross-thread bridge: numerical evidence supports the conjecture",
    ),
    CorpusEdge(
        key="E27",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N8",),
        conclusion_key="N7",
        rule="Selberg zeta obeys RH -> analogy for RH",
        expected_kappa=Kappa.K0,
        source="cross-thread bridge: a proven analogue of RH",
    ),
    CorpusEdge(
        key="E28",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N9",),
        conclusion_key="N13",
        rule="Hilbert-Polya operator <-> self-adjointness",
        expected_kappa=Kappa.K0,
        source="cross-thread bridge: the operator N9 is the self-adjointness N13",
    ),
    CorpusEdge(
        key="E29",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N13",),
        conclusion_key="N23",
        rule="self-adjointness <-> Mellin symmetry gap",
        expected_kappa=Kappa.K0,
        source="cross-thread bridge: self-adjointness is what the Mellin transform fails to carry",
    ),
    CorpusEdge(
        key="E30",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N16",),
        conclusion_key="N13",
        rule="total positivity <-> self-adjointness",
        expected_kappa=Kappa.K0,
        source="cross-thread bridge: both are 'positivity forces the line'",
    ),
    CorpusEdge(
        key="E31",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N1",),
        conclusion_key="N10",
        rule="flow orbits = primes <-> primon gas",
        expected_kappa=Kappa.K0,
        source="cross-thread bridge: both are 'primes as spectrum'",
    ),
    CorpusEdge(
        key="E32",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N12",),
        conclusion_key="N21",
        rule="zeros = phase transitions <-> critical line = RG fixed point",
        expected_kappa=Kappa.K0,
        source="cross-thread bridge: both locate the critical line as equilibrium",
    ),
    CorpusEdge(
        key="E33",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N20",),
        conclusion_key="N21",
        rule="1/3 balance <-> fixed point balance",
        expected_kappa=Kappa.K0,
        source="cross-thread bridge: both are 'the critical line is a balance point'",
    ),
    CorpusEdge(
        key="E34",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N22",),
        conclusion_key="N13",
        rule="self-duality <-> self-adjointness gap",
        expected_kappa=Kappa.K0,
        source="cross-thread bridge: self-duality gives symmetry, self-adjointness gives placement",
    ),
    CorpusEdge(
        key="E35",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N9",),
        conclusion_key="N24",
        rule="Hilbert-Polya operator is the positivity structure",
        expected_kappa=Kappa.K0,
        source="hub: positivity is the missing structure",
    ),
    CorpusEdge(
        key="E36",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N13",),
        conclusion_key="N24",
        rule="self-adjointness is the positivity structure",
        expected_kappa=Kappa.K0,
        source="hub: positivity is the missing structure",
    ),
    CorpusEdge(
        key="E37",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N16",),
        conclusion_key="N24",
        rule="total positivity is the positivity structure",
        expected_kappa=Kappa.K0,
        source="hub: positivity is the missing structure",
    ),
    CorpusEdge(
        key="E38",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N23",),
        conclusion_key="N24",
        rule="the Mellin transform fails to carry positivity",
        expected_kappa=Kappa.K0,
        source="hub: positivity is the missing structure",
    ),
    CorpusEdge(
        key="E39",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N1",),
        conclusion_key="N25",
        rule="flow orbits = primes",
        expected_kappa=Kappa.K0,
        source="hub: primes as spectrum",
    ),
    CorpusEdge(
        key="E40",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N10",),
        conclusion_key="N25",
        rule="primon gas = primes as spectrum",
        expected_kappa=Kappa.K0,
        source="hub: primes as spectrum",
    ),
    CorpusEdge(
        key="E41",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N21",),
        conclusion_key="N25",
        rule="primes = relevant operator (input)",
        expected_kappa=Kappa.K0,
        source="hub: primes as spectrum",
    ),
    CorpusEdge(
        key="E42",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N12",),
        conclusion_key="N26",
        rule="zeros = phase transitions at the balance",
        expected_kappa=Kappa.K0,
        source="hub: the critical line is a balance point",
    ),
    CorpusEdge(
        key="E43",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N20",),
        conclusion_key="N26",
        rule="1/3 exponent = balance",
        expected_kappa=Kappa.K0,
        source="hub: the critical line is a balance point",
    ),
    CorpusEdge(
        key="E44",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N21",),
        conclusion_key="N26",
        rule="fixed point = balance",
        expected_kappa=Kappa.K0,
        source="hub: the critical line is a balance point",
    ),
    CorpusEdge(
        key="E45",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N5",),
        conclusion_key="N9",
        rule="failure of the naive Berry-Keating operator -> the Hilbert-Polya operator is a genuine open problem",
        expected_kappa=Kappa.K0,
        source="cross-thread bridge: the negative result N5 is what makes N9 open",
    ),
    CorpusEdge(
        key="E46",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N3",),
        conclusion_key="N28",
        rule="von Mangoldt formula read topologically as Lk = Tw + Wr",
        expected_kappa=Kappa.K0,
        source="zeta-curve-writhe/results.md, NOEMA 820255c9c327",
    ),
    CorpusEdge(
        key="E47",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N2",),
        conclusion_key="N27",
        rule="phase arg zeta = the twist of the helix",
        expected_kappa=Kappa.K0,
        source="double-helix/results.md",
    ),
    CorpusEdge(
        key="E48",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N27",),
        conclusion_key="N28",
        rule="helix twist -> writhe decomposition",
        expected_kappa=Kappa.K0,
        source="double-helix/results.md",
    ),
    CorpusEdge(
        key="E49",
        edge_type=EdgeType.ANALOGY,
        premise_keys=("N28",),
        conclusion_key="N29",
        rule="writhe = S(T), so RH constrains the mean writhe",
        expected_kappa=Kappa.K0,
        source="zeta-curve-writhe/results.md",
    ),
    CorpusEdge(
        key="E50",
        edge_type=EdgeType.REFUTATION,
        premise_keys=(),
        conclusion_key="N30",
        rule=(
            "Littlewood 1924: S(T) = O(log T / log log T) is unconditional, "
            "so it cannot be equivalent to RH"
        ),
        expected_kappa=Kappa.K1,
        source="zeta-curve-writhe correction (this session)",
    ),
    CorpusEdge(
        key="E51",
        edge_type=EdgeType.CITATION,
        premise_keys=(),
        conclusion_key="N29",
        rule="RH <=> integral_0^T S(t) dt = O(log T) (mean bound)",
        expected_kappa=Kappa.K1,
        source="Titchmarsh (from training, medium-high confidence; verify)",
    ),
)
