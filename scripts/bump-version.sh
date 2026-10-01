#!/usr/bin/env bash
# Prepare a release on `develop`:  scripts/bump-version.sh 0.3.1
#
# Sets the version in rigdeck/__init__.py and the PKGBUILD, and writes the CHANGELOG section
# "X.Y.Z — today" from the commits' "Changelog: …" lines plus anything written by hand under
# "Unreleased" (see scripts/unreleased.sh). Review/edit CHANGELOG.md before committing.
# Then commit, and merge develop into main: the Release workflow publishes it.
set -euo pipefail
cd "$(dirname "$0")/.."

new=${1:-}
[[ $new =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "usage: $0 X.Y.Z" >&2; exit 2; }
old=$(scripts/version.sh)
[ "$new" != "$old" ] || { echo "already at $new" >&2; exit 1; }
if [ "$(printf '%s\n%s\n' "$old" "$new" | sort -V | tail -1)" != "$new" ]; then
    echo "$new is not newer than $old" >&2; exit 1
fi

# These become the release notes, so there must be some.
notes=$(scripts/unreleased.sh)
if [ -z "$notes" ]; then
    echo "Nothing to release notes from: no 'Changelog:' lines in the commits since the last release," >&2
    echo "and nothing under '## Unreleased' in CHANGELOG.md. Write the notes there, then run this again." >&2
    exit 1
fi

sed -i "s/^__version__ = \".*\"/__version__ = \"$new\"/" rigdeck/__init__.py
sed -i "s/^pkgver=.*/pkgver=$new/; s/^pkgrel=.*/pkgrel=1/" packaging/arch/PKGBUILD
# Replace the Unreleased section with an empty one followed by the new version's notes.
python3 - "$new" "$(date +%F)" "$notes" <<'PY'
import re, sys
new, day, notes = sys.argv[1:]
text = open("CHANGELOG.md").read()
head, sep, rest = text.partition("## Unreleased\n")
if not sep:
    sys.exit("CHANGELOG.md has no '## Unreleased' heading")
m = re.search(r"^## ", rest, re.M)
rest = rest[m.start():] if m else ""
open("CHANGELOG.md", "w").write(f"{head}## Unreleased\n\n## {new} — {day}\n\n{notes}\n\n{rest}")
PY

echo "Version $old → $new. Release notes:"
echo
sed 's/^/    /' <<<"$notes"
echo
echo "Edit CHANGELOG.md if you want to reword them, then:"
echo "  git commit -am \"v$new\" && git push origin develop"
echo "  open a pull request develop → main; merging it publishes the release"
