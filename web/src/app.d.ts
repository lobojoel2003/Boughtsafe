// See https://svelte.dev/docs/kit/types#app.d.ts
declare global {
	const __APP_VERSION__: string;
	const __BUILD_NUMBER__: string;
	const __GIT_SHA__: string;
	const __BUILD_DATE__: string;

	interface BarcodeDetectorOptions {
		formats?: string[];
	}
	interface DetectedBarcode {
		rawValue: string;
		format: string;
		boundingBox: DOMRectReadOnly;
	}
	// Shape Detection API (Chrome, Android, Edge). Safari/Firefox fall back to ZXing.
	class BarcodeDetector {
		constructor(options?: BarcodeDetectorOptions);
		static getSupportedFormats(): Promise<string[]>;
		detect(source: ImageBitmapSource): Promise<DetectedBarcode[]>;
	}

	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};
