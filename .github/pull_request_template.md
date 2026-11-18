## What changed

<!-- One or two sentences. Link the issue if there is one. -->

## Why

## How it was tested

- [ ] `server`: `ruff check . && ruff format --check . && mypy && pytest`
- [ ] `web`: `npm run lint && npm run check && npm test`
- [ ] `web`: `npm run e2e` (if the UI or the API contract changed)

## Release

- [ ] User-visible change noted under **Unreleased** in `CHANGELOG.md`
- [ ] Version bumped with `scripts/version.sh` (only when cutting a release)
