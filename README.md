<p align="center">
  <img src="web/static/icons/logo-256.png" alt="Boughtsafe" width="96" height="96">
</p>

<h1 align="center">Boughtsafe</h1>

<p align="center">
  <strong>Recall alerts matched to what you actually bought.</strong><br>
  Silent until something you own is recalled.
</p>

<p align="center">
  <a href="https://github.com/lobojoel2003/Boughtsafe/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/lobojoel2003/Boughtsafe/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <a href="https://github.com/lobojoel2003/Boughtsafe/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/lobojoel2003/Boughtsafe?sort=semver&color=1e6a49"></a>
  <a href="https://github.com/lobojoel2003/Boughtsafe/actions/workflows/codeql.yml"><img alt="CodeQL" src="https://github.com/lobojoel2003/Boughtsafe/actions/workflows/codeql.yml/badge.svg?branch=main"></a>
  <a href="LICENSE"><img alt="License: AGPL-3.0" src="https://img.shields.io/badge/license-AGPL--3.0-1e6a49"></a>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-3776ab">
  <img alt="SvelteKit PWA" src="https://img.shields.io/badge/web-SvelteKit%20PWA-ff3e00">
</p>

<p align="center">
  <img src="docs/images/hero.png" alt="Boughtsafe on three phones: an all-clear screen, a recall card for raw cheddar contaminated with E. coli, and the pantry pull list" width="100%">
</p>

Recall notices go out as press releases, and most people never learn that something in
their own kitchen is on the list. Boughtsafe pulls the **FDA**, **USDA FSIS** and **CPSC**
recall feeds and matches them to what you actually bought: from **receipt photos**,
**barcode scans** or **store loyalty exports**. A **pantry mode** checks donated stock by
UPC and lot code.

Your purchases stay on your device. Boughtsafe says nothing until a recall matches
something you own. Then it shows one clear card: the product, the reason, what to do,
where to get a refund, and how sure the match is.

---

## Contents

