<script lang="ts">
	import { Camera } from '@lucide/svelte';
	import { extractCode, recognize } from '$lib/ocr';
	import type { Item } from '$lib/types';

	let {
		item = $bindable(),
		showList = true,
		showPantryFields = false
	}: { item: Item; showList?: boolean; showPantryFields?: boolean } = $props();

	let reading = $state(false);
	let lotFile: HTMLInputElement | undefined = $state();

	async function readLot(e: Event) {
		const file = (e.currentTarget as HTMLInputElement).files?.[0];
		if (!file) return;
		reading = true;
		try {
			const code = extractCode(await recognize(file));
			if (code) item.lot = code;
		} finally {
			reading = false;
			if (lotFile) lotFile.value = '';
		}
	}
</script>

<div class="form stack">
	<label class="field">
		Product name
		<input bind:value={item.name} required autocomplete="off" placeholder="e.g. Raw cheddar 8 oz" />
	</label>
	<div class="two">
		<label class="field">
			Brand
			<input bind:value={item.brand} autocomplete="off" placeholder="Optional" />
		</label>
		<label class="field">
			Barcode (UPC / EAN)
			<input bind:value={item.code} inputmode="numeric" autocomplete="off" placeholder="Optional" />
		</label>
	</div>
	<label class="field">
		<span>Lot or best-by code <span class="hint">· makes matches exact</span></span>
		<div class="row">
			<input
				class="grow"
				bind:value={item.lot}
				autocomplete="off"
				placeholder="e.g. LOT 3B1 274 or BEST BY JUL 22 27"
			/>
			<button
				type="button"
				class="btn"
				onclick={() => lotFile?.click()}
				disabled={reading}
				title="Read the code from a photo"
			>
				<Camera size={18} />
				<span class="visually-hidden">Read the code from a photo</span>
				{reading ? 'Reading…' : ''}
			</button>
			<input
				bind:this={lotFile}
				type="file"
				accept="image/*"
				capture="environment"
				hidden
				onchange={readLot}
			/>
		</div>
	</label>
	<div class="two">
		<label class="field">
			{showPantryFields ? 'Received on' : 'Bought on'}
			<input type="date" bind:value={item.purchasedAt} required />
		</label>
		<label class="field">
			{showPantryFields ? 'Quantity' : 'Store'}
			{#if showPantryFields}
				<input type="number" min="1" bind:value={item.quantity} />
			{:else}
				<input bind:value={item.store} autocomplete="off" placeholder="Optional" />
			{/if}
		</label>
	</div>
	{#if showPantryFields}
		<label class="field">
			Donor
			<input bind:value={item.donor} autocomplete="off" placeholder="Optional" />
		</label>
	{/if}
	{#if showList}
		<fieldset class="list">
			<legend class="small muted">Keep this in</legend>
			<label><input type="radio" bind:group={item.list} value="home" /> My kitchen</label>
			<label><input type="radio" bind:group={item.list} value="pantry" /> Pantry stock</label>
		</fieldset>
	{/if}
</div>

<style>
	.two {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
	}
	@media (max-width: 420px) {
		.two {
			grid-template-columns: 1fr;
		}
	}
	.list {
		border: 0;
		padding: 0;
		margin: 0;
		display: flex;
		gap: 1.25rem;
		flex-wrap: wrap;
	}
	.list legend {
		margin-bottom: 0.4rem;
		font-weight: 600;
	}
	.list label {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
	}
	.list input {
		width: auto;
		min-height: auto;
		accent-color: var(--accent);
	}
</style>
