# Contributing to Boughtsafe

Thanks for helping people find out about recalls in time. This guide covers setup,
conventions and how releases are made.

## Setup

| Part   | Needs        | Install |
| ------ | ------------ | ------- |
| Server | Python 3.11+ | `cd server && python -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'` |
| Web    | Node 20.19+  | `cd web && npm install` |

Run the API with fixture data, then the web app (it proxies `/api` to port 8000):

```bash
cd server && boughtsafe migrate && boughtsafe seed tests/fixtures/recalls.json && boughtsafe serve
```

```bash
cd web && npm run dev
```

For the real catalog, run `boughtsafe sync` (about a minute for a full sync).

## Checks

CI runs all of these on every push and pull request. Please run them first.

```bash
cd server && ruff check . && ruff format --check . && mypy && pytest --cov
```

```bash
cd web && npm run lint && npm run check && npm test && npm run e2e
```

- Server tests use SQLite by default. Set
  `BOUGHTSAFE_TEST_DATABASE_URL=postgresql+psycopg://…` to run them on Postgres, as CI does.
- `npm run e2e` starts a fixture-seeded API (`web/tests/e2e/start-api.sh`) and a production
  build of the app, then drives it with Playwright.
- Schema changes need an Alembic migration:
  `cd server && alembic -c alembic.ini revision --autogenerate -m "describe change"`.
  CI runs `alembic check` to catch models that drifted from the migrations.

## Conventions

- **Silence is the feature.** Any change to matching must keep generic names
  ("cheddar cheese", "whole milk") quiet. Add a test for both the case that should
  alert and the one that shouldn't.
- **Purchases never get stored on the server.** Don't log request bodies. Don't add
  server-side purchase state.
- Python is formatted with `ruff format`. TypeScript and Svelte are formatted with Prettier.
- Fixtures under `server/tests/fixtures` are real upstream records, except the FSIS ones,
  which use fictional companies in the FSIS schema. Don't invent records about real firms.
- Note user-visible changes under **Unreleased** in `CHANGELOG.md`.

## Releases

`VERSION` is the single source of truth. To cut a release, bump it, commit, and push to `main`:

```bash
scripts/version.sh bump patch
```

```bash
git commit -am "Release $(cat VERSION)" && git push origin main
```

Here's what each step does:

1. `bump` takes `patch`, `minor` or `major`, or use `set X.Y.Z`. It updates
   `server/pyproject.toml`, `web/package.json` and the lockfile, and opens a dated section
   in `CHANGELOG.md`. Move the **Unreleased** notes into that section before you commit.
2. Once CI passes on `main`, the Release workflow tags `vX.Y.Z`. It publishes multi-arch
   images to GHCR and creates the GitHub Release with the wheel, the web bundle and checksums.
3. Every build carries the CI run number as its build number. It shows in the app's
   **Settings → About**, in `GET /v1/meta` and in the image labels.

Versions with a suffix (`1.2.0-rc.1`) are published as pre-releases and don't move
`latest`.
