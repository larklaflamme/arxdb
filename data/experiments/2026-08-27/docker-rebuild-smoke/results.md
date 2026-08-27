# Docker rebuild + full-stack smoke test

Date: 2026-08-27
Session: e3a2dd438a

## Goal
Rebuild the ArxDB Docker image locally and verify the full `docker compose up`
stack (arxdb + visualizer) works end-to-end, including the gRPC seeding path
added in the prior task.

## Bug found and fixed
The Dockerfile copied `scripts/arxdb_serve.py` but NOT `scripts/seed_phaser.py`,
while `docker-entrypoint.sh` calls `python scripts/seed_phaser.py`. The image
would have failed at the seed step. Fixed by adding:

    COPY scripts/seed_phaser.py ./scripts/seed_phaser.py

## Build results
- `docker build -t arxdb:local .` — SUCCESS (image 4e0a3af93240, 534MB)
- `docker build -t arxdb-visualizer:local ./visualizer` — SUCCESS (fabf852f8941, 358MB)

## Smoke test (arxdb container, gRPC backend, fresh volume)
- Seed ran inside container: 23 edges, all resolve to "Skye", entry_count=24
- `/health` -> {"status": "ok", "version": "0.1.0"}
- `/query/graph` -> 23 nodes, 23 edges, kappa K1:16 / K0:7
- Idempotency (restart warm volume): all edges SKIP, no duplicates, entry_count stays 24

## Full-stack integration (arxdb + visualizer on shared network)
- visualizer root -> HTTP 200 (HTML served)
- visualizer proxy `/api/query/graph` -> 23 nodes, 23 edges, K1:16/K0:7
- visualizer proxy `/api/reproduce` -> verdict_match:True, kappa_match:True, reproduced:True

## Host environment note
Port 8080 is occupied by an unrelated python process (pid 782003). The compose
override `ports` list MERGES (appends) rather than replaces, so the base
`8080:8080` binding still fired and failed. Worked around by running the two
containers manually on a shared network (arxdb with no host port, visualizer on
3090). This is a host-env conflict, not a code issue.

## Remaining (not done this task)
- Docker image NOT rebuilt/pushed to ghcr (push is gated).
- Nothing committed to git (working tree has all changes).
- `arxdb:test` image exists from a prior session (not created this session).

## Conclusion
The full stack works end-to-end. The gRPC seeding path is correct in the image.
The only blocker to external users is the image rebuild + push (gated).
