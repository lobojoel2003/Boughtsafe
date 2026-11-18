<script lang="ts">
	let { size = 32, wordmark = false }: { size?: number; wordmark?: boolean } = $props();
</script>

<span class="logo" style:--size="{size}px">
	<svg viewBox="0 0 48 48" width={size} height={size} aria-hidden="true">
		<rect x="2" y="2" width="44" height="44" rx="13" fill="var(--accent)" />
		<path
			d="M13 18.5h22l-1.6 17.2a3 3 0 0 1-3 2.8H17.6a3 3 0 0 1-3-2.8L13 18.5z"
			fill="var(--accent-ink)"
		/>
		<path
			d="M19 18.5v-2a5 5 0 0 1 10 0v2"
			fill="none"
			stroke="var(--accent-ink)"
			stroke-width="2.6"
			stroke-linecap="round"
		/>
		<path
			d="M19.2 28.2l3.4 3.4 6.4-6.6"
			fill="none"
			stroke="var(--accent)"
			stroke-width="2.8"
			stroke-linecap="round"
			stroke-linejoin="round"
		/>
	</svg>
	{#if wordmark}<span class="word">Boughtsafe</span>{/if}
</span>

<style>
	.logo {
		display: inline-flex;
		align-items: center;
		gap: 0.55rem;
	}
	.word {
		font-weight: 750;
		letter-spacing: -0.02em;
		font-size: calc(var(--size) * 0.6);
		color: var(--text);
	}
</style>
