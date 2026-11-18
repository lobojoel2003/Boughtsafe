<script lang="ts">
	import { ShieldCheck } from '@lucide/svelte';
	import { relativeTime, plural } from '$lib/format';
	import { app } from '$lib/state.svelte';

	let { catalogTotal = 0 }: { catalogTotal?: number } = $props();
	const total = $derived(app.last?.catalogTotal || catalogTotal);
</script>

<section class="clear" aria-labelledby="clear-title">
	<div class="halo" aria-hidden="true">
		<div class="ring"><ShieldCheck size={44} strokeWidth={1.75} /></div>
	</div>
	<h1 id="clear-title">Nothing you own is on a recall list.</h1>
	<p class="muted lead">We'll stay quiet until that changes.</p>
	<p class="meta faint small" data-testid="check-meta">
		{plural(app.items.length, 'item')} checked
		{#if total}against {plural(total, 'recall')}{/if}
		· {app.checking ? 'checking…' : relativeTime(app.last?.checkedAt)}
	</p>
	<button class="btn ghost small" onclick={() => app.check()} disabled={app.checking}>
		Check again
	</button>
</section>

<style>
	.clear {
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
		gap: 0.75rem;
		padding: 3.5rem 0.5rem 2rem;
	}
	.halo {
		width: 148px;
		height: 148px;
		border-radius: 50%;
		display: grid;
		place-items: center;
		background: radial-gradient(
			circle,
			color-mix(in srgb, var(--accent-soft) 100%, transparent) 0%,
			transparent 70%
		);
		margin-bottom: 0.75rem;
	}
	.ring {
		width: 96px;
		height: 96px;
		border-radius: 50%;
		display: grid;
		place-items: center;
		color: var(--accent);
		background: var(--surface);
		border: 1px solid var(--line);
		box-shadow: var(--shadow);
		animation: settle 0.6s cubic-bezier(0.2, 0.8, 0.2, 1) both;
	}
	h1 {
		max-width: 18ch;
	}
	.lead {
		font-size: 1.05rem;
	}
	.meta {
		margin-top: 1.25rem;
	}
	@keyframes settle {
		from {
			transform: scale(0.92);
			opacity: 0;
		}
	}
</style>
