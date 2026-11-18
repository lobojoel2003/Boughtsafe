# Changelog

All notable changes to Boughtsafe are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Every release is
tagged `vX.Y.Z`; each CI build also carries a build number (the GitHub Actions
run number), shown in the app under **Settings → About** and in `GET /v1/meta`.

## [Unreleased]

## [1.0.0] - 2026-11-18

The first public release.

### Added

- **Recall mirror.** A FastAPI service mirrors the openFDA food enforcement
  API, the USDA FSIS recall API and the CPSC recalls API into Postgres. It runs
  hourly incremental syncs, a weekly full refresh, and isolates failures so one
  agency's outage never stops the others.
- **Normalization.** Every barcode is reduced to a canonical GTIN-14. Notices
  that print UPCs with spaces, dashes, missing check digits or missing leading
  zeros are repaired, and UPC-E and EAN-13 codes compare equal to their UPC-A
  forms. Lot codes and best-by dates are parsed from free text, including date
  ranges ("OCT 1 2026 to OCT 21 2026").
- **Matching with confidence levels.** `POST /v1/match` reports *exact*
  (UPC + lot, or a notice that covers every lot), *UPC only* and *name only*
  matches. Name matching uses RapidFuzz with rarity weighting, so generic names
  like "cheddar cheese" stay silent. Purchases are processed in memory and never
  stored on the server.
- **Installable web app** (SvelteKit PWA). Purchases live in IndexedDB on the
  device. Add them by barcode scan (BarcodeDetector with ZXing fallback, GS1
  case labels with lot and expiry), receipt photo (Tesseract.js, on-device),
  loyalty or order-history CSV import, or by hand.
- **Silence by default.** The home screen says nothing until a recall matches.
  Then it shows one card per item: the product, the reason, what to do, where to
  get a refund, and how sure the match is. "Check the code on your package"
  clears a UPC-only match in one step when your lot isn't listed.
- **Pantry mode.** Receive donated stock with a continuous scanner, import
  inventory spreadsheets, check everything by UPC and lot, and export or print a
  pull list.
- **Private push alerts.** Devices register 16-bit watch buckets instead of
  barcodes. The service worker confirms matches on the device and notifies only
  when something you own is affected. A daily on-device check runs where
  Periodic Background Sync is available.
- Product names from Open Food Facts, cached on the server.
- Docker images for the API/worker and the web app, a Compose stack, CI (lint,
  types, unit, Postgres integration and Playwright end-to-end tests), CodeQL,
  Dependabot, and an automated release workflow with build numbers.

[Unreleased]: https://github.com/lobojoel2003/Boughtsafe/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/lobojoel2003/Boughtsafe/releases/tag/v1.0.0
