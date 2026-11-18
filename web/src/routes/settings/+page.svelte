<script lang="ts">
	import { Bell, BellOff, Download, Server, Trash2, Upload } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { api, DEFAULT_API_BASE } from '$lib/api';
	import { exportBackup, kvGet, kvSet, wipeEverything } from '$lib/db';
	import { download, plural, relativeTime, today } from '$lib/format';
	import {
		alertsEnabled,
		disableAlerts,
		enableAlerts,
		pushSupported,
		sendTestAlert
	} from '$lib/push';
	import { app } from '$lib/state.svelte';
	import type { Meta } from '$lib/types';

	let meta = $state<Meta | null>(null);
	let metaError = $state<string | null>(null);
	let alerts = $state(false);
	let busy = $state(false);
	let apiBaseInput = $state('');

	const version = __APP_VERSION__;
	const build = __BUILD_NUMBER__;
	const sha = __GIT_SHA__;
	const builtOn = __BUILD_DATE__;

	async function loadMeta() {
		metaError = null;
		try {
			meta = await api.meta();
		} catch (e) {
			meta = null;
			metaError = (e as Error).message;
		}
	}

	onMount(async () => {
		alerts = await alertsEnabled();
		apiBaseInput = await kvGet('apiBase', '');
		await loadMeta();
	});

	async function toggleAlerts() {
		busy = true;
		try {
			if (alerts) {
				await disableAlerts();
				alerts = false;
				app.toast('Alerts are off.');
				return;
			}
			const result = await enableAlerts();
			alerts = result === 'enabled';
			const messages = {
				enabled: "Alerts are on. You'll hear from us only when something you own is recalled.",
				denied: 'Notifications are blocked for this site in your browser settings.',
				unsupported:
					"This browser can't receive push alerts. On iPhone, add Boughtsafe to your Home Screen first.",
				'server-disabled': "This Boughtsafe server hasn't enabled push alerts.",
				error: "Couldn't turn on alerts. Try again."
			};
			app.toast(messages[result], result === 'enabled' ? 'ok' : 'danger');
		} finally {
			busy = false;
		}
	}

	async function test() {
		const sent = await sendTestAlert().catch(() => false);
		app.toast(sent ? 'Test alert sent.' : "Couldn't send a test alert.", sent ? 'ok' : 'danger');
	}

	async function saveServer(e: SubmitEvent) {
		e.preventDefault();
		await kvSet('apiBase', apiBaseInput.trim());
		await loadMeta();
		if (meta) app.toast(`Connected to Boughtsafe ${meta.version}.`);
	}

	async function backup() {
		download(
			`boughtsafe-backup-${today()}.json`,
			JSON.stringify(await exportBackup(), null, 1),
			'application/json'
		);
	}

	async function wipe() {
		if (!confirm('Delete every item, match and setting from this device? This cannot be undone.'))
			return;
		await disableAlerts().catch(() => {});
		await wipeEverything();
		await app.reload();
		alerts = false;
		app.toast('Everything was deleted from this device.');
	}

	const handled = $derived(app.matches.filter((m) => m.state !== 'active'));
</script>

<svelte:head><title>Settings · Boughtsafe</title></svelte:head>

<PageHeader title="Settings" />

