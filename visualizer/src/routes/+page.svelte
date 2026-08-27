<script lang="ts">
	import { onMount } from 'svelte';
	import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide } from 'd3-force';
	import { select } from 'd3-selection';
	import { zoom, zoomIdentity, type ZoomBehavior } from 'd3-zoom';
	import 'd3-transition';
	import { fetchGraph, reproduce } from '$lib/api';
	import type { GraphResponse, ReproduceResponse } from '$lib/types';

	// -- reactive state ------------------------------------------------------
	let graph: GraphResponse | null = $state(null);
	let error: string | null = $state(null);
	let selected: ReproduceResponse | null = $state(null);
	let selectedHash: string | null = $state(null);
	let loading = $state(false);

	let svgEl: SVGSVGElement;

	// The zoom behavior is created once per render and stored here so the
	// toolbar buttons can drive it (scaleBy / reset).
	let zoomBehavior: ZoomBehavior<SVGSVGElement, unknown> | null = null;

	// κ → color. This is the visual heart of the tool: the confidence of a
	// claim is visible at a glance, and the "weakest link" in a chain pops out
	// as the one amber/gray edge in a green chain.
	const KAPPA_COLORS: Record<string, string> = {
		K0: '#64748b', // unverified — gray
		K1: '#f59e0b', // weak — amber
		K2: '#22d3ee', // moderate — cyan
		K3: '#10b981', // strong — green
		K_INF: '#8b5cf6' // axiom — violet
	};

	function kappaColor(k: string | null | undefined): string {
		return KAPPA_COLORS[k ?? 'K0'] ?? '#64748b';
	}

	// -- data loading --------------------------------------------------------
	onMount(async () => {
		try {
			graph = await fetchGraph();
			renderGraph(graph);
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		}
	});

	// -- d3 force layout -----------------------------------------------------
	function renderGraph(g: GraphResponse) {
		const nodeMap = new Map<string, (typeof g.nodes)[number]>();
		for (const n of g.nodes) nodeMap.set(n.node_id, n);

		// d3 nodes: { id, ...node }
		const nodes = g.nodes.map((n) => ({ id: n.node_id, ...n }));

		// d3 links: source/target are node ids; carry the edge record along.
		const links = g.edges
			.filter((e) => nodeMap.has(e.conclusion))
			.map((e) => ({
				source: e.premises[0] ?? e.conclusion,
				target: e.conclusion,
				edge: e
			}))
			.filter((l) => nodeMap.has(l.source as string));

		const svg = select(svgEl);
		svg.selectAll('*').remove();

		const width = svgEl.clientWidth || 900;
		const height = svgEl.clientHeight || 600;

		// A single root <g> holds everything; zoom/pan transforms this group.
		const root = svg.append('g');

		// edges (lines), colored by κ, clickable to reproduce.
		const link = root
			.append('g')
			.selectAll('line')
			.data(links)
			.join('line')
			.attr('stroke', (d: any) => kappaColor(d.edge.kappa))
			.attr('stroke-width', 1.5)
			.attr('stroke-opacity', 0.55)
			.style('cursor', 'pointer')
			.on('click', (_event: any, d: any) => onEdgeClick(d.edge.edge_hash));

		// nodes (circles), colored by κ.
		const node = root
			.append('g')
			.selectAll('circle')
			.data(nodes)
			.join('circle')
			.attr('r', 6)
			.attr('fill', (d: any) => kappaColor(d.kappa))
			.attr('stroke', '#0f172a')
			.attr('stroke-width', 1.5);

		// labels.
		const label = root
			.append('g')
			.selectAll('text')
			.data(nodes)
			.join('text')
			.text((d: any) => d.claim)
			.attr('font-size', 10)
			.attr('fill', '#e2e8f0')
			.attr('dx', 9)
			.attr('dy', 3);

		const sim = forceSimulation(nodes as any)
			.force(
				'link',
				forceLink(links as any)
					.id((d: any) => d.id)
					.distance(140)
			)
			.force('charge', forceManyBody().strength(-320))
			.force('center', forceCenter(width / 2, height / 2))
			.force('collide', forceCollide().radius(34))
			.on('tick', () => {
				link
					.attr('x1', (d: any) => d.source.x)
					.attr('y1', (d: any) => d.source.y)
					.attr('x2', (d: any) => d.target.x)
					.attr('y2', (d: any) => d.target.y);
				node.attr('cx', (d: any) => d.x).attr('cy', (d: any) => d.y);
				label.attr('x', (d: any) => d.x).attr('y', (d: any) => d.y);
			});

		// -- zoom + pan ------------------------------------------------------
		// Wheel = zoom, drag = pan (horizontal + vertical movement). The
		// toolbar buttons drive the same behavior programmatically.
		const z = zoom<SVGSVGElement, unknown>()
			.scaleExtent([0.2, 8])
			.on('zoom', (event) => {
				root.attr('transform', event.transform.toString());
			});
		svg.call(z);
		zoomBehavior = z;
	}

	// -- toolbar: zoom in / out / reset --------------------------------------
	function zoomIn() {
		if (!zoomBehavior) return;
		select(svgEl).transition().duration(200).call(zoomBehavior.scaleBy, 1.5);
	}
	function zoomOut() {
		if (!zoomBehavior) return;
		select(svgEl).transition().duration(200).call(zoomBehavior.scaleBy, 0.7);
	}
	function zoomReset() {
		if (!zoomBehavior) return;
		select(svgEl).transition().duration(200).call(zoomBehavior.transform, zoomIdentity);
	}

	// -- edge click → reproduce the proof ------------------------------------
	async function onEdgeClick(edgeHash: string) {
		selectedHash = edgeHash;
		loading = true;
		selected = null;
		try {
			selected = await reproduce(edgeHash);
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head>
	<title>ArxDB Visualizer</title>
</svelte:head>

<div class="app">
	<header>
		<h1>ArxDB <span>Visualizer</span></h1>
		<p class="sub">A database that stores reasoning, not just facts. Click an edge to re-verify its proof.</p>
	</header>

	<div class="legend">
		{#each Object.entries(KAPPA_COLORS) as [k, color]}
			<span class="legend-item">
				<span class="dot" style="background:{color}"></span>
				{k}
			</span>
		{/each}
	</div>

	<main>
		<div class="graph-pane">
			{#if error}
				<div class="error">⚠ {error}</div>
			{:else if !graph}
				<div class="loading">Loading graph…</div>
			{/if}
			<svg bind:this={svgEl} class="graph"></svg>

			<div class="toolbar">
				<button onclick={zoomIn} title="Zoom in">+</button>
				<button onclick={zoomOut} title="Zoom out">−</button>
				<button onclick={zoomReset} title="Reset view">⤢</button>
			</div>
		</div>

		<aside class="panel">
			{#if loading}
				<div class="loading">Re-verifying…</div>
			{:else if selected}
				<h2>Reproduce the proof</h2>
				<div class="field"><span class="k">rule</span> {selected.rule}</div>
				<div class="field"><span class="k">conclusion</span> {selected.conclusion.claim}</div>
				<div class="field">
					<span class="k">verdict</span>
					<span class="badge {selected.reproduced ? 'ok' : 'bad'}">
						{selected.re_verified.verdict} · {selected.re_verified.kappa}
					</span>
				</div>
				<div class="field">
					<span class="k">verdict match</span> {selected.verdict_match ? '✓' : '✗'}
				</div>
				<div class="field">
					<span class="k">κ match</span> {selected.kappa_match ? '✓' : '✗'}
				</div>
				<div class="field">
					<span class="k">attestation</span> {selected.attestation.ok ? '✓ valid' : '✗ invalid'}
				</div>
				<div class="verdict-line {selected.reproduced ? 'ok' : 'bad'}">
					{selected.reproduced ? 'REPRODUCED' : 'FAILED TO REPRODUCE'}
				</div>
			{:else}
				<h2>Reproduce the proof</h2>
				<p class="hint">Click any edge in the graph to independently re-run its verification and check that the stored verdict and κ still hold.</p>
			{/if}
		</aside>
	</main>
</div>

<style>
	:global(body) {
		margin: 0;
		background: #0f172a;
		color: #e2e8f0;
		font-family: 'Inter', 'Helvetica Neue', system-ui, sans-serif;
	}

	.app {
		display: flex;
		flex-direction: column;
		height: 100vh;
		padding: 1.25rem 1.5rem;
		box-sizing: border-box;
		gap: 0.75rem;
	}

	header h1 {
		margin: 0;
		font-size: 1.5rem;
		font-weight: 700;
	}
	header h1 span {
		color: #22d3ee;
	}
	.sub {
		margin: 0.25rem 0 0;
		color: #94a3b8;
		font-size: 0.9rem;
	}

	.legend {
		display: flex;
		gap: 1rem;
		flex-wrap: wrap;
	}
	.legend-item {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		font-size: 0.8rem;
		color: #cbd5e1;
	}
	.dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		display: inline-block;
	}

	main {
		display: flex;
		gap: 1rem;
		flex: 1;
		min-height: 0;
	}

	.graph-pane {
		flex: 1;
		position: relative;
		background: #0b1120;
		border: 1px solid #1e293b;
		border-radius: 10px;
		overflow: hidden;
	}
	.graph {
		width: 100%;
		height: 100%;
		display: block;
		cursor: grab;
	}
	.graph:active {
		cursor: grabbing;
	}

	.toolbar {
		position: absolute;
		top: 0.75rem;
		right: 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}
	.toolbar button {
		width: 2rem;
		height: 2rem;
		border: 1px solid #1e293b;
		border-radius: 6px;
		background: #0f172a;
		color: #e2e8f0;
		font-size: 1.1rem;
		line-height: 1;
		cursor: pointer;
		transition: background 0.15s, border-color 0.15s;
	}
	.toolbar button:hover {
		background: #1e293b;
		border-color: #334155;
	}

	.panel {
		width: 300px;
		flex-shrink: 0;
		background: #0b1120;
		border: 1px solid #1e293b;
		border-radius: 10px;
		padding: 1rem;
		overflow-y: auto;
	}
	.panel h2 {
		margin: 0 0 0.75rem;
		font-size: 1rem;
		color: #22d3ee;
	}
	.field {
		margin-bottom: 0.5rem;
		font-size: 0.85rem;
		word-break: break-word;
	}
	.k {
		color: #64748b;
		margin-right: 0.4rem;
	}
	.badge {
		padding: 0.1rem 0.5rem;
		border-radius: 4px;
		font-weight: 600;
	}
	.badge.ok {
		background: #10b98122;
		color: #10b981;
	}
	.badge.bad {
		background: #ef444422;
		color: #ef4444;
	}
	.verdict-line {
		margin-top: 0.75rem;
		padding: 0.5rem;
		border-radius: 6px;
		text-align: center;
		font-weight: 700;
		font-size: 0.85rem;
	}
	.verdict-line.ok {
		background: #10b98122;
		color: #10b981;
	}
	.verdict-line.bad {
		background: #ef444422;
		color: #ef4444;
	}
	.hint {
		color: #94a3b8;
		font-size: 0.85rem;
		line-height: 1.5;
	}

	.loading,
	.error {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		color: #94a3b8;
	}
	.error {
		color: #ef4444;
	}
</style>
