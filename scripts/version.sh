#!/usr/bin/env bash
# Single source of truth for the version is ./VERSION. This script keeps
# server/pyproject.toml, web/package.json and web/package-lock.json in step.
#
#   scripts/version.sh check            # fail if any file disagrees with VERSION
#   scripts/version.sh bump patch       # 1.0.0 -> 1.0.1 (also: minor, major)
#   scripts/version.sh set 1.2.0        # explicit version
#
# A bump also opens a new section in CHANGELOG.md. Commit, merge to main, and the
# Release workflow tags vX.Y.Z and publishes the release once CI passes.
set -euo pipefail
cd "$(dirname "$0")/.."

current() { tr -d '[:space:]' < VERSION; }
py_version() { sed -n 's/^version = "\(.*\)"/\1/p' server/pyproject.toml | head -1; }
js_version() { node -p "require('./web/package.json').version"; }
lock_version() { node -p "require('./web/package-lock.json').version"; }

check() {
  local v; v=$(current)
  [[ $v =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$ ]] || { echo "VERSION '$v' is not semver" >&2; exit 1; }
  local ok=1
  for pair in "server/pyproject.toml:$(py_version)" "web/package.json:$(js_version)" "web/package-lock.json:$(lock_version)"; do
    if [[ ${pair#*:} != "$v" ]]; then echo "✗ ${pair%%:*} has ${pair#*:}, VERSION has $v" >&2; ok=0; fi
  done
  grep -q "^## \[$v\]" CHANGELOG.md || { echo "✗ CHANGELOG.md has no section for $v" >&2; ok=0; }
  [[ $ok == 1 ]] && echo "✓ version $v is consistent"
  [[ $ok == 1 ]]
}

write() {
  local v=$1
  echo "$v" > VERSION
  sed -i.bak "s/^version = \".*\"/version = \"$v\"/" server/pyproject.toml && rm server/pyproject.toml.bak
  node -e '
    const fs = require("fs"); const v = process.argv[1];
    for (const f of ["web/package.json", "web/package-lock.json"]) {
      const j = JSON.parse(fs.readFileSync(f, "utf8"));
      j.version = v; if (j.packages && j.packages[""]) j.packages[""].version = v;
      fs.writeFileSync(f, JSON.stringify(j, null, f.endsWith("lock.json") ? 2 : "\t") + "\n");
    }' "$v"
  if ! grep -q "^## \[$v\]" CHANGELOG.md; then
    local today; today=$(date -u +%Y-%m-%d)
    awk -v v="$v" -v d="$today" '
      /^## \[Unreleased\]/ && !done { print; print ""; print "## [" v "] - " d; done=1; next } { print }' \
      CHANGELOG.md > CHANGELOG.md.tmp && mv CHANGELOG.md.tmp CHANGELOG.md
  fi
  echo "version set to $v"
}

case "${1:-check}" in
  check) check ;;
  set) write "${2:?usage: version.sh set X.Y.Z}" ;;
  bump)
    IFS=. read -r major minor patch <<<"$(current | cut -d- -f1)"
    case "${2:?usage: version.sh bump major|minor|patch}" in
      major) write "$((major + 1)).0.0" ;;
      minor) write "$major.$((minor + 1)).0" ;;
      patch) write "$major.$minor.$((patch + 1))" ;;
      *) echo "unknown part: $2" >&2; exit 2 ;;
    esac ;;
  *) echo "usage: $0 check | bump major|minor|patch | set X.Y.Z" >&2; exit 2 ;;
esac
