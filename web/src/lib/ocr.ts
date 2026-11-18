/**
 * On-device text recognition with Tesseract.js. Photos never leave the device;
 * only the recognition model is downloaded (once, then cached by the browser).
 */
import type { Worker } from 'tesseract.js';

let worker: Promise<Worker> | null = null;

async function getWorker(onProgress?: (p: number) => void): Promise<Worker> {
	worker ??= (async () => {
		const { createWorker } = await import('tesseract.js');
		return createWorker('eng', 1, {
			logger: (m: { status: string; progress: number }) => {
				if (m.status === 'recognizing text') onProgress?.(m.progress);
			}
		});
	})();
	return worker;
}

/** Downscale and grayscale large photos: faster and usually more accurate. */
async function prepare(file: Blob): Promise<Blob | HTMLCanvasElement> {
	if (typeof createImageBitmap === 'undefined' || typeof document === 'undefined') return file;
	const bitmap = await createImageBitmap(file);
	const scale = Math.min(1, 2000 / Math.max(bitmap.width, bitmap.height));
	const canvas = document.createElement('canvas');
	canvas.width = Math.round(bitmap.width * scale);
	canvas.height = Math.round(bitmap.height * scale);
	const ctx = canvas.getContext('2d');
	if (!ctx) return file;
	ctx.filter = 'grayscale(1) contrast(1.25)';
	ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
	bitmap.close();
	return canvas;
}

export async function recognize(file: Blob, onProgress?: (p: number) => void): Promise<string> {
	const w = await getWorker(onProgress);
	const { data } = await w.recognize(await prepare(file));
	return data.text;
}

/** Pick the most likely lot / best-by code out of a photo of a package. */
export function extractCode(text: string): string | undefined {
	const lines = text
		.split(/\r?\n/)
		.map((l) => l.trim())
		.filter(Boolean);
	const labelled = lines.find((l) => /\b(lot|batch|best\s*by|use\s*by|exp|bb)\b/i.test(l));
	if (labelled) {
		return (
			labelled.replace(/^.*?\b(lot|batch|best\s*by|use\s*by|exp\.?|bb)\b[\s:#.-]*/i, '').trim() ||
			labelled
		);
	}
	const tokens = text.match(/[A-Z0-9][A-Z0-9 /.-]{3,20}[A-Z0-9]/gi) ?? [];
	return tokens.filter((t) => /\d/.test(t)).sort((a, b) => b.length - a.length)[0];
}

export async function terminateOcr(): Promise<void> {
	if (worker) await (await worker).terminate();
	worker = null;
}
