# ArxDB — Development Environment Setup

This document lists every tool required to build, test, and run ArxDB, with the
exact versions and install locations used on the reference machine. It is the
single source of truth for onboarding a new developer or a fresh machine.

ArxDB is a two-language project: a **Python** verification/query layer and a
**Go** storage engine, connected over **gRPC**. You need all three toolchains.

---

## 1. System prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Linux (x86_64) | — | Reference machine is Ubuntu |
| `curl`, `unzip` | — | Used to fetch protoc |
| `git` | — | Repo is `github.com/larklaflamme/arxdb` |

No `sudo` is assumed. Everything below installs into the user's home directory
(`/home/ubuntu/...`) or a conda environment.

---

## 2. Python environment

ArxDB's Python layer runs in a dedicated conda environment named **`arxdb`**.

```bash
# Create the environment (Python 3.10+; reference uses 3.14.7)
conda create -n arxdb python=3.14
conda activate arxdb
```

### Core dependencies (from `pyproject.toml`)

| Package | Version | Purpose |
|---------|---------|---------|
| `blake3` | 1.0.9 | Content addressing (BLAKE3 multihash) |
| `cbor2` | 6.1.4 | Canonical CBOR serialization |
| `cryptography` | 50.0.1 | Ed25519 signing |

### Development dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | 9.1.1 | Test runner |
| `hypothesis` | 6.165.10 | Property-based testing |

### Verification-layer dependencies (used by the κ/ELENCHUS checkers)

| Package | Version | Purpose |
|---------|---------|---------|
| `sympy` | 1.14.0 | Symbolic verification |
| `mpmath` | 1.3.0 | Arbitrary-precision numerics |
| `z3-solver` | 5.1.0.0 | SMT verification |

Install everything:

```bash
pip install -e .            # core deps (editable install of the arxdb package)
pip install pytest hypothesis sympy mpmath z3-solver
```

> **Note:** the Lean checker (`checkers/lean_check.py`) additionally requires the
> **Lean 4** theorem prover, which is **not yet installed** on the reference
> machine. Four tests that exercise the Lean checker currently fail with
> `HARD_VETO` for this reason. See §6.

---

## 3. Go toolchain

The storage engine is written in Go. The reference machine uses **Go 1.27.0**,
installed from the official tarball (no `sudo`).

| Tool | Version | Location |
|------|---------|----------|
| Go | 1.27.0 | `/home/ubuntu/go-sdk/go` |
| `GOPATH` | — | `/home/ubuntu/go` |
| `GOBIN` | — | `/home/ubuntu/go/bin` |

```bash
# Install Go (adjust version as needed)
curl -sL -o /tmp/go.tar.gz https://go.dev/dl/go1.27.0.linux-amd64.tar.gz
mkdir -p /home/ubuntu/go-sdk
tar -C /home/ubuntu/go-sdk -xzf /tmp/go.tar.gz
```

### Go module dependencies (from `go/go.mod`)

