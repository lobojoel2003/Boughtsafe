<script lang="ts">
	import { FileUp } from '@lucide/svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { parseCsv } from '$lib/csv';
	import { importBackup, isBackup } from '$lib/db';
	import { FIELD_LABELS, guessMapping, rowsToItems, type Field, type Mapping } from '$lib/imports';
	import { app } from '$lib/state.svelte';
	import type { ListKind } from '$lib/types';

	let input: HTMLInputElement | undefined = $state();
	let header = $state<string[]>([]);
	let rows = $state<string[][]>([]);
	let mapping = $state<Mapping>({});
	let list = $state<ListKind>(page.url.searchParams.get('list') === 'pantry' ? 'pantry' : 'home');
	let fileName = $state('');
	let saving = $state(false);
	const fields = Object.keys(FIELD_LABELS) as Field[];

	async function pick(e: Event) {
		const file = (e.currentTarget as HTMLInputElement).files?.[0];
		if (!file) return;
		fileName = file.name;
		const text = await file.text();
		if (file.name.endsWith('.json') || text.trimStart().startsWith('{')) {
			try {
				const data = JSON.parse(text);
				if (!isBackup(data)) throw new Error('not a Boughtsafe backup');
				const n = await importBackup(data);
				await app.reload();
				await app.check();
				app.toast(`Restored ${n} items from backup.`);
				return goto('/');
			} catch (err) {
				app.toast(
					`That JSON file isn't a Boughtsafe backup (${(err as Error).message}).`,
					'danger'
				);
				return;
			}
		}
		const parsed = parseCsv(text);
		header = parsed[0] ?? [];
		rows = parsed.slice(1);
		mapping = guessMapping(header);
	}

	const preview = $derived(rowsToItems(rows.slice(0, 5), mapping, { list }));
	const total = $derived(rowsToItems(rows, mapping, { list }).length);

	async function doImport() {
		saving = true;
		const items = rowsToItems(rows, mapping, { list });
		const found = await app.addItems(items);
		saving = false;
		if (found.length) return goto('/');
		app.toast(`Imported ${items.length} items. None are on a recall.`);
		await goto(list === 'pantry' ? '/pantry' : '/items');
	}
</script>

<svelte:head><title>Import · Boughtsafe</title></svelte:head>

<PageHeader title="Import a file" back={list === 'pantry' ? '/pantry' : '/add'} />

<div class="stack">
	<div class="card stack">
		<p>
			Most stores let you download purchase history from your loyalty account or order history as a
			CSV file. Pantries can import inventory spreadsheets the same way.
		</p>
		<button class="btn primary lg" onclick={() => input?.click()}
			><FileUp size={20} /> Choose a CSV or backup file</button
		>
		<input
			bind:this={input}
			type="file"
			accept=".csv,.tsv,.txt,.json,text/csv,application/json"
			hidden
			onchange={pick}
		/>
		{#if fileName}<p class="small muted">{fileName}: {rows.length} rows</p>{/if}
	</div>

	{#if header.length}
		<div class="card stack">
			<h2>Match the columns</h2>
			<div class="map">
				{#each fields as f (f)}
					<label class="field">
						{FIELD_LABELS[f]}
						<select
							value={mapping[f] ?? ''}
							onchange={(e) => {
								const v = (e.currentTarget as HTMLSelectElement).value;
								mapping = { ...mapping, [f]: v === '' ? undefined : Number(v) };
							}}
						>
							<option value="">Not in file</option>
							{#each header as h, i (i)}<option value={i}>{h || `Column ${i + 1}`}</option>{/each}
						</select>
					</label>
				{/each}
			</div>
			<fieldset class="row">
				<legend class="small muted">Add to</legend>
				<label class="row"><input type="radio" bind:group={list} value="home" /> My kitchen</label>
				<label class="row"
					><input type="radio" bind:group={list} value="pantry" /> Pantry stock</label
				>
			</fieldset>
		</div>

		<div class="card stack">
			<h2>Preview</h2>
			{#if preview.length}
				<table>
					<thead><tr><th>Name</th><th>Barcode</th><th>Lot</th><th>Date</th></tr></thead>
					<tbody>
						{#each preview as p (p.id)}
							<tr
								><td>{p.name}</td><td class="mono">{p.code ?? ''}</td><td class="mono"
									>{p.lot ?? ''}</td
								><td>{p.purchasedAt}</td></tr
							>
						{/each}
					</tbody>
				</table>
			{:else}
				<p class="muted">Pick at least a product name or barcode column.</p>
			{/if}
			<button class="btn primary lg" onclick={doImport} disabled={saving || !total}>
				{saving ? 'Checking…' : `Import ${total} item${total === 1 ? '' : 's'}`}
			</button>
		</div>
	{/if}
</div>

<style>
	.map {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(12rem, 1fr));
		gap: 0.75rem;
	}
	fieldset {
		border: 0;
		padding: 0;
		margin: 0;
		--gap: 1.25rem;
	}
	fieldset input {
		width: auto;
		min-height: auto;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.88rem;
	}
	th,
	td {
		text-align: left;
		padding: 0.4rem 0.5rem;
		border-bottom: 1px solid var(--line);
		vertical-align: top;
	}
	th {
		color: var(--faint);
		font-weight: 600;
	}
</style>
