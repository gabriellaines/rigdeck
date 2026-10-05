#!/usr/bin/env bash
# Print how big the next release is — patch, minor or major — for automatic releases.
# Patch unless a commit since the last release tag has a "Release: minor" or "Release: major"
# trailer; the biggest one wins.
set -euo pipefail
cd "$(dirname "$0")/.."

last=$(git tag -l 'v*' --sort=-v:refname | head -1)
levels=$(git log --format='%(trailers:key=Release,valueonly,separator=%x0a)' "${last:+$last..}HEAD" \
         | tr '[:upper:]' '[:lower:]' | tr -d '[:blank:]')
if grep -qx major <<<"$levels"; then echo major
elif grep -qx minor <<<"$levels"; then echo minor
else echo patch
fi