| Package | Version | Purpose |
|---------|---------|---------|
| `github.com/cockroachdb/pebble` | 1.1.5 | KV store (the storage engine's DB) |
| `github.com/fxamacker/cbor/v2` | 2.9.3 | Canonical CBOR (parity with cbor2) |
| `github.com/zeebo/blake3` | 0.2.4 | BLAKE3 (parity with Python blake3) |

The Go module lives at `go/` with module path `github.com/larklaflamme/arxdb/go`.

---

## 4. gRPC toolchain

The Python and Go layers communicate over gRPC. This is the toolchain that was
**newly installed** for Phase 6.

### 4.1 protoc (the Protocol Buffers compiler)

| Tool | Version | Location |
|------|---------|----------|
| `protoc` | 36.0 | `/home/ubuntu/protoc/bin/protoc` |

```bash
curl -sL -o /tmp/protoc.zip \
  https://github.com/protocolbuffers/protobuf/releases/download/v36.0/protoc-36.0-linux-x86_64.zip
mkdir -p /home/ubuntu/protoc
unzip -o -q /tmp/protoc.zip -d /home/ubuntu/protoc
```

### 4.2 Go protoc plugins

| Tool | Version | Location |
|------|---------|----------|
| `protoc-gen-go` | 1.36.12 | `/home/ubuntu/go/bin` |
| `protoc-gen-go-grpc` | 1.6.2 | `/home/ubuntu/go/bin` |

```bash
export GOBIN=/home/ubuntu/go/bin
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
```

### 4.3 Python gRPC packages

| Package | Version | Purpose |
|---------|---------|---------|
| `grpcio` | 1.83.0 | gRPC runtime |
| `grpcio-tools` | 1.83.0 | `grpc_tools.protoc` (Python codegen) |
| `protobuf` | 7.36.0 | Protobuf runtime |

```bash
pip install grpcio grpcio-tools
```

### 4.4 Code generation

The single source of truth is `go/proto/arxdb.proto`. Generate both languages
from it:

```bash
# Go (from the go/ directory; output lands in go/proto/arxdbpb/)
protoc -I proto \
  --go_out=. --go_opt=module=github.com/larklaflamme/arxdb/go \
  --go-grpc_out=. --go-grpc_opt=module=github.com/larklaflamme/arxdb/go \
  proto/arxdb.proto

# Python (output lands in src/arxdb/storage/grpc_gen/)
python -m grpc_tools.protoc -I go/proto \
  --python_out=src/arxdb/storage/grpc_gen \
  --grpc_python_out=src/arxdb/storage/grpc_gen \
  go/proto/arxdb.proto
```

**Post-processing (required for the Python package to import).** The generated
`arxdb_pb2_grpc.py` uses an absolute `import arxdb_pb2`, which breaks when the
files live in a subpackage. Fix it to a relative import and add an `__init__.py`:

```bash
sed -i 's/^import arxdb_pb2 as arxdb__pb2/from . import arxdb_pb2 as arxdb__pb2/' \
  src/arxdb/storage/grpc_gen/arxdb_pb2_grpc.py
touch src/arxdb/storage/grpc_gen/__init__.py
```

> **Known minor discrepancy:** the standalone `protoc` is **36.0**, but
> `grpc_tools.protoc` (bundled with grpcio-tools 1.83.0) reports
> `libprotoc 35.1`. Both are recent and generate mutually compatible code; the
> discrepancy is cosmetic. Prefer the standalone `protoc` 36.0 for Go codegen
> and `grpc_tools.protoc` for Python codegen, as shown above.

---

## 5. Environment variables

Persist these in `~/.bashrc` (already done on the reference machine):

```bash
# Go
export GOROOT=/home/ubuntu/go-sdk/go
export GOPATH=/home/ubuntu/go
export GOBIN=/home/ubuntu/go/bin

# PATH — Go toolchain + protoc + Go plugins
export PATH="$PATH:$GOROOT/bin:$GOBIN:/home/ubuntu/protoc/bin"
```

---

## 6. Optional: Lean 4 (verification layer)

The `checkers/lean_check.py` checker shells out to the **Lean 4** theorem prover to
verify formal proofs. It is **not installed** on the reference machine, so the
four tests that exercise it fail with `HARD_VETO` (a pre-existing condition,
unrelated to the Go swap).

To enable full verification coverage, install **elan** (the Lean version
manager) via its official installer script, then install the stable Lean 4
toolchain:

```bash
# elan installer (see https://leanprover-community.github.io/get_started.html)
# then:
elan toolchain install leanprover/lean4:stable
```

This is a post-Phase-7 follow-up (Lean is the one remaining toolchain gap).

---

## 7. Verification checklist

Run these to confirm a fresh setup is correct:

```bash
# 1. Toolchain versions
protoc --version                 # libprotoc 36.0
protoc-gen-go --version          # protoc-gen-go v1.36.12
protoc-gen-go-grpc --version     # protoc-gen-go-grpc 1.6.2
go version                       # go1.27.0
python -c "import grpc; print(grpc.__version__)"   # 1.83.0

# 2. Go tests (parity moat + storage engine)
cd go && go test ./...           # all green

# 3. Python tests
cd .. && pytest tests/           # all green except the 4 Lean-dependent tests
```

---

## 8. Summary table

| Layer | Tool | Version | Status |
|-------|------|---------|--------|
| Python | conda env `arxdb` | 3.14.7 | ✅ |
| Python | blake3 / cbor2 / cryptography | 1.0.9 / 6.1.4 / 50.0.1 | ✅ |
| Python | pytest / hypothesis | 9.1.1 / 6.165.10 | ✅ |
| Python | sympy / mpmath / z3-solver | 1.14.0 / 1.3.0 / 5.1.0.0 | ✅ |
| Python | grpcio / grpcio-tools / protobuf | 1.83.0 / 1.83.0 / 7.36.0 | ✅ |
| Go | Go toolchain | 1.27.0 | ✅ |
| Go | Pebble / cbor / blake3 | 1.1.5 / 2.9.3 / 0.2.4 | ✅ |
| gRPC | protoc | 36.0 | ✅ |
| gRPC | protoc-gen-go / protoc-gen-go-grpc | 1.36.12 / 1.6.2 | ✅ |
| Verification | Lean 4 | — | ❌ not installed |
