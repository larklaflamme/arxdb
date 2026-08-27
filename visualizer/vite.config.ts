import adapter from '@sveltejs/adapter-node';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			// adapter-node produces a self-contained Node server (build/) that we
			// run in Docker. It also lets us proxy API calls server-side, so the
			// browser never talks to ArxDB directly (no CORS needed).
			adapter: adapter()
		})
	]
});
