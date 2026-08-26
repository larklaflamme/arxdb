#!/usr/bin/env python3
"""client.py — drive the ArxDB public HTTP API end-to-end (Phase 7).

The "reproduce the proof" story, demonstrated over the wire: start the server,
author a couple of edges through the API, query reachability, then
independently re-verify a reasoning step and confirm its attestation — all
with nothing but stdlib HTTP.

Run from the repo root with the `arxdb` env active:

    python examples/08-public-api/client.py

The script starts its own server on a throwaway data directory and a fixed
port, so it is fully self-contained (no manual server setup needed).
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVE = REPO_ROOT / "scripts" / "arxdb_serve.py"
PYTHON = sys.executable
HOST = "127.0.0.1"
PORT = 8098
BASE = f"http://{HOST}:{PORT}"


def _post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    tmp = tempfile.mkdtemp(prefix="arxdb-api-")
    proc = subprocess.Popen(
        [PYTHON, str(SERVE), "--root", tmp, "--host", HOST, "--port", str(PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        # Wait for the server to come up.
        for _ in range(50):
            try:
                _get("/health")
                break
            except Exception:
                time.sleep(0.1)

        print("=== /health ===")
        print(json.dumps(_get("/health"), indent=2))

        # 1. Ground a premise as a definition (zero-premise edge).
        print("\n=== /commit: definition (grounds 'x > 0') ===")
        definition = _post(
            "/commit",
            {
                "premises": [],
                "conclusion": {"claim": "x > 0", "domain": "math"},
                "rule": "assumption",
                "edge_type": "definition",
            },
        )
        print(json.dumps(definition, indent=2))

        # 2. A deduction: x > 0  =>  x + 1 > 0  (Z3, kappa3).
        print("\n=== /commit: deduction (x > 0 => x + 1 > 0, Z3) ===")
        deduction = _post(
            "/commit",
            {
                "premises": [{"claim": "x > 0", "domain": "math"}],
                "conclusion": {"claim": "x + 1 > 0", "domain": "math"},
                "rule": "monotonicity of addition",
                "edge_type": "deduction",
            },
        )
        print(json.dumps(deduction, indent=2))
        edge_hash = deduction["edge_hash"]

        # 3. A citation carrying a proof blob (demonstrates proof binding).
        print("\n=== /commit: citation with a proof blob ===")
        proof_text = b"Euclid, Elements, Book I, Common Notion 5."
        citation = _post(
            "/commit",
            {
                "premises": [],
                "conclusion": {
                    "claim": "the whole is greater than the part",
                    "domain": "math",
                },
                "rule": "cite",
                "edge_type": "citation",
                "proof": base64.b64encode(proof_text).decode(),
            },
        )
        print(json.dumps(citation, indent=2))

        # 4. Query reachability.
        print("\n=== /query/reachable (x + 1 > 0) ===")
        print(json.dumps(_post("/query/reachable", {"claim": "x + 1 > 0", "domain": "math"}), indent=2))

        # 5. Path discovery.
        print("\n=== /query/path (x + 1 > 0) ===")
        print(json.dumps(_post("/query/path", {"claim": "x + 1 > 0", "domain": "math"}), indent=2))

        # 6. THE reproduce-the-proof story.
        print("\n=== /reproduce (the deduction edge) ===")
        print(json.dumps(_post("/reproduce", {"edge_hash": edge_hash}), indent=2))

        # 7. Attestation.
        print("\n=== /attest (the deduction edge) ===")
        print(json.dumps(_post("/attest", {"edge_hash": edge_hash}), indent=2))

        # 8. Anchor + trustless history verification.
        print("\n=== /anchor ===")
        anchor = _get("/anchor")
        print(json.dumps(anchor, indent=2))
        print("\n=== /verify_history (from the anchor root) ===")
        print(json.dumps(_post("/verify_history", {"root_hash": anchor["root_hash"]}), indent=2))
    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    main()
