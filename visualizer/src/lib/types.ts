// types.ts — the typed contract of the ArxDB public HTTP API.
//
// These mirror the response shapes documented in PUBLIC_API.md. They are the
// dogfooding artifact: a typed client for the public API that any third party
// can copy into their own project.

export interface Node {
	claim: string;
	domain: string;
	polarity: boolean;
	node_id: string;
}

export interface Edge {
	type: string;
	premises: string[];
	conclusion: string;
	rule: string;
	proof_hash: string | null;
	verdict: string;
	kappa: string;
	signer_pubkey: string;
	edge_hash: string;
}

/** Response of GET /query/graph — the whole reasoning graph. */
export interface GraphResponse {
	nodes: Node[];
	edges: Edge[];
}

/** Response of POST /query/reachable. */
export interface ReachableResponse {
	target: Node;
	min_kappa: string;
	established: boolean;
	kappa: string | null;
	depth: number | null;
	proof_tree_edges: string[];
}

/** Response of POST /reproduce — the re-verification report. */
export interface ReproduceResponse {
	edge: Edge;
	premises: Node[];
	conclusion: Node;
	rule: string;
	proof: string | null;
	embedded: { verdict: string; kappa: string };
	re_verified: { verdict: string; kappa: string; rejected: boolean };
	verdict_match: boolean;
	kappa_match: boolean;
	attestation: {
		signer_agent_id: string | null;
		signature_valid: boolean;
		proof_bound: boolean;
		proof_intact: boolean;
		ok: boolean;
	};
	reproduced: boolean;
}
