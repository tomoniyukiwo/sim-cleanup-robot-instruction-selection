"""Compare registered task selection without starting the robot."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import uuid

from cleanup_robot.comparison import run_comparison


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cases', default='tasks/comparison_cases_qwen35.json')
    ap.add_argument('--catalog', default='tasks/libero_object.json')
    ap.add_argument('--config', default='configs/qwen35_fewshot.json')
    ap.add_argument('--lock', default='models/assets.qwen35.lock.json')
    ap.add_argument('--out', help='New output directory; refuses existing paths')
    ap.add_argument('--method', choices=['both', 'qwen', 'minilm'], default='both')
    args = ap.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    out = args.out or f'outputs/comparison/{stamp}_{uuid.uuid4().hex[:8]}'
    methods = ('qwen', 'minilm') if args.method == 'both' else (args.method,)
    summary = run_comparison(args.cases, args.catalog, args.config, args.lock, out, methods)
    print(f'Saved {out}: {summary["completed_cases"]} case results, {len(summary["errors"])} errors')


if __name__ == '__main__':
    main()