- [Why this exists](#why-this-exists)
- [What it does](#what-it-does)
- [Screenshots](#screenshots)
- [How matching works](#how-matching-works)
- [Privacy](#privacy)
- [Architecture](#architecture)
- [Quick start (Docker)](#quick-start-docker)
- [Local development](#local-development)
- [Configuration](#configuration)
- [HTTP API](#http-api)
- [Data sources and limits](#data-sources-and-limits)
- [Versioning, builds and releases](#versioning-builds-and-releases)
- [Project layout](#project-layout)
- [Contributing](#contributing) · [Security](#security) · [License](#license)

## Why this exists

**Foodborne illness linked to recalled food is getting worse, not better.**
U.S. PIRG Education Fund's
[*Food for Thought 2025*](https://pirg.org/edfund/resources/food-for-thought-2025/)
report, which covers recalls announced in 2024, counts:

| 2024 (vs. 2023)            | Count                     |
| -------------------------- | ------------------------- |
| Food recalls (FDA + USDA)  | **296**, slightly down    |
| Illnesses                  | **1,392**, up from 1,118  |
| Hospitalizations           | **487**, up from 230      |
| Deaths                     | **19**, up from 8         |

Fewer recalls did not mean safer food: hospitalizations and deaths both more than
doubled. The report links the deaths to deli meat, cucumbers, onions, carrots, soft
cheese, mushroom chocolate snacks, and ready-to-eat meat and poultry.

**People don't hear about recalls in time.** Covering a paid recall app,
[ConsumerAffairs](https://www.consumeraffairs.com/news/new-app-alerts-you-when-theres-a-recall-031626.html)
writes that *"most families don't know a product in their home has been recalled until
someone gets hurt,"* and that recalled products stay in homes for years.

**People already pay for matching.** The same app charges $1.99 a month for filtering and
$4.99 a month for matching recalls to your products.

**What exists falls short.** Closed apps such as
[RecallSentry](https://apps.apple.com/us/app/recallsentry/id6757089047),
[Recall Scope](https://apps.apple.com/app/id6753904018),
[GroceryGuard](https://www.producthunt.com/products/groceryguard) and
[Food Recall Monitor](https://apps.apple.com/us/app/-/id6768889941) keep your purchase
history on their servers and put matching behind a paywall. On GitHub there are only feed
readers such as [rishipalb/FDA_recall](https://github.com/rishipalb/FDA_recall), and a search
for "food recall receipt" returns no repositories. None of them serves food pantries.

|                                   | Boughtsafe | Closed recall apps | Feed readers |
| --------------------------------- | :--------: | :----------------: | :----------: |
| FDA + USDA FSIS + CPSC            |     ✓      |       varies       |    usually one |
| Matches *your* purchases          |     ✓      |        paid        |      ✗       |
| Lot code / best-by aware          |     ✓      |         ✗          |      ✗       |
| Purchase history stays on device  |     ✓      |         ✗          |      –       |
| Food pantry mode                  |     ✓      |         ✗          |      ✗       |
| Open source, self-hostable        |     ✓      |         ✗          |      ✓       |

## What it does

- **Adds what you bought, four ways.**
  - **Barcode scan:** the browser's `BarcodeDetector`, with ZXing as a fallback on Safari
    and Firefox. Scanning a GS1-128 or GS1 DataMatrix case label also fills in the lot and expiry.
  - **Receipt photo:** read on the device with Tesseract.js, with common shelf-tag
    abbreviations expanded ("GV WHL MLK" → "Great Value Whole Milk").
  - **Store export:** loyalty or order-history CSV, with automatic column detection.
  - **By hand.**

  Product names come from Open Food Facts.
- **Stays silent.** The home screen is a calm "Nothing you own is on a recall list." until a
  recall matches.
- **One card per problem.** It shows the product, the hazard ("E. coli", "Undeclared
  sesame"), what to do, and where to get a refund ("Take it back to Kroger for a full
  refund."). For CPSC recalls it shows the company's own remedy and contact.
- **Says how sure it is.** Every match is labelled **UPC + lot**, **UPC only** or **name
  only**. A UPC-only card asks for the code on your package and clears itself when your
  lot isn't on the notice.
- **Pantry mode.** Food banks receive donations with a continuous scanner, import
  inventory spreadsheets, check all stock by UPC and lot, and export or print a pull list.
- **Private push alerts.** See [Privacy](#privacy). A daily on-device check also runs
  where Periodic Background Sync is available.
- **Installable and offline-capable.** It's a PWA with a service worker, a manifest,
  dark mode and accessible markup.

## Screenshots

<table>
  <tr>
    <td align="center" width="33%"><img src="docs/images/welcome.png" alt="Welcome screen" width="260"><br><sub>First run</sub></td>
    <td align="center" width="33%"><img src="docs/images/all-clear.png" alt="All clear: 24 items checked against 34,251 recalls" width="260"><br><sub>Silence by default</sub></td>
    <td align="center" width="33%"><img src="docs/images/alert.png" alt="Recall card for Family Farmstead raw cheddar" width="260"><br><sub>One clear card</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="docs/images/upc-check.png" alt="UPC-only match asking for the lot code" width="260"><br><sub>UPC only: check your code</sub></td>
    <td align="center"><img src="docs/images/name-match.png" alt="Name-only match from a receipt" width="260"><br><sub>Name only, from a receipt</sub></td>
    <td align="center"><img src="docs/images/receipt.png" alt="Reviewing lines read from a receipt" width="260"><br><sub>Receipt review</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="docs/images/pantry.png" alt="Pantry mode pull list" width="260"><br><sub>Pantry pull list</sub></td>
    <td align="center"><img src="docs/images/items.png" alt="Items list" width="260"><br><sub>Your items</sub></td>
    <td align="center"><img src="docs/images/alert-dark.png" alt="Recall card in dark mode" width="260"><br><sub>Dark mode</sub></td>
  </tr>
</table>

The screenshots show real recalls from the live catalog (34,251 FDA and CPSC notices at
the time), regenerated by [`web/tests/e2e/screenshots.spec.ts`](web/tests/e2e/screenshots.spec.ts).

## How matching works

| Confidence      | When                                                                                      | What the card says                         |
| --------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------ |
| **UPC + lot**   | Your barcode is on the notice **and** your lot or best-by date is listed, or the notice covers every lot | Exact match: act on it                     |
| **UPC only**    | Your barcode is on the notice, the notice lists specific lots, and we don't know yours    | Check the code on your package (one tap clears it) |
| **Name only**   | No barcode on one side; product name and brand match closely                               | Compare brand, size and codes first        |

The matcher is built for silence, so a false alarm counts as a bug:

- **Barcodes are normalized to GTIN-14.** UPC-A, UPC-E, EAN-8, EAN-13 and GTIN-14 compare
  equal. Notices that print `UPC 8 98111 00206` with no check digit, or drop the leading
  zero, are repaired. Receipts that print zero-padded codes without check digits are
  repaired too.
- **Lot codes and dates are compared like with like.** A best-by date is checked against
  the notice's dates *and date ranges* ("BEST BY OCT 1 2026 to OCT 21 2026"). A lot number
  is checked against its lot codes, including codes split by spaces ("3B1 274"). If your
  code isn't listed, the match is ruled out quietly and explained on the item's page.
  If the notice lists only the other kind of code, the answer is "check your package", not "safe".
- **Name matching is weighted by rarity.** RapidFuzz scores the overlap, and every word
  is weighted by how rare it is across all 34k notices. "WinCo hoagie rolls" matches the
  WinCo recall. "Cheddar cheese", "chicken breast" and "whole milk" never trigger an
  alert on their own. OCR typos are corrected against the catalog's vocabulary.
- **Time windows.** Name matches only consider recalls from about four months before to
  two years after the purchase. A barcode recalled more than two years before you bought
  the product needs a matching lot to alert.
- **A listed barcode overrides the name.** If a notice lists barcodes and yours isn't one
  of them, a similar name won't trigger an alert.

## Privacy

- **Purchases live in IndexedDB on your device.** There is no account and no server-side
  purchase history. Export and delete everything from **Settings**.
- **Matching is stateless.** The app sends the relevant fields (barcode, lot, name, brand,
  date) with each `POST /v1/match`. The server matches them in memory, logs only a count,
  and answers with `Cache-Control: no-store`. Nothing in the request is written to disk.
- **Receipts are read on the device.** Photos are never uploaded. Only the OCR model is
  downloaded, once.
- **Push alerts don't reveal what you own.** Your device registers *watch buckets*: the
  first 16 bits of a salted SHA-256 of each barcode. Each bucket is shared by roughly 1 in
  65,536 of all products. When a sync adds a recall, the server wakes only the devices
  watching that recall's buckets. The service worker then checks its own items and shows a
  notification only if something you own really matches. Push endpoints are restricted to
  the browser vendors' push services.
- **Self-host it.** The whole stack is one `docker compose up`.

## Architecture

```mermaid
flowchart LR
  subgraph Agencies["Recall agencies"]
    FDA["openFDA<br/>food enforcement"]
    FSIS["USDA FSIS<br/>recall API"]
    CPSC["CPSC<br/>recalls API"]
  end

  subgraph Server["Boughtsafe server · Python / FastAPI"]
    W["sync worker<br/>hourly incremental · weekly full"]
    PG[("Postgres<br/>recalls · GTINs · buckets")]
    M["matcher<br/>GTIN index + RapidFuzz"]
    API["HTTP API<br/>/v1/match · /v1/products · /v1/push"]
    W --> PG --> M --> API
  end

  OFF["Open Food Facts"]

  subgraph Device["Your phone · SvelteKit PWA"]
    UI["app<br/>scan · receipt OCR · import"]
    IDB[("IndexedDB<br/>your purchases")]
    SW["service worker<br/>offline · push · daily check"]
    UI <--> IDB
    SW <--> IDB
  end

  FDA --> W
  FSIS --> W
  CPSC --> W
  OFF -. "product names, cached" .-> API
  UI -- "items per request, never stored" --> API
  W -- "push: watch buckets only" --> SW
  SW -- "confirm on device" --> API
```

| Part        | Stack                                                                                         |
| ----------- | --------------------------------------------------------------------------------------------- |
| Server      | Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, Postgres 16 (SQLite for development), httpx, RapidFuzz, pywebpush |
| Web app     | SvelteKit 2 + Svelte 5 (static SPA), TypeScript, `idb`, BarcodeDetector + ZXing, Tesseract.js, Lucide icons |
| Delivery    | Docker (API/worker and nginx web images, amd64 + arm64), Docker Compose, GitHub Actions, GHCR |

## Quick start (Docker)

```bash
git clone https://github.com/lobojoel2003/Boughtsafe.git
```

```bash
cd Boughtsafe && cp .env.example .env
```

```bash
docker compose up -d
```

Open <http://localhost:8080>. The worker starts a full sync immediately. The first run
loads about 34,000 recalls in roughly a minute; after that it syncs hourly.

To turn on push alerts, generate VAPID keys, put them in `.env`, then restart:

```bash
docker compose run --rm api vapid-keys
```

```bash
docker compose up -d
```

Camera access, installing the app, the service worker and push alerts all need HTTPS
(`localhost` is exempt). In production, put the `web` service behind a TLS-terminating
proxy such as Caddy or Traefik. To pin a release instead of `latest`, set
`BOUGHTSAFE_VERSION=1.0.0` in `.env`.

Prebuilt images:

```bash
docker pull ghcr.io/lobojoel2003/boughtsafe-api:latest
```

```bash
docker pull ghcr.io/lobojoel2003/boughtsafe-web:latest
```

## Local development

**Server** (Python 3.11+). SQLite is the default, so no database setup is needed:

```bash
cd server && python -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'
```

```bash
boughtsafe migrate && boughtsafe seed tests/fixtures/recalls.json
```

```bash
boughtsafe serve --port 8000
```

`boughtsafe sync` mirrors the real feeds (`--source fda`, `--full`, `--loop`). Interactive
API docs are at <http://localhost:8000/docs>.

**Web app** (Node 20.19+). The dev server proxies `/api` to `localhost:8000`:

```bash
cd web && npm install && npm run dev
```

**Checks** — the same ones CI runs:

```bash
cd server && ruff check . && ruff format --check . && mypy && pytest --cov
```

```bash
cd web && npm run lint && npm run check && npm test && npm run e2e
```

There are 119 server tests (normalization, every adapter, matching, ingest, API, CLI;
they run on SQLite and on Postgres), 29 web unit tests, and 6 Playwright end-to-end tests
against a fixture-seeded API.

## Configuration

Server settings are environment variables prefixed `BOUGHTSAFE_` (a `.env` file also works):

| Variable                              | Default                         | Purpose                                              |
| ------------------------------------- | ------------------------------- | ---------------------------------------------------- |
| `BOUGHTSAFE_DATABASE_URL`             | `sqlite:///./boughtsafe.db`     | SQLAlchemy URL, e.g. `postgresql+psycopg://user:pass@host/db` |
| `BOUGHTSAFE_CORS_ORIGINS`             | `["http://localhost:5173"]`     | Origins allowed to call the API directly             |
| `BOUGHTSAFE_OPENFDA_API_KEY`          | –                               | Optional key for higher openFDA rate limits          |
| `BOUGHTSAFE_FSIS_URL`                 | FSIS API                        | Also accepts `file:///path/fsis.json` (see below)    |
| `BOUGHTSAFE_BACKFILL_FROM_YEAR`       | `2012`                          | Oldest year to mirror                                 |
| `BOUGHTSAFE_SYNC_INTERVAL_MINUTES`    | `60`                            | Worker interval (`boughtsafe sync --loop`)           |
| `BOUGHTSAFE_FULL_REFRESH_HOURS`       | `168`                           | How often a full re-download replaces incremental sync |
| `BOUGHTSAFE_OFF_ENABLED`              | `true`                          | Look up product names on Open Food Facts             |
| `BOUGHTSAFE_VAPID_PUBLIC_KEY` / `_PRIVATE_KEY` | –                      | Web Push keys (`boughtsafe vapid-keys`)              |
| `BOUGHTSAFE_VAPID_SUBJECT`            | project URL                     | Contact for push services (`mailto:` or URL)         |
| `BOUGHTSAFE_NAME_MATCH_MIN_SCORE`     | `82`                            | Minimum name-match score (0–100)                     |
| `BOUGHTSAFE_UPC_MATCH_MAX_AGE_DAYS`   | `730`                           | Barcode recalls older than this need a lot match      |
| `BOUGHTSAFE_BUILD_NUMBER` / `_GIT_SHA`| `dev` / `local`                 | Set by CI and the Docker build                        |

The web app reads `VITE_API_BASE` at build time (default `/api`). Users can also point it
at another server from **Settings → Recall server**.

## HTTP API

| Method & path                  | Purpose                                                                 |
| ------------------------------ | ----------------------------------------------------------------------- |
| `POST /v1/match`               | Match up to 2,000 items; returns matches, ruled-out recalls and catalog version |
| `GET /v1/recalls`              | Browse the catalog (`source`, `q`, `code`, `since`, `limit`, `offset`)  |
| `GET /v1/recalls/{id}`         | One normalized recall, e.g. `fda:H-0197-2027`                           |
| `GET /v1/products/{code}`      | Barcode → product name via Open Food Facts (cached)                     |
| `GET /v1/meta`                 | Version, build, commit, per-source counts and last sync, push key       |
| `POST/DELETE /v1/push/subscriptions` | Register or remove a device and its watch buckets                 |
| `POST /v1/push/test`           | Send a test notification to a registered device                         |
| `GET /healthz`, `GET /readyz`  | Liveness and readiness                                                  |

```bash
curl -s localhost:8000/v1/match -H 'content-type: application/json' -d '{"items":[{"id":"1","code":"860007132216","lot":"Best by JUL 22 27","purchased_at":"2026-10-20"}]}'
```

```json
{
  "matches": [{
    "item_id": "1", "confidence": "exact", "lot_status": "matched",
    "matched_gtin": { "gtin": "00860007132216", "display": "8 60007 13221 6" },
    "recall": {
      "id": "fda:H-0197-2027", "source_label": "FDA", "classification": "Class I",
      "hazard": { "kind": "pathogen", "label": "E. coli", "allergens": [] },
      "reason": "Potential contamination with E. coli (pathogenic non-O157 STEC).",
      "action": "Don't eat it, even if it looks and smells fine. …",
      "refund": { "options": ["Refund"], "text": "Return it to the store where you bought it for a full refund." }
    }
  }],
  "ruled_out": [],
  "catalog": { "version": "34251-1795030511", "total": 34251 }
}
```

## Data sources and limits

| Source | What | Notes |
| ------ | ---- | ----- |
| [openFDA food enforcement](https://open.fda.gov/apis/food/enforcement/) | FDA-regulated food recalls since 2012 (about 29,600) | Partitioned by year to stay under openFDA's 25,000-row paging limit. UPCs are extracted from free text, so about 43% of records carry a barcode. |
| [USDA FSIS recall API](https://www.fsis.usda.gov/science-data/developer-resources/recall-api) | Meat, poultry and egg recalls and public health alerts | FSIS's CDN rejects some automated clients and data-center IPs. If yours is blocked, download the JSON another way and set `BOUGHTSAFE_FSIS_URL=file:///path/fsis.json`. Other sources keep syncing either way. |
| [CPSC recalls API](https://www.cpsc.gov/Recalls/CPSC-Recalls-Application-Program-Interface-API-Information) | Consumer product recalls (about 4,600 since 2012) | Includes remedies, refund contacts and product photos. |
| [Open Food Facts](https://world.openfoodfacts.org/) | Barcode → product name and brand | Open data (ODbL), cached for 30 days. |

Recall data can be incomplete, late or wrong. Boughtsafe reduces the chance that you
miss a recall, but it is not a guarantee and it is not medical advice. Always read the
official notice, which every card links to.

## Versioning, builds and releases

- **Semantic versioning**, with [`VERSION`](VERSION) as the single source of truth.
  [`scripts/version.sh`](scripts/version.sh) keeps `server/pyproject.toml`,
  `web/package.json` and the lockfile in step, and CI fails if they drift.
- **Build numbers.** Every CI run stamps its run number and commit into the web app
  (Settings → About shows `1.0.0 · build 42 · a1b2c3d`), the API (`GET /v1/meta`) and the
  Docker image labels.
- **Changelog.** [`CHANGELOG.md`](CHANGELOG.md) follows Keep a Changelog. Each release's
  notes are taken from its section.
- **Continuous delivery.** Every push to `main` that passes CI publishes `edge`,
  `sha-<commit>` and `build-<n>` images to GHCR.
- **Releases.** When `main` carries a `VERSION` with no tag yet and CI is green, the
  [Release workflow](.github/workflows/release.yml) tags `vX.Y.Z` and builds the Python
  wheel and sdist, the web bundle, `BUILD-INFO.txt` and `SHA256SUMS.txt`. It pushes
  multi-arch images tagged `X.Y.Z`, `X.Y`, `X`, `latest` and `build-<n>`, and publishes a
  GitHub Release with all of these attached.

To cut a release, bump the version, commit, and push to `main`:

```bash
scripts/version.sh bump minor
```

```bash
git commit -am "Release $(cat VERSION)" && git push origin main
```

## Project layout

```text
.
├── server/                    FastAPI service, sync worker and CLI (`boughtsafe`)
│   ├── boughtsafe/
│   │   ├── sources/           openFDA, FSIS and CPSC adapters → one normalized shape
│   │   ├── gtin.py            UPC/EAN/GTIN normalization, extraction, watch buckets
│   │   ├── codes.py           lot codes, package dates and ranges, hazard classification
│   │   ├── matching.py        GTIN index + RapidFuzz name matching with confidence levels
│   │   ├── ingest.py          sync, upsert, FDA de-duplication
│   │   ├── push.py            Web Push (VAPID) by watch bucket
│   │   ├── api/               HTTP API and schemas
│   │   └── migrations/        Alembic migrations
│   └── tests/                 pytest suite and real recall fixtures
├── web/                       SvelteKit installable web app
│   ├── src/lib/               IndexedDB, check, scanner, OCR, receipt and CSV parsing
│   ├── src/routes/            home, items, add (scan, receipt, import, manual), pantry, settings
│   ├── src/service-worker.ts  offline cache, private push handling, daily check
│   └── tests/                 Vitest unit tests and Playwright end-to-end tests
├── docs/images/               README screenshots (generated)
├── scripts/                   version and changelog tooling
├── docker-compose.yml         Postgres + API + worker + web
└── .github/                   CI, release, CodeQL, Dependabot, templates
```

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup,
conventions and the release process. Useful areas to work on: more store export formats,
regional recall feeds, translations, and better receipt parsing.

## Security

Please report vulnerabilities privately; see [SECURITY.md](SECURITY.md).

## License

Boughtsafe is free software under the [GNU Affero General Public License v3.0](LICENSE).
If you run a modified version as a service, you must share your changes with its users.

Recall data comes from the U.S. Food and Drug Administration (openFDA), the USDA Food
Safety and Inspection Service, and the U.S. Consumer Product Safety Commission. Product
data comes from Open Food Facts contributors. None of these agencies or projects endorses
Boughtsafe.
