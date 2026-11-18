#!/usr/bin/env bash
# Print the CHANGELOG.md section for one version (used for GitHub release notes).
set -euo pipefail
v=${1:?usage: changelog-section.sh X.Y.Z}
awk -v v="$v" '
  $0 ~ "^## \\[" v "\\]" { on=1; next }
  on && /^## \[/ { exit }
  on && /^\[[^]]+\]: / { exit }
  on { print }' "$(dirname "$0")/../CHANGELOG.md" | sed -e '/./,$!d'
