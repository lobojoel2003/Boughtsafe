<script lang="ts">
	import { Camera, LockKeyhole } from '@lucide/svelte';
	import { goto } from '$app/navigation';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { newId } from '$lib/db';
	import { today } from '$lib/format';
	import { recognize } from '$lib/ocr';
	import { parseReceipt, type ReceiptLine } from '$lib/receipt';
	import { app } from '$lib/state.svelte';
	import type { Item } from '$lib/types';

	type Row = ReceiptLine & { keep: boolean };

	let input: HTMLInputElement | undefined = $state();
	let preview = $state<string | null>(null);
	let progress = $state(0);
	let phase = $state<'pick' | 'reading' | 'review'>('pick');
	let rows = $state<Row[]>([]);
	let store = $state('');
	let date = $state(today());
	let rawText = $state('');
	let saving = $state(false);

	async function pick(e: Event) {
		const file = (e.currentTarget as HTMLInputElement).files?.[0];
		if (!file) return;
		preview = URL.createObjectURL(file);
		phase = 'reading';
		progress = 0;
		try {
			rawText = await recognize(file, (p) => (progress = p));
			useText(rawText);
		} catch (err) {
			app.toast(`Couldn't read that photo: ${(err as Error).message}`, 'danger');
			phase = 'pick';
		}
	}

	function useText(text: string) {
		const parsed = parseReceipt(text);
		rows = parsed.lines.map((l) => ({ ...l, keep: true }));
		store = parsed.store ?? '';
		date = parsed.date ?? today();
		phase = 'review';
	}

	const kept = $derived(rows.filter((r) => r.keep && r.name.trim()));

	async function save() {
		saving = true;
		const now = new Date().toISOString();
		const items: Item[] = kept.map((r) => ({
			id: newId(),
			list: 'home',
			name: r.name.trim(),
			code: r.code,
			lenient: r.code ? true : undefined,
			store: store || undefined,
			purchasedAt: date,
			addedAt: now,
			source: 'receipt'
		}));
		const found = await app.addItems(items);
		saving = false;
		if (found.length) return goto('/');
		app.toast(`Added ${items.length} items. None are on a recall.`);
		await goto('/items');
	}
</script>

<svelte:head><title>Receipt · Boughtsafe</title></svelte:head>

<PageHeader title="Photograph a receipt" back="/add" />

{#if phase === 'pick'}
	<div class="card stack pickcard">
		<p>
			Lay the receipt flat in good light and fill the frame. Long receipts work best in two photos.
		</p>
		<button class="btn primary lg" onclick={() => input?.click()}>
			<Camera size={20} /> Take or choose a photo
		</button>
		<input
			bind:this={input}
			type="file"
			accept="image/*"
			capture="environment"
			hidden
			onchange={pick}
		/>
		<p class="small muted row">
			<LockKeyhole size={15} /> The photo is read on this device and never uploaded.
		</p>
		<details class="small">
			<summary>Paste receipt text instead</summary>
			<textarea rows="6" bind:value={rawText} placeholder="Paste text from an e-receipt"></textarea>
			<button class="btn" onclick={() => useText(rawText)} disabled={!rawText.trim()}
				>Read text</button
			>
		</details>
	</div>
{:else if phase === 'reading'}
	<div class="card stack reading">
		{#if preview}<img src={preview} alt="Your receipt" />{/if}
		<p>Reading your receipt… {Math.round(progress * 100)}%</p>
		<progress max="1" value={progress}></progress>
		<p class="small muted">The first time takes a little longer while the reader downloads.</p>
	</div>
{:else}
	<div class="stack">
		<div class="card two">
			<label class="field">Store <input bind:value={store} placeholder="Store name" /></label>
			<label class="field">Date <input type="date" bind:value={date} /></label>
		</div>
		{#if rows.length}
			<div class="panel lines">
				{#each rows as row, i (i)}
					<label class="line">
						<input type="checkbox" bind:checked={row.keep} aria-label="Keep line {i + 1}" />
						<input class="name" bind:value={row.name} aria-label="Product name" />
						{#if row.price !== undefined}<span class="small faint">${row.price.toFixed(2)}</span
							>{/if}
					</label>
				{/each}
			</div>
			<p class="small muted">
				Untick anything that isn't a product. Fix names that came out garbled.
			</p>
		{:else}
			<p class="card muted">No product lines found. Try a sharper photo, or paste the text.</p>
		{/if}
		<div class="row">
			<button class="btn primary lg grow" onclick={save} disabled={saving || !kept.length}>
				{saving ? 'Checking…' : `Add ${kept.length} item${kept.length === 1 ? '' : 's'}`}
			</button>
			<button class="btn lg" onclick={() => (phase = 'pick')}>Retake</button>
		</div>
	</div>
{/if}

<style>
	.pickcard textarea {
		margin: 0.5rem 0;
	}
	.reading img {
		max-height: 40vh;
		object-fit: contain;
		border-radius: var(--radius-sm);
	}
	progress {
		width: 100%;
		accent-color: var(--accent);
	}
	.two {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
	}
	.lines {
		overflow: hidden;
	}
	.line {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.4rem 0.75rem;
		border-top: 1px solid var(--line);
	}
	.line:first-child {
		border-top: 0;
	}
	.line .name {
		border-color: transparent;
		background: transparent;
	}
	.line .name:focus {
		border-color: var(--accent);
	}
</style>
