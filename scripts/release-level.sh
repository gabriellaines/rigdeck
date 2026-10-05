#!/usr/bin/env bash
# Print how big the next release is — patch, minor or major — for automatic releases:
#   - major / minor when a commit since the last release tag has a "Release: major" / "Release: minor"
#     trailer (the biggest wins; optional, to override the guess below),
#   - minor when a new hardware module was added (rigdeck/modules/<name>/),
#   - patch otherwise.
set -euo pipefail
cd "$(dirname "$0")/.."

last=$(git tag -l 'v*' --sort=-v:refname | head -1)
range=${last:+$last..}HEAD
levels=$(git log --format='%(trailers:key=Release,valueonly,separator=%x0a)' "$range" \
         | tr '[:upper:]' '[:lower:]' | tr -d '[:blank:]')
if grep -qx major <<<"$levels"; then echo major
elif grep -qx minor <<<"$levels"; then echo minor
elif [ -n "$(git diff --name-only --diff-filter=A "${last:-$(git hash-object -t tree /dev/null)}" HEAD -- 'rigdeck/modules/*/__init__.py')" ]; then echo minor
else echo patch
fi
