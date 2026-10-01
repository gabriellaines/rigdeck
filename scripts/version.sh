#!/usr/bin/env bash
# Print rigdeck's version (from rigdeck/__init__.py, the single source of truth).
set -euo pipefail
cd "$(dirname "$0")/.."
sed -n 's/^__version__ = "\(.*\)"$/\1/p' rigdeck/__init__.py
