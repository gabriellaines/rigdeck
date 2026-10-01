#!/usr/bin/env bash
# Print the notes for the next release:
#   - anything written by hand under "## Unreleased" in CHANGELOG.md, then
#   - one bullet per "Changelog: …" trailer in the commits since the last release tag.
# Commits without a Changelog trailer are internal and left out.
set -euo pipefail
cd "$(dirname "$0")/.."

git fetch -q --tags origin 2>/dev/null || true
last=$(git tag -l 'v*' --sort=-v:refname | head -1)
range=${last:+$last..}HEAD

trim() { sed -e '/./,$!d' | tac | sed -e '/./,$!d' | tac; }  # drop leading/trailing blank lines

manual=$(awk '/^## Unreleased/{f=1; next} /^## /{f=0} f' CHANGELOG.md | trim)
trailers=$(git log --reverse --format='%(trailers:key=Changelog,valueonly,unfold,separator=%x0a)' "$range" \
           | sed -e '/^[[:space:]]*$/d' -e 's/^[[:space:]]*/- /')

printf '%s\n' "$manual" "" "$trailers" | trim
