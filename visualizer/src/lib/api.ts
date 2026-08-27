// api.ts — a thin typed client for the ArxDB public API.
//
// All calls go through the same-origin `/api/*` proxy (see
// src/routes/api/[...path]/+server.ts), which forwards to the ArxDB backend
// server-side. This keeps the browser on a single origin (no CORS) and keeps
// the backend URL a runtime concern, not a build-time one.

import type { GraphResponse, ReachableResponse, ReproduceResponse } from './types';

const BASE = '/api';

async function post<T>(path: string, body: unknown): Promise<T> {
	const r = await fetch(`${BASE}${path}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	});
	if (!r.ok) {
		const err = await r.json().catch(() => ({ error: r.statusText }));
		throw new Error(err.error ?? `request failed: ${r.status}`);
	}
	return r.json();
}

async function get<T>(path: string): Promise<T> {
	const r = await fetch(`${BASE}${path}`);
	if (!r.ok) {
		const err = await r.json().catch(() => ({ error: r.statusText }));
		throw new Error(err.error ?? `request failed: ${r.status}`);
	}
	return r.json();
}

/** Fetch the entire reasoning graph (all nodes + edges). */
export function fetchGraph(): Promise<GraphResponse> {
	return get<GraphResponse>('/query/graph');
}

/** Ask whether a claim is established, and at what κ. */
export function reachable(claim: string): Promise<ReachableResponse> {
	return post<ReachableResponse>('/query/reachable', { claim });
}

/** Re-verify a single reasoning edge and report whether it still holds. */
export function reproduce(edge_hash: string): Promise<ReproduceResponse> {
	return post<ReproduceResponse>('/reproduce', { edge_hash });
}
