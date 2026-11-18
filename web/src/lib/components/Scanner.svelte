<script lang="ts">
	import { Flashlight, ImageUp, Keyboard } from '@lucide/svelte';
	import { onDestroy, onMount } from 'svelte';
	import { scanImage, startScanning, type ScanResult, type ScanSession } from '$lib/scanner';

	let {
		onscan,
		continuous = false,
		onmanual
	}: { onscan: (r: ScanResult) => void; continuous?: boolean; onmanual?: () => void } = $props();

	let video: HTMLVideoElement | undefined = $state();
	let session: ScanSession | null = null;
	let status = $state<'starting' | 'live' | 'denied' | 'unavailable'>('starting');
	let torchOn = $state(false);
	let flash = $state(false);
	let photo: HTMLInputElement | undefined = $state();
	let lastCode = '';
	let lastAt = 0;

	function handle(r: ScanResult) {
		const now = Date.now();
		if (r.code === lastCode && now - lastAt < 2500) return;
		lastCode = r.code;
		lastAt = now;
		flash = true;
		setTimeout(() => (flash = false), 250);
		navigator.vibrate?.(40);
		if (!continuous) stop();
		onscan(r);
	}

	async function start() {
		if (!video) return;
		if (!navigator.mediaDevices?.getUserMedia) {
			status = 'unavailable';
			return;
		}
		try {
			session = await startScanning(video, handle);
			status = 'live';
		} catch (e) {
			status = (e as DOMException)?.name === 'NotAllowedError' ? 'denied' : 'unavailable';
		}
	}

	function stop() {
		session?.stop();
		session = null;
	}

	async function toggleTorch() {
		if (session && (await session.torch(!torchOn))) torchOn = !torchOn;
	}

	async function fromPhoto(e: Event) {
		const file = (e.currentTarget as HTMLInputElement).files?.[0];
		if (!file) return;
		const r = await scanImage(file);
		if (r) handle(r);
		else alert("Couldn't find a barcode in that photo. Try a closer, sharper shot.");
		if (photo) photo.value = '';
	}

	onMount(start);
	onDestroy(stop);
</script>

<div class="scanner" class:flash>
	<video bind:this={video} muted playsinline aria-label="Camera preview"></video>
	{#if status === 'live'}
		<div class="reticle" aria-hidden="true"><span></span></div>
		<p class="tip">Hold the barcode inside the frame</p>
	{:else}
		<div class="overlay">
			{#if status === 'starting'}
				<p>Starting camera…</p>
			{:else if status === 'denied'}
				<p><strong>Camera access is off.</strong></p>
				<p class="small">Allow camera access in your browser settings, or use a photo instead.</p>
			{:else}
				<p><strong>No camera available.</strong></p>
				<p class="small">Upload a photo of the barcode, or type the number.</p>
			{/if}
		</div>
	{/if}
</div>

<div class="row wrap tools">
	<button class="btn" type="button" onclick={() => photo?.click()}>
		<ImageUp size={18} /> Use a photo
	</button>
	<input bind:this={photo} type="file" accept="image/*" hidden onchange={fromPhoto} />
	{#if onmanual}
		<button class="btn" type="button" onclick={onmanual}><Keyboard size={18} /> Type it</button>
	{/if}
	{#if status === 'live'}
		<button class="btn ghost" type="button" onclick={toggleTorch} aria-pressed={torchOn}>
			<Flashlight size={18} /> Light
		</button>
	{/if}
</div>

<style>
	.scanner {
		position: relative;
		aspect-ratio: 3 / 4;
		max-height: 58vh;
		width: 100%;
		border-radius: var(--radius);
		overflow: hidden;
		background: #0b0f0d;
		transition: box-shadow 0.2s;
	}
	.scanner.flash {
		box-shadow: 0 0 0 4px var(--accent);
	}
	video {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}
	.reticle {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		pointer-events: none;
	}
	.reticle span {
		width: 74%;
		height: 30%;
		border-radius: 16px;
		box-shadow: 0 0 0 100vmax rgb(0 0 0 / 0.35);
		border: 2px solid rgb(255 255 255 / 0.9);
	}
	.tip {
		position: absolute;
		bottom: 1rem;
		left: 0;
		right: 0;
		text-align: center;
		color: #fff;
		font-size: 0.9rem;
		font-weight: 600;
		text-shadow: 0 1px 4px rgb(0 0 0 / 0.6);
	}
	.overlay {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.4rem;
		color: #e8ece9;
		padding: 1.5rem;
		text-align: center;
	}
	.tools {
		margin-top: 0.75rem;
		--gap: 0.5rem;
	}
</style>
