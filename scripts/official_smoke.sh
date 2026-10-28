#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/uv_env.sh
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
# This checks the official baseline separately from our controller. Tokenizer processor
# path is overridden via a local checkpoint copy by scripts/prepare_smoke.py.
uv run --locked python scripts/prepare_smoke.py
uv run --locked python scripts/official_eval_video.py --policy.path=models/smoke_policy --policy.n_action_steps=10   --rename_map='{"observation.images.image":"observation.images.camera1","observation.images.image2":"observation.images.camera2"}' \
  --env.type=libero --env.task=libero_object '--env.task_ids=[0]'   --eval.batch_size=1 --eval.n_episodes=1 --env.max_parallel_tasks=1   --output_dir="${1:-outputs/official_smoke}"

printf '\nVideo FPS: %s (default 20). For half-speed: RECORD_FPS=10 bash scripts/official_smoke.sh outputs/official_slow_01\n' "${RECORD_FPS:-20}"
