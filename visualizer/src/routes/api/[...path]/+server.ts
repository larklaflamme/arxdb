// +server.ts — a same-origin proxy to the ArxDB backend.
//
// The browser calls `/api/query/graph`, `/api/reproduce`, etc. This handler
// forwards those calls to the real backend (ARXDB_API_URL) server-side. Two
// benefits:
//
//   1. No CORS — the browser only ever talks to this Node server.
//   2. The backend URL is a runtime env var, so the same image works against
//      any ArxDB deployment without a rebuild.
//
// ARXDB_API_URL defaults to http://localhost:8080 for local dev.

import type { RequestHandler } from './$types';

const ARXDB_API_URL = process.env.ARXDB_API_URL ?? 'http://localhost:8080';

function forward(res: Response): Response {
	return new Response(res.body, {
		status: res.status,
		headers: { 'Content-Type': 'application/json' }
	});
}

export const GET: RequestHandler = async ({ params, url }) => {
	const path = params.path;
	const target = `${ARXDB_API_URL}/${path}${url.search}`;
	const res = await fetch(target);
	return forward(res);
};

export const POST: RequestHandler = async ({ params, request }) => {
	const path = params.path;
	const target = `${ARXDB_API_URL}/${path}`;
	const body = await request.text();
	const res = await fetch(target, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body
	});
	return forward(res);
};
