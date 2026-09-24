"""spectral_check.py — the spectral checker (numpy/mpmath).

Verifies numeric spectral claims about matrices: self-adjointness, symmetry,
real spectrum, and low-rank structure. The claim text has the form

    "<property> <matrix_expr>"

where <property> is a fixed-vocabulary keyword and <matrix_expr> is a
restricted-eval expression (numpy + mpmath + registered constructors) that
evaluates to a 2D array. On success the property holds within tolerance (κ2);
on failure it does not, or the claim is not parseable (a clean failure — never
a silent pass).

Why this checker exists: the operator-theory findings in the RH ontology
(self-adjointness of L_{1/4}, low-rank defect, broken PT-symmetry) are spectral
claims that neither the CAS checker (sympy identities) nor the Z3 checker
(logical formulas) can verify. They are κ2 in spirit (mpmath-checked) but were
stuck at κ1 as CITATION edges. This checker re-runs the computation and earns
κ2.

Property vocabulary (single matrix M, tolerance tol):
    self_adjoint   — M ≈ M^H (Hermitian) AND all eigenvalues real
    symmetric      — M ≈ M^T (real symmetric)
    real_spectrum  — all eigenvalues have |Im| < tol
    complex_spectrum — some eigenvalue has |Im| > tol (broken PT)
    rank_leq:k     — at most k singular values exceed tol
    low_rank       — σ1 / σ2 > 10 (dominant singular value)

Boundary discipline: imports numpy/mpmath and the schema enums + base protocol.
No storage, no graph, no I/O.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import mpmath as mp

from ..schema import Kappa, Node
from .base import CheckerResult, CheckerTimeout, run_bounded

# --- registered constructors ------------------------------------------------

def bessel_kernel(nu, N):
    """The Bessel kernel K(x,y) = J_nu(2√(xy)) / (xy)^(nu/2), Gauss–Legendre.

    Returns an N×N complex numpy array. This is the operator whose determinant
    relates to ζ (Mayer's transfer-operator picture); L_{1/4} corresponds to
    nu = -1/2. Complex order nu is handled by mpmath.
    """
    x, w = np.polynomial.legendre.leggauss(int(N))
    s = (x + 1.0) / 2.0
    w = w / 2.0
    M = np.zeros((int(N), int(N)), dtype=complex)
    for i in range(int(N)):
        for j in range(int(N)):
            xy = float(s[i]) * float(s[j])
            z = 2.0 * np.sqrt(xy)
            K = mp.besselj(nu, z) / (xy ** (nu / 2))
            M[i, j] = np.sqrt(w[i] * w[j]) * complex(K)
    return M


_NAMESPACE = {
    "np": np,
    "mp": mp,
    "bessel_kernel": bessel_kernel,
    "array": np.array,
    "eye": np.eye,
    "zeros": np.zeros,
    "ones": np.ones,
    "diag": np.diag,
}

# --- property checks --------------------------------------------------------

_DEFAULT_TOL = 1e-10


def _as_matrix(obj) -> np.ndarray:
    arr = np.asarray(obj, dtype=complex)
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1]:
        raise ValueError(f"expected a square 2D matrix, got shape {arr.shape}")
    return arr


def _check(prop: str, M: np.ndarray, tol: float):
    if prop == "self_adjoint":
        hermitian_err = float(np.max(np.abs(M - M.conj().T)))
        evals = np.linalg.eigvals(M)
        im_err = float(np.max(np.abs(evals.imag)))
        ok = hermitian_err < tol and im_err < tol
        return ok, {"hermitian_err": hermitian_err, "max_im_eig": im_err}
    if prop == "symmetric":
        sym_err = float(np.max(np.abs(M - M.T)))
        return sym_err < tol, {"symmetry_err": sym_err}
    if prop == "real_spectrum":
        evals = np.linalg.eigvals(M)
        im_err = float(np.max(np.abs(evals.imag)))
        return im_err < tol, {"max_im_eig": im_err}
    if prop == "complex_spectrum":
        evals = np.linalg.eigvals(M)
        im_err = float(np.max(np.abs(evals.imag)))
        return im_err > tol, {"max_im_eig": im_err}
    if prop.startswith("rank_leq:"):
        k = int(prop.split(":", 1)[1])
        sv = np.linalg.svd(M, compute_uv=False)
        n_above = int(np.sum(sv > tol))
        return n_above <= k, {"singular_values": sv.tolist(), "n_above_tol": n_above}
    if prop == "low_rank":
        sv = np.linalg.svd(M, compute_uv=False)
        ratio = float(sv[0] / sv[1]) if len(sv) > 1 and sv[1] > 0 else float("inf")
        return ratio > 10.0, {"singular_values": sv.tolist(), "ratio_s1_s2": ratio}
    raise ValueError(f"unknown property {prop!r}")


class SpectralChecker:
    def check(
        self,
        premises: Sequence[Node],
        conclusion: Node,
        rule: str,
        proof_bytes: bytes | None,
        timeout_seconds: float = 5.0,
    ) -> CheckerResult:
        def _run() -> CheckerResult:
            claim = conclusion.claim.strip()
            if " " not in claim:
                return CheckerResult(
                    False, Kappa.K0, {}, "claim must be '<property> <matrix_expr>'"
                )
            prop, expr = claim.split(" ", 1)
            prop = prop.strip()
            expr = expr.strip()
            try:
                M = _as_matrix(eval(expr, {"__builtins__": {}}, _NAMESPACE))
                ok, details = _check(prop, M, _DEFAULT_TOL)
            except (ValueError, SyntaxError, NameError, TypeError, ZeroDivisionError) as e:
                return CheckerResult(False, Kappa.K0, {}, f"error: {e}")
            if ok:
                return CheckerResult(True, Kappa.K2, {"property": prop, **details})
            return CheckerResult(False, Kappa.K0, details, f"property {prop!r} failed")

        try:
            return run_bounded(_run, timeout_seconds)
        except CheckerTimeout as e:
            return CheckerResult(False, Kappa.K0, {}, str(e))
