#!/usr/bin/env bash
# Reconcile the isolated uv environment against the checked-in lockfile.
set -euo pipefail
cd "$(dirname "$0")/.."
exec bash scripts/setup_ubuntu.sh
