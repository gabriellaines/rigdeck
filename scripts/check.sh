#!/usr/bin/env bash
# Validations run by CI before anything is merged or released. Run it locally too:
#   scripts/check.sh
# Each check prints one line; the script stops at the first failure.
set -euo pipefail
cd "$(dirname "$0")/.."

ok()   { printf '\033[32m✓\033[0m %s\n' "$*"; }
fail() {
    printf '\033[31m✗ %s\033[0m\n' "$*" >&2
    if [ -n "${GITHUB_ACTIONS:-}" ]; then   # also as an annotation: readable without opening the log
        printf '::error title=scripts/check.sh::%s\n' "$(printf '%s' "$*" | sed -e 's/%/%25/g' | sed -e ':a;N;$!ba;s/\n/%0A/g')"
    fi
    exit 1
}

# 1. one version everywhere -------------------------------------------------------
version=$(scripts/version.sh)
[ -n "$version" ] || fail "no __version__ in rigdeck/__init__.py"
pkgver=$(sed -n 's/^pkgver=//p' packaging/arch/PKGBUILD)
[ "$pkgver" = "$version" ] || fail "PKGBUILD pkgver ($pkgver) ≠ rigdeck/__init__.py ($version) — use scripts/bump-version.sh"
ok "version $version (PKGBUILD matches)"

# 2. shell scripts ----------------------------------------------------------------
for f in install.sh get.sh scripts/*.sh; do
    bash -n "$f" || fail "syntax error in $f"
done
if command -v shellcheck >/dev/null; then
    shellcheck -S error install.sh get.sh scripts/*.sh || fail "shellcheck found errors"
    ok "shell scripts (syntax + shellcheck)"
else
    ok "shell scripts (syntax; shellcheck not installed)"
fi

# 3. Python compiles --------------------------------------------------------------
python3 -m compileall -q rigdeck >/dev/null || fail "Python syntax errors (see above)"
ok "Python compiles"

# 4. the package installs, with every data file -------------------------------------
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
python3 -m venv --system-site-packages "$tmp/venv"   # sees PySide6 (GUI tests) if installed
"$tmp/venv/bin/pip" install --quiet --disable-pip-version-check . || fail "pip install failed"
rm -rf build rigdeck.egg-info
# run from $tmp: in the repo, Python would import the source tree instead of the install
site=$(cd "$tmp" && "$tmp/venv/bin/python" -c 'import rigdeck, os; print(os.path.dirname(os.path.dirname(rigdeck.__file__)))')
case "$site" in "$PWD"*) fail "checked the source tree instead of the installed package" ;; esac
missing=$(find rigdeck \( -name '*.qml' -o -name qmldir -o -name '*.svg' \) -not -path '*/__pycache__/*' \
          | while read -r f; do [ -e "$site/$f" ] || echo "  $f"; done)
[ -z "$missing" ] || fail "files missing from the installed package (add them to package-data in pyproject.toml):
$missing"
ok "package installs with all QML/icon files"

# 5. the CLI starts (no hardware needed for --help) ----------------------------------
rd="$tmp/venv/bin/rigdeck"
[ "$("$rd" --version | awk '{print $NF}')" = "$version" ] || fail "rigdeck --version doesn't report $version"
for cmd in "" info service update cooler gpu "gpu status" "gpu fan" "gpu power" "gpu enable-controls" \
           headset "headset status" "headset sidetone" "headset auto-off" "headset lights" \
           webcam "webcam list" "webcam status" "webcam set" "webcam reset" \
           mouse "mouse list" "mouse status" "mouse set" "mouse backup" "mouse restore" \
           keyboard "keyboard status" "keyboard brightness" "keyboard features" \
           monitor "monitor status" "monitor set" motherboard network bluetooth \
           session "session start" "session stop" "session status" "session list" "session show" "session export"; do
    # shellcheck disable=SC2086  # word-splitting the subcommand is intended
    "$rd" $cmd --help >/dev/null || fail "rigdeck $cmd --help failed"
done
ok "CLI runs"

# 5b. every QML file compiles (needs PySide6; CI installs it, RIGDECK_REQUIRE_QML=1 makes it mandatory)
set +e
out=$(python3 scripts/check_qml.py 2>&1); rc=$?
set -e
case $rc in
    0) ok "QML compiles (${out##*$'\n'})" ;;
    2) [ -z "${RIGDECK_REQUIRE_QML:-}" ] || fail "PySide6 is needed to compile the QML"
       ok "QML (skipped: PySide6 not installed)" ;;
    *) fail "QML errors:
$out" ;;
esac

# 6. release notes exist for this version ---------------------------------------------
scripts/release-notes.sh "$version" >/dev/null || fail "CHANGELOG.md needs a '## $version' section"
ok "CHANGELOG has notes for $version"

# 7. tests (when there are some) ------------------------------------------------------
if [ -d tests ]; then
    "$tmp/venv/bin/pip" install --quiet pytest
    out=$("$tmp/venv/bin/python" -m pytest -q tests 2>&1) || fail "tests failed:
$(printf '%s\n' "$out" | tail -25)"
    printf '%s\n' "$out" | tail -1
    ok "tests pass"
fi

ok "all checks passed"
