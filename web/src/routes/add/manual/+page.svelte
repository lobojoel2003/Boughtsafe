<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import ItemForm from '$lib/components/ItemForm.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { newId } from '$lib/db';
	import { today } from '$lib/format';
	import { app } from '$lib/state.svelte';
	import type { Item } from '$lib/types';

	const list = page.url.searchParams.get('list') === 'pantry' ? 'pantry' : 'home';
	const blank = (): Item => ({
		id: newId(),
		list,
		name: '',
		purchasedAt: today(),
		addedAt: new Date().toISOString(),
		source: 'manual',
		quantity: list === 'pantry' ? 1 : undefined
	});
	let item = $state<Item>(blank());
	let saving = $state(false);

	async function save(e: SubmitEvent) {
		e.preventDefault();
		saving = true;
		const found = await app.addItems([
			{ ...$state.snapshot(item), addedAt: new Date().toISOString() }
		]);
		saving = false;
		if (found.length) return goto('/');
		app.toast(`Saved “${item.name}”. Not on any recall.`);
		item = blank();
	}
</script>

<svelte:head><title>Type it in · Boughtsafe</title></svelte:head>

<PageHeader title="Type it in" back="/add" />
<form class="stack" onsubmit={save}>
	<div class="card"><ItemForm bind:item showPantryFields={item.list === 'pantry'} /></div>
	<button class="btn primary lg" disabled={saving || !item.name.trim()} data-testid="save-item">
		{saving ? 'Checking…' : 'Save and check'}
	</button>
</form>
