<script lang="ts">
	import { Trash2 } from '@lucide/svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import ItemForm from '$lib/components/ItemForm.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { formatDate } from '$lib/format';
	import { app } from '$lib/state.svelte';
	import type { Item } from '$lib/types';

	const original = $derived(app.itemsById.get(page.params.id ?? ''));
	let draft = $state<Item | null>(null);
	let saving = $state(false);

	$effect(() => {
		if (original && (!draft || draft.id !== original.id)) draft = { ...original };
	});

	const history = $derived(app.matches.filter((m) => m.itemId === original?.id));
	const ruled = $derived(app.ruledOut.filter((r) => r.item_id === original?.id));
	const stateLabel = { active: 'Active', resolved: 'Handled', dismissed: 'Not mine' };

	async function save(e: SubmitEvent) {
		e.preventDefault();
		if (!draft) return;
		saving = true;
		const found = await app.saveItem($state.snapshot(draft));
		saving = false;
		if (found.length) {
			await goto('/');
		} else {
			app.toast('Saved. Nothing you own is affected.');
		}
	}

	async function remove() {
		if (!original || !confirm(`Delete “${original.name}” from this device?`)) return;
		await app.removeItems([original.id]);
		app.toast('Deleted.');
		await goto('/items');
	}
</script>

<svelte:head><title>{original?.name ?? 'Item'} · Boughtsafe</title></svelte:head>

{#if !app.loaded}
	<p class="muted">Loading…</p>
{:else if !original || !draft}
	<PageHeader title="Item not found" back="/items" />
	<p class="muted">It may have been deleted.</p>
{:else}
	<PageHeader
		title={original.name}
		subtitle="Added {formatDate(original.addedAt)} by {original.source}"
		back="/items"
	/>
	<form class="stack" onsubmit={save}>
		<div class="card">
			<ItemForm bind:item={draft} showPantryFields={draft.list === 'pantry'} />
		</div>
		<div class="row">
			<button class="btn primary" disabled={saving}
				>{saving ? 'Checking…' : 'Save and check'}</button
			>
			<span class="grow"></span>
			<button type="button" class="btn ghost" onclick={remove}><Trash2 size={18} /> Delete</button>
		</div>
	</form>

	{#if history.length || ruled.length}
		<section class="stack history">
			<h2>Recall history</h2>
			{#each history as m (m.key)}
				<div class="panel entry">
					<div class="row spread wrap">
						<strong>{m.recall.hazard.label}</strong>
						<span class="chip {m.state === 'active' ? 'danger' : ''}">{stateLabel[m.state]}</span>
					</div>
					<p class="small muted">{m.recall.title}</p>
					<div class="row">
						<a class="small" href="/recall/{encodeURIComponent(m.recallId)}?item={original.id}"
							>Details</a
						>
						{#if m.state !== 'active'}
							<button class="btn ghost small" onclick={() => app.decide(m.key, 'active')}
								>Show again</button
							>
						{/if}
					</div>
				</div>
			{/each}
			{#each ruled as r (r.key)}
				<div class="panel entry quiet">
					<p class="small">
						<strong>Not affected.</strong>
						{#if r.reason === 'lot_not_listed'}
							A recall exists for this barcode, but your code <span class="mono"
								>{original.lot}</span
							> isn't listed.
						{:else}
							A recall for this barcode was issued long before you bought it.
						{/if}
					</p>
					<p class="tiny faint">{r.title}</p>
				</div>
			{/each}
		</section>
	{/if}
{/if}

<style>
	.history {
		margin-top: 2rem;
		--gap: 0.6rem;
	}
	.entry {
		padding: 0.85rem 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}
	.quiet {
		background: var(--accent-soft);
		border-color: transparent;
	}
</style>
