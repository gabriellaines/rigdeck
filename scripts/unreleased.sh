#!/usr/bin/env bash
# Print the notes for the next release, all collected automatically:
#   - anything written by hand under "## Unreleased" in CHANGELOG.md, then
#   - for each commit since the last release tag: its "Changelog: …" trailers if it has any,
#     otherwise its subject line — unless it only touches internal files (CI, scripts, tests,
#     developer docs). Merges and "vX.Y.Z" version commits are left out.
set -euo pipefail
cd "$(dirname "$0")/.."

git fetch -q --tags origin 2>/dev/null || true
last=$(git tag -l 'v*' --sort=-v:refname | head -1)
range=${last:+$last..}HEAD

trim() { sed -e '/./,$!d' | tac | sed -e '/./,$!d' | tac; }  # drop leading/trailing blank lines

# changes users never see
internal='^(\.github/|scripts/|tests/|docs/|[^/]*\.md$|\.gitignore$)'

manual=$(awk '/^## Unreleased/{f=1; next} /^## /{f=0} f' CHANGELOG.md | trim)
notes=$(for c in $(git rev-list --reverse --no-merges "$range"); do
    subject=$(git log -1 --format=%s "$c")
    [[ $subject =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] && continue
    trailers=$(git log -1 --format='%(trailers:key=Changelog,valueonly,unfold,separator=%x0a)' "$c" \
               | sed -e '/^[[:space:]]*$/d' -e 's/^[[:space:]]*//')
    if [ -n "$trailers" ]; then
        printf '%s\n' "$trailers"
    elif git diff-tree --no-commit-id --name-only -r "$c" | grep -qvE "$internal"; then
        printf '%s\n' "$subject"
    fi
done | sed 's/^/- /')

printf '%s\n' "$manual" "" "$notes" | trim
