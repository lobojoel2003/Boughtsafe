<script lang="ts">
	import '../app.css';
	import { Boxes, House, List, Plus, Settings } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { dev } from '$app/environment';
	import { page } from '$app/state';
	import Logo from '$lib/components/Logo.svelte';
	import Toasts from '$lib/components/Toasts.svelte';
	import { isStale } from '$lib/check';
	import { app } from '$lib/state.svelte';

	let { children } = $props();

	const nav = [
		{ href: '/', label: 'Home', icon: House },
		{ href: '/items', label: 'Items', icon: List },
		{ href: '/add', label: 'Add', icon: Plus, primary: true },
		{ href: '/pantry', label: 'Pantry', icon: Boxes },
		{ href: '/settings', label: 'Settings', icon: Settings }
	];

	const active = (href: string) =>
		href === '/' ? page.url.pathname === '/' : page.url.pathname.startsWith(href);

	async function maybeCheck() {
		if (app.items.length && (await isStale())) await app.check({ quiet: true });
	}

	onMount(() => {
		void app.load().then(maybeCheck);
		if ('serviceWorker' in navigator) {
			navigator.serviceWorker
				.register('/service-worker.js', { type: dev ? 'module' : 'classic' })
				.catch(() => {});
			navigator.serviceWorker.addEventListener('message', (e) => {
				if (e.data?.type === 'matches-updated') void app.reload();
			});
		}
		const onVisible = () => document.visibilityState === 'visible' && void maybeCheck();
		document.addEventListener('visibilitychange', onVisible);
		return () => document.removeEventListener('visibilitychange', onVisible);
	});
</script>

<a class="skip" href="#main">Skip to content</a>

<header class="top no-print">
	<a href="/" class="brand" aria-label="Boughtsafe home"><Logo size={30} wordmark /></a>
	{#if app.loaded && app.items.length}
		{#if app.alerts.length}
			<a href="/" class="chip danger status" data-testid="status">
				{app.alerts.length} recall{app.alerts.length > 1 ? 's' : ''}
			</a>
		{:else}
			<span class="chip ok status" data-testid="status"><span class="dot"></span>All clear</span>
		{/if}
	{/if}
</header>

<main id="main">
	{@render children()}
</main>

<nav class="tabs no-print" aria-label="Main">
	{#each nav as n (n.href)}
		<a
			href={n.href}
			class="tab"
			class:primary={n.primary}
			aria-current={active(n.href) ? 'page' : undefined}
		>
			<span class="ico"
				><n.icon size={n.primary ? 24 : 21} strokeWidth={n.primary ? 2.4 : 2} /></span
			>
			<span class="lbl">{n.label}</span>
		</a>
	{/each}
</nav>

<Toasts />

<style>
	.skip {
		position: absolute;
		left: -999px;
		top: 0.5rem;
		background: var(--surface);
		padding: 0.5rem 0.8rem;
		border-radius: 8px;
		z-index: 100;
	}
	.skip:focus {
		left: 0.5rem;
	}
	.top {
		position: sticky;
		top: 0;
		z-index: 20;
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: calc(0.7rem + env(safe-area-inset-top)) max(1rem, env(safe-area-inset-right)) 0.7rem
			max(1rem, env(safe-area-inset-left));
		max-width: 44rem;
		margin: 0 auto;
		background: color-mix(in srgb, var(--bg) 88%, transparent);
		backdrop-filter: saturate(1.4) blur(12px);
	}
	.brand {
		text-decoration: none;
	}
	.status {
		text-decoration: none;
	}
	.dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: currentColor;
	}
	main {
		max-width: 44rem;
		margin: 0 auto;
		padding: 0 max(1rem, env(safe-area-inset-left)) calc(var(--nav-h) + 2.5rem)
			max(1rem, env(safe-area-inset-right));
	}
	.tabs {
		position: fixed;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 30;
		height: calc(var(--nav-h) + env(safe-area-inset-bottom));
		padding-bottom: env(safe-area-inset-bottom);
		display: grid;
		grid-template-columns: repeat(5, 1fr);
		align-items: center;
		background: color-mix(in srgb, var(--surface) 92%, transparent);
		backdrop-filter: saturate(1.4) blur(14px);
		border-top: 1px solid var(--line);
	}
	.tab {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 2px;
		color: var(--faint);
		text-decoration: none;
		font-size: 0.72rem;
		font-weight: 600;
		padding: 0.35rem 0;
		-webkit-tap-highlight-color: transparent;
	}
	.tab[aria-current='page'] {
		color: var(--accent);
	}
	.tab.primary .ico {
		width: 46px;
		height: 46px;
		border-radius: 50%;
		display: grid;
		place-items: center;
		background: var(--accent);
		color: var(--accent-ink);
		box-shadow: var(--shadow);
		margin-top: -14px;
	}
	.tab.primary .lbl {
		color: var(--muted);
	}
	@media (min-width: 900px) {
		.tabs {
			max-width: 44rem;
			margin: 0 auto 1rem;
			border: 1px solid var(--line);
			border-radius: 22px;
			bottom: 0;
			box-shadow: var(--shadow);
		}
	}
</style>
