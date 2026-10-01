#!/usr/bin/env bash
# Print the CHANGELOG section for a version:  scripts/release-notes.sh 0.3.1
# Exits non-zero if the section is missing or empty.
set -euo pipefail
cd "$(dirname "$0")/.."
v=${1:?usage: $0 X.Y.Z}
notes=$(awk -v v="$v" '
    $0 ~ "^## \\[?" v "\\]?( |$)" {f=1; next}
    /^## /{f=0}
    f' CHANGELOG.md)
# trim blank lines at the start and end
notes=$(printf '%s\n' "$notes" | sed -e '/./,$!d' | tac | sed -e '/./,$!d' | tac)
[ -n "$notes" ] || { echo "CHANGELOG.md has no notes for $v" >&2; exit 1; }
printf '%s\n' "$notes"
