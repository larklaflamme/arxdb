"""server.py — the ArxDB public HTTP API (Phase 7).

Exposes the two queries (reachability, path discovery) plus the
"reproduce the proof" story over a plain JSON HTTP API, so an external
user can query the graph and independently re-verify any reasoning step
without us.

Design:
  - Zero dependencies: stdlib `http.server` + `HTTPServer` (single-threaded).
  - `ArxDBApp` is the application logic (pure, testable without HTTP);
    the handler returned by `_make_handler` is the thin HTTP transport.
  - The server holds a `Storage` (SQLite or gRPC backend via the factory),
    a `Roster` (for attestation), and a signer keypair (the default proposer
    for the commit endpoint).

Endpoints:
  GET  /health                 -> {"status": "ok", "version": ...}
  POST /query/reachable        -> reachability result
  POST /query/path             -> path-discovery result
  POST /reproduce              -> the full reproduce-the-proof report
  POST /attest                 -> attestation (provenance/integrity/binding)
  GET  /anchor                 -> the anchor record (root hash, count, roster)
  POST /verify_history         -> trustless whole-history verification
  POST /commit                 -> verify-and-commit an edge (authoring)
"""

from __future__ import annotations

import base64
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from arxdb.attestation.attest import anchor, verify_edge_attestation, verify_history
from arxdb.attestation.roster import Roster
from arxdb.query.path import path_discovery
from arxdb.query.reachability import reachable
from arxdb.query.resolve import resolve_edge, resolve_node
from arxdb.storage.hashing import Hash
from arxdb.storage.storage import Storage
from arxdb.verification.commit import verify_and_commit
from arxdb.verification.schema import Edge, EdgeType, Kappa, Node
from arxdb.verification.verifier import verify

__version__ = "0.1.0"


