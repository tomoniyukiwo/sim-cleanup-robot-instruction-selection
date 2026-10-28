#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v uv >/dev/null || { echo 'Install uv first: see README.md' >&2; exit 1; }
command -v gcc >/dev/null || { echo 'Install build-essential first: see README.md' >&2; exit 1; }
source scripts/uv_env.sh
uv sync --locked --python 3.12
uv pip check --python "$UV_PROJECT_ENVIRONMENT/bin/python"
uv run --locked python scripts/init_libero.py
printf '\nEnvironment ready. In your terminal run:\nsource scripts/uv_env.sh\nuv run --locked cleanup-robot doctor\n'
