#!/usr/bin/env bash
# Run one setup/evaluation stage at a time and keep the last output on disk.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
stage="${1:-}"
case "$stage" in
  lock|sync|check|prepare|compare) ;;
  *) echo 'Usage: bash scripts/setup_qwen35.sh {lock|sync|check|prepare|compare}' >&2; exit 2 ;;
esac
mkdir -p outputs/setup
log="outputs/setup/$(date -u +%Y%m%dT%H%M%SZ)_${stage}.log"
echo "Logging $stage to $log"
exec > >(tee -a "$log") 2>&1
trap 'status=$?; echo "Stage $stage failed with exit code $status"; exit "$status"' ERR
case "$stage" in
  lock) env -u UV_PROJECT_ENVIRONMENT uv lock --project planner_env ;;
  sync) env -u UV_PROJECT_ENVIRONMENT uv sync --project planner_env --locked ;;
  check) env -u UV_PROJECT_ENVIRONMENT uv run --project planner_env --locked python -c 'from transformers import AutoModelForMultimodalLM, AutoProcessor; print("Qwen3.5 loader OK")' ;;
  prepare)
    source scripts/uv_env.sh
    uv run --locked cleanup-robot --config configs/qwen35_fewshot.json prepare-planner \
      --lock models/assets.qwen35.lock.json --base-lock models/assets.lock.json ;;
  compare)
    source scripts/uv_env.sh
    uv run --locked python scripts/compare_selection.py ;;
esac
echo "Stage $stage completed"
