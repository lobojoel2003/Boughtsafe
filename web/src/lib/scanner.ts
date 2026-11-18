/**
 * Barcode scanning: the browser's BarcodeDetector where available (Chrome,
 * Android, Edge), ZXing everywhere else (Safari, Firefox).
 */
import { parseGs1 } from './gs1';

export interface ScanResult {
	code: string;
	format: string;
	lot?: string;
	expiry?: string;
	raw: string;
}

const NATIVE_FORMATS = ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128', 'data_matrix', 'qr_code'];

const ZXING_FORMATS: Record<string, string> = {
	EAN_13: 'ean_13',
	EAN_8: 'ean_8',
	UPC_A: 'upc_a',
	UPC_E: 'upc_e',
	CODE_128: 'code_128',
	DATA_MATRIX: 'data_matrix',
	QR_CODE: 'qr_code',
	RSS_14: 'gs1_databar',
	RSS_EXPANDED: 'gs1_databar'
};

/** Turn whatever a scanner returned into a barcode plus any GS1 lot/expiry. */
export function interpret(raw: string, format: string): ScanResult | null {
	const value = raw.trim();
	if (/^\d{8,14}$/.test(value)) return { code: value, format, raw: value };
	const gs1 = parseGs1(value);
	if (gs1?.gtin) return { code: gs1.gtin, format, lot: gs1.lot, expiry: gs1.expiry, raw: value };
	return null;
}

async function nativeDetector(): Promise<BarcodeDetector | null> {
	if (typeof BarcodeDetector === 'undefined') return null;
	try {
		const supported = await BarcodeDetector.getSupportedFormats();
		const formats = NATIVE_FORMATS.filter((f) => supported.includes(f));
		return formats.length ? new BarcodeDetector({ formats }) : null;
	} catch {
		return null;
	}
}

export interface ScanSession {
	stop(): void;
	torch(on: boolean): Promise<boolean>;
	engine: 'native' | 'zxing';
}

/** Start the camera in ``video`` and call ``onResult`` for each barcode seen. */
export async function startScanning(
	video: HTMLVideoElement,
	onResult: (r: ScanResult) => void
): Promise<ScanSession> {
	const stream = await navigator.mediaDevices.getUserMedia({
		video: {
			facingMode: { ideal: 'environment' },
			width: { ideal: 1920 },
			height: { ideal: 1080 }
		},
		audio: false
	});
	video.srcObject = stream;
	video.setAttribute('playsinline', 'true');
	await video.play();
	const track = stream.getVideoTracks()[0];
	let stopped = false;
	const stopStream = () => stream.getTracks().forEach((t) => t.stop());
	const torch = async (on: boolean) => {
		try {
			await track.applyConstraints({ advanced: [{ torch: on } as MediaTrackConstraintSet] });
			return true;
		} catch {
			return false;
		}
	};

	const native = await nativeDetector();
	if (native) {
		const tick = async () => {
			if (stopped) return;
			try {
				for (const b of await native.detect(video)) {
					const r = interpret(b.rawValue, b.format);
					if (r) onResult(r);
				}
			} catch {
				/* frame not ready */
			}
			setTimeout(tick, 120);
		};
		void tick();
		return {
			engine: 'native',
			torch,
			stop: () => {
				stopped = true;
				stopStream();
			}
		};
	}

	const { BrowserMultiFormatReader } = await import('@zxing/browser');
	const { BarcodeFormat, DecodeHintType } = await import('@zxing/library');
	const hints = new Map();
	hints.set(DecodeHintType.POSSIBLE_FORMATS, [
		BarcodeFormat.EAN_13,
		BarcodeFormat.EAN_8,
		BarcodeFormat.UPC_A,
		BarcodeFormat.UPC_E,
		BarcodeFormat.CODE_128,
		BarcodeFormat.DATA_MATRIX,
		BarcodeFormat.QR_CODE
	]);
	const reader = new BrowserMultiFormatReader(hints);
	const controls = await reader.decodeFromVideoElement(video, (result) => {
		if (!result || stopped) return;
		const fmt = ZXING_FORMATS[BarcodeFormat[result.getBarcodeFormat()]] ?? 'unknown';
		const r = interpret(result.getText(), fmt);
		if (r) onResult(r);
	});
	return {
		engine: 'zxing',
		torch,
		stop: () => {
			stopped = true;
			controls.stop();
			stopStream();
		}
	};
}

/** Read a barcode from a photo (desktop, or when camera access is refused). */
export async function scanImage(file: Blob): Promise<ScanResult | null> {
	const native = await nativeDetector();
	if (native) {
		const bitmap = await createImageBitmap(file);
		try {
			for (const b of await native.detect(bitmap)) {
				const r = interpret(b.rawValue, b.format);
				if (r) return r;
			}
		} finally {
			bitmap.close();
		}
	}
	const { BrowserMultiFormatReader } = await import('@zxing/browser');
	const { BarcodeFormat } = await import('@zxing/library');
	const url = URL.createObjectURL(file);
	try {
		const result = await new BrowserMultiFormatReader().decodeFromImageUrl(url);
		const fmt = ZXING_FORMATS[BarcodeFormat[result.getBarcodeFormat()]] ?? 'unknown';
		return interpret(result.getText(), fmt);
	} catch {
		return null;
	} finally {
		URL.revokeObjectURL(url);
	}
}
