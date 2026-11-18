<script lang="ts">
	import { ChevronRight, TriangleAlert } from '@lucide/svelte';
	import { formatDate } from '$lib/format';
	import { prettyCode } from '$lib/gtin';
	import type { Item } from '$lib/types';

	let { item, flagged = false }: { item: Item; flagged?: boolean } = $props();
</script>

<a class="item" href="/items/{item.id}" data-testid="item-row">
	<div class="grow">
		<p class="name">
			{#if flagged}<span class="flag" title="On a recall"><TriangleAlert size={15} /></span>{/if}
			{item.name}
			{#if item.quantity && item.quantity > 1}<span class="faint">× {item.quantity}</span>{/if}
		</p>
		<p class="meta small muted">
			{[item.brand, item.store, formatDate(item.purchasedAt)].filter(Boolean).join(' · ')}
		</p>
		{#if item.code || item.lot}
			<p class="codes tiny faint">
				{#if item.code}<span class="mono">{prettyCode(item.code, item.codeFormat)}</span>{/if}
				{#if item.lot}<span>Code <span class="mono">{item.lot}</span></span>{/if}
			</p>
		{/if}
	</div>
	<ChevronRight size={18} class="chev" />
</a>

<style>
	.item {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.85rem 1rem;
		color: inherit;
		text-decoration: none;
		border-top: 1px solid var(--line);
	}
	.item:first-child {
		border-top: 0;
	}
	.item:hover {
		background: color-mix(in srgb, var(--surface-2) 50%, transparent);
	}
	.name {
		font-weight: 600;
		display: flex;
		align-items: center;
		gap: 0.35rem;
	}
	.flag {
		color: var(--danger);
		display: inline-flex;
	}
	.codes {
		display: flex;
		gap: 0.75rem;
		margin-top: 0.15rem;
	}
	.item :global(.chev) {
		color: var(--faint);
		flex: none;
	}
</style>
