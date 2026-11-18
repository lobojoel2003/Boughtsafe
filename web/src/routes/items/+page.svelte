<script lang="ts">
	import { Download, Plus, Search } from '@lucide/svelte';
	import ItemRow from '$lib/components/ItemRow.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { toCsv } from '$lib/csv';
	import { download, plural, today } from '$lib/format';
	import { app } from '$lib/state.svelte';
	import type { ListKind } from '$lib/types';

	let q = $state('');
	let list = $state<ListKind | 'all'>('home');

	const flagged = $derived(new Set(app.alerts.map((a) => a.item.id)));
	const shown = $derived(
		app.items.filter(
			(i) =>
				(list === 'all' || i.list === list) &&
				(!q ||
					`${i.name} ${i.brand ?? ''} ${i.store ?? ''} ${i.code ?? ''} ${i.lot ?? ''}`
						.toLowerCase()
						.includes(q.toLowerCase()))
		)
	);

	function exportCsv() {
		const rows = [
			['name', 'brand', 'upc', 'lot', 'purchased', 'store', 'quantity', 'list'],
			...shown.map((i) => [
				i.name,
				i.brand,
				i.code,
				i.lot,
				i.purchasedAt,
				i.store,
				i.quantity,
				i.list
			])
		];
		download(`boughtsafe-items-${today()}.csv`, toCsv(rows), 'text/csv');
	}
</script>

<svelte:head><title>Items · Boughtsafe</title></svelte:head>

<PageHeader title="Your items" subtitle={plural(app.items.length, 'item') + ' on this device'}>
	{#snippet actions()}
		<a class="btn" href="/add"><Plus size={18} /> Add</a>
	{/snippet}
</PageHeader>

<div class="stack">
	<div class="row tools">
		<label class="search grow">
			<Search size={18} />
			<span class="visually-hidden">Search items</span>
			<input type="search" placeholder="Search name, store, barcode or lot" bind:value={q} />
		</label>
	</div>
	<div class="seg" role="tablist" aria-label="Which list">
		{#each [['home', 'My kitchen'], ['pantry', 'Pantry'], ['all', 'All']] as [value, label] (value)}
			<button
				role="tab"
				aria-selected={list === value}
				class:on={list === value}
				onclick={() => (list = value as ListKind | 'all')}>{label}</button
			>
		{/each}
	</div>

	{#if shown.length}
		<div class="panel list">
			{#each shown as item (item.id)}
				<ItemRow {item} flagged={flagged.has(item.id)} />
			{/each}
		</div>
		<button class="btn ghost small export" onclick={exportCsv}
			><Download size={16} /> Export CSV</button
		>
	{:else}
		<div class="empty panel">
			<p class="muted">{q ? 'Nothing matches that search.' : 'Nothing here yet.'}</p>
			<a class="btn primary" href="/add">Add something</a>
		</div>
	{/if}
</div>

<style>
	.search {
		position: relative;
		display: flex;
		align-items: center;
	}
	.search :global(svg) {
		position: absolute;
		left: 0.8rem;
		color: var(--faint);
	}
	.search input {
		padding-left: 2.4rem;
		border-radius: 999px;
	}
	.seg {
		display: inline-flex;
		background: var(--surface-2);
		border-radius: 999px;
		padding: 3px;
		align-self: flex-start;
	}
	.seg button {
		border: 0;
		background: transparent;
		font: inherit;
		font-weight: 600;
		font-size: 0.88rem;
		color: var(--muted);
		padding: 0.4rem 0.95rem;
		border-radius: 999px;
		cursor: pointer;
	}
	.seg button.on {
		background: var(--surface);
		color: var(--text);
		box-shadow: var(--shadow);
	}
	.list {
		overflow: hidden;
	}
	.empty {
		padding: 2rem 1rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
	}
	.export {
		align-self: flex-start;
	}
</style>
