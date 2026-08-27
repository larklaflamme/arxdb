# ArxDB Visualizer

A read-only web client for [ArxDB](../README.md) — a database that stores
reasoning, not just facts. It renders the reasoning graph as a force-directed
layout, colors every node and edge by its κ (confidence) level, and lets you
click any edge to **independently re-verify its proof**.

## Stack

- **SvelteKit** (Svelte 5, runes mode) + **TypeScript**
- **d3-force** / **d3-selection** for the graph layout
- **adapter-node** — builds a self-contained Node server for Docker

## Architecture

The visualizer is a *client of the public API*, not a part of the database.
Its only coupling to ArxDB is the HTTP contract. That boundary is enforced by
Docker: the visualizer runs in its own container and reaches ArxDB only over
the network.

```
browser ──► visualizer (Node, :3000) ──► /api/* proxy ──► arxdb (HTTP, :8080)
```

All API calls go through a same-origin proxy
(`src/routes/api/[...path]/+server.ts`), which forwards to `ARXDB_API_URL`
server-side. This keeps the browser on one origin (no CORS) and makes the
backend URL a runtime env var.

## Run locally

```bash
npm install
ARXDB_API_URL=http://localhost:8080 npm run dev
```

## Run with Docker (the whole stack)

From the repo root:

```bash
docker compose up -d
# visualizer at http://localhost:3000
# arxdb at      http://localhost:8080
```

## The typed API client

`src/lib/types.ts` + `src/lib/api.ts` are a typed contract of the public API.
They're the dogfooding artifact: proof that the public API is enough to build
a real client on top of, and a starting point any third party can copy.
