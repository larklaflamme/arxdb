"""Tests for the query-layer boundary discipline (AST-verified).

The query layer must never reach into storage internals: no `sqlite3`, no
`pathlib`, no private attributes (`_conn`, `objects.root`). It resolves records
via ObjectStore decode and reads adjacency via public `Storage.graph` methods.
"""

from __future__ import annotations

import ast
from pathlib import Path

QUERY_DIR = Path("src/arxdb/query")

FORBIDDEN_MODULES = {"sqlite3", "pathlib"}
FORBIDDEN_ATTRS = ("_conn", "objects.root")


def _query_sources():
    return sorted(QUERY_DIR.glob("*.py"))


def test_no_forbidden_module_imports():
    for py_file in _query_sources():
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    assert root not in FORBIDDEN_MODULES, (
                        f"{py_file} imports forbidden module {alias.name!r}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module is not None:
                    root = node.module.split(".")[0]
                    assert root not in FORBIDDEN_MODULES, (
                        f"{py_file} imports from forbidden module {node.module!r}"
                    )


def test_no_private_storage_attributes():
    for py_file in _query_sources():
        source = py_file.read_text()
        for attr in FORBIDDEN_ATTRS:
            assert attr not in source, (
                f"{py_file} references private storage attribute {attr!r}"
            )
