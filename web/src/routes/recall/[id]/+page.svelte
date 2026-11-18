<script lang="ts">
	import { ExternalLink } from '@lucide/svelte';
	import { page } from '$app/state';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { api } from '$lib/api';
	import { formatDate } from '$lib/format';
	import { app } from '$lib/state.svelte';
	import type { Recall } from '$lib/types';

	const id = $derived(decodeURIComponent(page.params.id ?? ''));
	const itemId = $derived(page.url.searchParams.get('item'));
	const stored = $derived(
		app.matches.find((m) => m.recallId === id && (!itemId || m.itemId === itemId))
	);
	let fetched = $state<Recall | null>(null);
	let error = $state<string | null>(null);
	const recall = $derived(stored?.recall ?? fetched);

	$effect(() => {
		if (app.loaded && !stored && !fetched && id) {
			api.recall(id).then(
				(r) => (fetched = r),
				(e) => (error = (e as Error).message)
			);
		}
	});

	const rows = $derived(
		recall
			? ([
					['Product', recall.product],
					['Company', recall.firm],
					['Reason', recall.reason],
					['Codes', recall.codes || (recall.covers_all_codes ? 'All codes' : '')],
					['Barcodes', recall.gtins.map((g) => g.display).join(', ')],
					['Distribution', recall.distribution],
					['Classification', recall.classification],
					['Status', recall.status === 'ongoing' ? 'Ongoing' : 'Closed by the agency'],
					['Recall started', formatDate(recall.recall_date)],
					['Published', formatDate(recall.published_date)],
					[
						'Refund',
						[recall.refund.options.join(', '), recall.refund.text].filter(Boolean).join(': ')
					],
					['Contact', recall.refund.contact]
				].filter(([, v]) => v) as [string, string][])
			: []
	);
</script>

<svelte:head><title>{recall?.title ?? 'Recall'} · Boughtsafe</title></svelte:head>

<PageHeader
	title={recall?.hazard.label ?? 'Recall'}
	subtitle={recall?.title}
	back={itemId ? `/items/${itemId}` : '/'}
/>

{#if recall}
	<div class="stack">
		{#if recall.image_url}<img class="photo" src={recall.image_url} alt="Recalled product" />{/if}
		<div class="card stack">
			<h2>What to do</h2>
			<p>{recall.action}</p>
		</div>
		<dl class="card">
			{#each rows as [k, v] (k)}
				<dt>{k}</dt>
				<dd class:mono={k === 'Codes' || k === 'Barcodes'}>{v}</dd>
			{/each}
		</dl>
		{#if recall.url}
			<a class="btn primary lg" href={recall.url} target="_blank" rel="noopener noreferrer">
				Read the official {recall.source_label} notice <ExternalLink size={16} />
			</a>
		{/if}
		<p class="tiny faint">Source: {recall.source_label}, record {recall.id.split(':')[1]}.</p>
	</div>
{:else if error}
	<p class="chip danger">{error}</p>
{:else}
	<p class="muted">Loading…</p>
{/if}

<style>
	.photo {
		width: 100%;
		max-height: 18rem;
		object-fit: contain;
		background: #fff;
		border-radius: var(--radius);
		border: 1px solid var(--line);
	}
	dl {
		display: grid;
		grid-template-columns: minmax(7rem, max-content) 1fr;
		gap: 0.55rem 1rem;
		margin: 0;
	}
	dt {
		color: var(--faint);
		font-size: 0.85rem;
		font-weight: 600;
	}
	dd {
		margin: 0;
		word-break: break-word;
	}
	@media (max-width: 480px) {
		dl {
			grid-template-columns: 1fr;
		}
		dd {
			margin-bottom: 0.5rem;
		}
	}
</style>
