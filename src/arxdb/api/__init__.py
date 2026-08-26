"""api/ — the ArxDB public HTTP API (Phase 7).

Exposes the two queries (reachability, path discovery) plus the
"reproduce the proof" story over a plain JSON HTTP API.

Public API:
    ArxDBApp  — the application logic (pure, testable without HTTP)
    serve     — run the HTTP server
"""

from .server import ArxDBApp, serve

__all__ = ["ArxDBApp", "serve"]