<div class="stack">
	<section class="card stack">
		<div class="row spread">
			<div>
				<h2>Recall alerts</h2>
				<p class="small muted">A notification only when a recall matches something you own.</p>
			</div>
			<button
				class="btn {alerts ? '' : 'primary'}"
				onclick={toggleAlerts}
				disabled={busy || !pushSupported()}
			>
				{#if alerts}<BellOff size={18} /> Turn off{:else}<Bell size={18} /> Turn on{/if}
			</button>
		</div>
		{#if alerts}
			<button class="btn ghost small left" onclick={test}>Send a test alert</button>
		{/if}
		<p class="tiny faint">
			Your device registers short, anonymous codes that each stand for tens of thousands of possible
			products, never the barcodes themselves. When a new recall shares a code, your device checks
			its own list and stays silent unless something really matches.
		</p>
	</section>

	<section class="card stack">
		<h2>Your data</h2>
		<p class="small muted">
			{plural(app.items.length, 'item')} and {plural(
				app.matches.length,
				'recall match',
				'recall matches'
			)}, stored only in this browser.
		</p>
		<div class="row wrap">
			<button class="btn" onclick={backup}><Download size={18} /> Export backup</button>
			<a class="btn" href="/add/import"><Upload size={18} /> Restore backup</a>
			<button class="btn ghost danger-text" onclick={wipe}
				><Trash2 size={18} /> Delete everything</button
			>
		</div>
		{#if handled.length}
			<details class="small">
				<summary>{plural(handled.length, 'dismissed or handled recall')}</summary>
				<ul class="handled">
					{#each handled as m (m.key)}
						<li class="row spread">
							<span>
								{app.itemsById.get(m.itemId)?.name ?? 'Deleted item'}
								<span class="faint"
									>· {m.recall.hazard.label} · {m.state === 'resolved'
										? 'handled'
										: 'not mine'}</span
								>
							</span>
							<button class="btn ghost small" onclick={() => app.decide(m.key, 'active')}
								>Undo</button
							>
						</li>
					{/each}
				</ul>
			</details>
		{/if}
	</section>

	<section class="card stack">
		<h2><Server size={18} /> Recall server</h2>
		{#if meta}
			<p class="small">
				Connected to Boughtsafe <span class="mono">{meta.version}</span> (build {meta.build}).
			</p>
			<table class="sources small">
				<tbody>
					{#each meta.sources as s (s.source)}
						<tr>
							<td><strong>{s.label}</strong></td>
							<td>{s.count.toLocaleString()} recalls</td>
							<td class="faint">
								{s.last_sync ? `synced ${relativeTime(s.last_sync)}` : 'not synced yet'}
								{#if s.last_ok === false}<span class="chip warn">last sync failed</span>{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{:else if metaError}
			<p class="small chip danger">{metaError}</p>
		{:else}
			<p class="small muted">Connecting…</p>
		{/if}
		<form class="row" onsubmit={saveServer}>
			<label class="grow field">
				Server address <span class="hint">· leave empty for {DEFAULT_API_BASE}</span>
				<input bind:value={apiBaseInput} placeholder={DEFAULT_API_BASE} inputmode="url" />
			</label>
			<button class="btn self-end">Save</button>
		</form>
	</section>

	<section class="card stack about">
		<h2>About</h2>
		<p class="small">
			Boughtsafe <span class="mono">{version}</span> · build <span class="mono">{build}</span> ·
			<span class="mono">{sha}</span> · {builtOn}
		</p>
		<p class="small muted">
			Recall data from the openFDA food enforcement API, USDA FSIS and the CPSC recalls API. Product
			names from Open Food Facts. Recall data can be incomplete or late; always follow the official
			notice.
		</p>
		<p class="small">
			<a href="https://github.com/lobojoel2003/Boughtsafe" target="_blank" rel="noopener"
				>Source code</a
			>
			·
			<a
				href="https://github.com/lobojoel2003/Boughtsafe/blob/main/LICENSE"
				target="_blank"
				rel="noopener">AGPL-3.0</a
			>
			·
			<a href="https://github.com/lobojoel2003/Boughtsafe/issues" target="_blank" rel="noopener"
				>Report a problem</a
			>
		</p>
	</section>
</div>

<style>
	h2 {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}
	.left {
		align-self: flex-start;
	}
	.danger-text {
		color: var(--danger);
	}
	.self-end {
		align-self: flex-end;
	}
	.sources {
		border-collapse: collapse;
		width: 100%;
	}
	.sources td {
		padding: 0.35rem 0.5rem 0.35rem 0;
		border-bottom: 1px solid var(--line);
	}
	.handled {
		list-style: none;
		padding: 0;
		margin: 0.5rem 0 0;
	}
	.handled li {
		padding: 0.25rem 0;
	}
</style>
