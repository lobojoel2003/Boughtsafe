<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import ItemForm from '$lib/components/ItemForm.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Scanner from '$lib/components/Scanner.svelte';
	import { api } from '$lib/api';
	import { newId } from '$lib/db';
	import { today } from '$lib/format';
	import { prettyCode } from '$lib/gtin';
	import type { ScanResult } from '$lib/scanner';
	import { app } from '$lib/state.svelte';
	import type { Item } from '$lib/types';

	const list = page.url.searchParams.get('list') === 'pantry' ? 'pantry' : 'home';
	let draft = $state<Item | null>(null);
	let looking = $state(false);
	let lookedUp = $state<'found' | 'missing' | null>(null);
	let saving = $state(false);

	async function onscan(r: ScanResult) {
		draft = {
			id: newId(),
			list,
			name: '',
			code: r.code,
			codeFormat: r.format,
			lot: r.lot ?? (r.expiry ? `EXP ${r.expiry}` : undefined),
			purchasedAt: today(),
			addedAt: new Date().toISOString(),
			source: 'scan',
			quantity: list === 'pantry' ? 1 : undefined
		};
		looking = true;
		try {
			const p = await api.product(r.code, r.format);
			if (draft && p.found) {
				draft.name = [p.name, p.quantity].filter(Boolean).join(' ');
				draft.brand = p.brand ?? undefined;
				draft.imageUrl = p.image_url ?? undefined;
				lookedUp = 'found';
			} else lookedUp = 'missing';
		} catch {
			lookedUp = 'missing';
		} finally {
			looking = false;
		}
		if (draft && !draft.name) draft.name = `Barcode ${prettyCode(r.code, r.format)}`;
	}

	async function save(e: SubmitEvent) {
		e.preventDefault();
		if (!draft) return;
		saving = true;
		const found = await app.addItems([$state.snapshot(draft)]);
		saving = false;
		if (found.length) return goto('/');
		app.toast(`Saved “${draft.name}”. Not on any recall.`);
		draft = null;
		lookedUp = null;
	}
</script>

<svelte:head><title>Scan · Boughtsafe</title></svelte:head>

<PageHeader title="Scan a barcode" back={list === 'pantry' ? '/pantry' : '/add'} />

{#if !draft}
	<Scanner
		{onscan}
		onmanual={() => goto(`/add/manual${list === 'pantry' ? '?list=pantry' : ''}`)}
	/>
	<p class="small muted tip">
		Tip: after scanning, add the <strong>lot code</strong> or <strong>best-by date</strong> printed near
		the barcode. With it, Boughtsafe can tell you for certain whether your package is affected.
	</p>
{:else}
	<form class="stack" onsubmit={save}>
		<div class="card stack">
			<div class="row">
				{#if draft.imageUrl}<img src={draft.imageUrl} alt="" class="thumb" />{/if}
				<div class="grow">
					<p class="mono">{prettyCode(draft.code, draft.codeFormat)}</p>
					<p class="small muted">
						{looking
							? 'Looking up the product…'
							: lookedUp === 'found'
								? 'Found on Open Food Facts. Check the name.'
								: 'Not in Open Food Facts. Type the product name.'}
					</p>
				</div>
			</div>
			<ItemForm bind:item={draft} showPantryFields={draft.list === 'pantry'} />
		</div>
		<div class="row">
			<button
				class="btn primary lg grow"
				disabled={saving || looking || !draft.name.trim()}
				data-testid="save-scan"
			>
				{saving ? 'Checking…' : 'Save and check'}
			</button>
			<button type="button" class="btn lg" onclick={() => (draft = null)}>Rescan</button>
		</div>
	</form>
{/if}

<style>
	.tip {
		margin-top: 1rem;
	}
	.thumb {
		width: 56px;
		height: 56px;
		object-fit: contain;
		border-radius: 10px;
		background: #fff;
		border: 1px solid var(--line);
	}
</style>