class ApiError(Exception):
    """An application error that maps to an HTTP status code."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _h(h: Hash | None) -> str | None:
    """Hash -> hex string (None-safe)."""
    return h.hex() if h is not None else None


def _hex_to_hash(s: str) -> Hash:
    try:
        return Hash(bytes.fromhex(s))
    except ValueError:
        raise ApiError(400, f"invalid hex hash: {s!r}")


def _parse_pubkey(s: str) -> bytes:
    try:
        raw = bytes.fromhex(s)
    except ValueError:
        raise ApiError(400, f"invalid hex pubkey: {s!r}")
    if len(raw) != 32:
        raise ApiError(400, f"pubkey must be 32 bytes, got {len(raw)}")
    return raw


def _node_to_dict(n: Node) -> dict:
    return {
        "claim": n.claim,
        "domain": n.domain,
        "polarity": n.polarity,
        "node_id": _h(n.node_id()),
    }


def _edge_to_dict(e: Edge) -> dict:
    return {
        "type": e.type.value,
        "premises": [_h(p) for p in e.premises],
        "conclusion": _h(e.conclusion),
        "rule": e.rule,
        "proof_hash": _h(e.proof_hash),
        "verdict": e.verdict.value,
        "kappa": e.kappa.value,
        "signer_pubkey": e.signer_pubkey.hex(),
        "edge_hash": _h(e.edge_hash()),
    }


def _verification_to_dict(v) -> dict:
    return {
        "verdict": v.verdict.value,
        "kappa": v.kappa.value,
        "rejected": v.rejected,
    }


def _parse_kappa(s: str | None) -> Kappa:
    if s is None:
        return Kappa.K0
    try:
        return Kappa(s)
    except ValueError:
        raise ApiError(400, f"invalid min_kappa: {s!r}")


def _parse_node(d: Any) -> Node:
    if not isinstance(d, dict):
        raise ApiError(400, "node must be an object")
    claim = d.get("claim")
    if not isinstance(claim, str) or not claim:
        raise ApiError(400, "node.claim must be a non-empty string")
    domain = d.get("domain", "math")
    polarity = d.get("polarity", True)
    return Node(claim=claim, domain=domain, polarity=bool(polarity))


def _parse_edge_type(s: str) -> EdgeType:
    try:
        return EdgeType(s)
    except ValueError:
        raise ApiError(400, f"invalid edge_type: {s!r}")


# ---------------------------------------------------------------------------
# Application logic
# ---------------------------------------------------------------------------

class ArxDBApp:
    """The application logic behind the HTTP API (pure, no transport)."""

    def __init__(self, storage: Storage, roster: Roster, signer_pubkey: bytes) -> None:
        self.storage = storage
        self.roster = roster
        self.signer_pubkey = signer_pubkey

    # -- queries -----------------------------------------------------------

    def query_reachable(self, body: dict) -> dict:
        node = _parse_node(body)
        min_kappa = _parse_kappa(body.get("min_kappa"))
        r = reachable(node.node_id(), self.storage, min_kappa=min_kappa)
        return {
            "target": _node_to_dict(node),
            "min_kappa": min_kappa.value,
            "established": r.established,
            "kappa": r.kappa.value if r.kappa is not None else None,
            "depth": r.depth,
            "proof_tree_edges": [_h(e) for e in r.proof_tree_edges],
        }

    def query_path(self, body: dict) -> dict:
        node = _parse_node(body)
        min_kappa = _parse_kappa(body.get("min_kappa"))
        r = path_discovery(node.node_id(), self.storage, min_kappa=min_kappa)
        return {
            "target": _node_to_dict(node),
            "min_kappa": min_kappa.value,
            "reachable": r.reachable,
            "depth": r.depth,
            "kappa": r.kappa.value if r.kappa is not None else None,
            "missing_edges": [
                {
                    "conclusion": _h(m.conclusion),
                    "premises": [_h(p) for p in m.premises],
                    "blocking_nodes": [_h(p) for p in m.blocking_nodes],
                    "rule": m.rule,
                }
                for m in r.missing_edges
            ],
        }

    # -- reproduce / attest -------------------------------------------------

    def reproduce(self, body: dict) -> dict:
        edge_hash = _hex_to_hash(body["edge_hash"])
        edge = resolve_edge(edge_hash, self.storage)
        if edge is None:
            raise ApiError(404, "edge not found")

        premises: list[Node] = []
        for p in edge.premises:
            n = resolve_node(p, self.storage)
            if n is None:
                raise ApiError(500, f"premise node {p.hex()} not resolvable")
            premises.append(n)
        conclusion = resolve_node(edge.conclusion, self.storage)
        if conclusion is None:
            raise ApiError(500, f"conclusion node {edge.conclusion.hex()} not resolvable")

        proof = (
            self.storage.objects.get(edge.proof_hash)
            if edge.proof_hash is not None
            else None
        )
        re_verify = verify(premises, conclusion, edge.rule, edge.type, proof)
        attestation = verify_edge_attestation(edge, self.storage, self.roster)

        verdict_match = re_verify.verdict == edge.verdict
        kappa_match = re_verify.kappa == edge.kappa

        return {
            "edge": _edge_to_dict(edge),
            "premises": [_node_to_dict(n) for n in premises],
            "conclusion": _node_to_dict(conclusion),
            "rule": edge.rule,
            "proof": base64.b64encode(proof).decode() if proof is not None else None,
            "embedded": {"verdict": edge.verdict.value, "kappa": edge.kappa.value},
            "re_verified": _verification_to_dict(re_verify),
            "verdict_match": verdict_match,
            "kappa_match": kappa_match,
            "attestation": {
                "signer_agent_id": attestation.signer_agent_id,
                "signature_valid": attestation.signature_valid,
                "proof_bound": attestation.proof_bound,
                "proof_intact": attestation.proof_intact,
                "ok": attestation.ok,
            },
            "reproduced": verdict_match and kappa_match and attestation.ok,
        }

    def attest(self, body: dict) -> dict:
        edge_hash = _hex_to_hash(body["edge_hash"])
        edge = resolve_edge(edge_hash, self.storage)
        if edge is None:
            raise ApiError(404, "edge not found")
        a = verify_edge_attestation(edge, self.storage, self.roster)
        return {
            "edge_hash": _h(edge_hash),
            "signer_agent_id": a.signer_agent_id,
            "signature_valid": a.signature_valid,
            "proof_bound": a.proof_bound,
            "proof_intact": a.proof_intact,
            "ok": a.ok,
        }

    def anchor_record(self) -> dict:
        a = anchor(self.storage, self.roster)
        return {
            "root_hash": _h(a.root_hash),
            "entry_count": a.entry_count,
            "timestamp_ns": a.timestamp_ns,
            "roster_hash": _h(a.roster_hash),
        }

    def verify_history_endpoint(self, body: dict) -> dict:
        root = _hex_to_hash(body["root_hash"])
        ok = verify_history(self.storage, root)
        return {"root_hash": _h(root), "valid": ok}

    # -- authoring ----------------------------------------------------------

    def commit(self, body: dict) -> dict:
        premises = [_parse_node(p) for p in body.get("premises", [])]
        conclusion = _parse_node(body["conclusion"])
        rule = body.get("rule", "")
        edge_type = _parse_edge_type(body["edge_type"])
        proof_b64 = body.get("proof")
        proof = base64.b64decode(proof_b64) if proof_b64 else None
        signer_hex = body.get("signer_pubkey")
        signer = _parse_pubkey(signer_hex) if signer_hex else self.signer_pubkey
        timeout = float(body.get("timeout_seconds", 5.0))
        cr = verify_and_commit(
            self.storage, signer, premises, conclusion, rule, edge_type, proof, timeout
        )
        return {
            "rejected": cr.rejected,
            "verification": _verification_to_dict(cr.verification),
            "edge": _edge_to_dict(cr.edge) if cr.edge is not None else None,
            "edge_hash": _h(cr.edge_hash),
        }


# ---------------------------------------------------------------------------
# HTTP transport
# ---------------------------------------------------------------------------

def _make_handler(app: ArxDBApp) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, status: int, payload: dict) -> None:
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _read_body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            if not raw:
                return {}
            try:
                return json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                raise ApiError(400, "request body is not valid JSON")

        def _route(self) -> None:
            path = self.path.split("?", 1)[0]
            method = self.command
            try:
                if method == "GET" and path == "/health":
                    self._send_json(200, {"status": "ok", "version": __version__})
                    return
                if method == "GET" and path == "/anchor":
                    self._send_json(200, app.anchor_record())
                    return
                body = self._read_body()
                if method == "POST" and path == "/query/reachable":
                    self._send_json(200, app.query_reachable(body))
                elif method == "POST" and path == "/query/path":
                    self._send_json(200, app.query_path(body))
                elif method == "POST" and path == "/reproduce":
                    self._send_json(200, app.reproduce(body))
                elif method == "POST" and path == "/attest":
                    self._send_json(200, app.attest(body))
                elif method == "POST" and path == "/verify_history":
                    self._send_json(200, app.verify_history_endpoint(body))
                elif method == "POST" and path == "/commit":
                    self._send_json(200, app.commit(body))
                else:
                    self._send_json(404, {"error": f"no route for {method} {path}"})
            except ApiError as e:
                self._send_json(e.status, {"error": e.message})
            except KeyError as e:
                self._send_json(400, {"error": f"missing field: {e}"})
            except Exception as e:  # noqa: BLE001
                self._send_json(500, {"error": f"internal error: {e}"})

        def do_GET(self) -> None:
            self._route()

        def do_POST(self) -> None:
            self._route()

        def log_message(self, fmt: str, *args: Any) -> None:  # quiet by default
            pass

    return Handler


def serve(app: ArxDBApp, host: str, port: int) -> None:
    """Run the HTTP server until interrupted."""
    handler = _make_handler(app)
    httpd = HTTPServer((host, port), handler)
    print(f"ArxDB API listening on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
