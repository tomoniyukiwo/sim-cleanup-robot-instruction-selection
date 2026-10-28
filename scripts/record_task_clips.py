"""Record one real LIBERO/SmolVLA episode per held-out task, without selector attribution."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid


ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--task-ids', type=int, nargs='+', default=list(range(1, 10)))
    args = ap.parse_args()
    if shutil.which('uv') is None:
        ap.error('uv is required to record LIBERO clips; run this on the configured Ubuntu AI environment')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = args.out or Path(f'outputs/physical_clips/{stamp}_{uuid.uuid4().hex[:8]}')
    out.mkdir(parents=True, exist_ok=False)
    print(f'Recording output: {out}', flush=True)
    catalog = json.loads((ROOT / 'tasks/libero_object.json').read_text())
    tasks = {task['task_id']: task for task in catalog['tasks']}
    if len(args.task_ids) != len(set(args.task_ids)) or any(task_id not in tasks or task_id == 0 for task_id in args.task_ids):
        ap.error('Choose distinct registered task IDs from 1 to 9')
    env = os.environ.copy()
    env.update(UV_PROJECT_ENVIRONMENT=str(ROOT / '.venv-uv'),
               MUJOCO_GL=env.get('MUJOCO_GL', 'egl'),
               LIBERO_CONFIG_PATH=env.get('LIBERO_CONFIG_PATH', str(ROOT / '.libero')))
    rows = []
    for task_id in args.task_ids:
        task = tasks[task_id]
        episode = out / f'task_{task_id}'
        command = ['uv', 'run', '--locked', 'cleanup-robot',
                   '--config', 'configs/default.json', 'run',
                   '--catalog', 'tasks/libero_object.json',
                   '--lock', 'models/assets.lock.json',
                   '--instruction', task['instruction'], '--task-id', str(task_id),
                   '--steps-per-attempt', '200', '--max-attempts', '1',
                   '--seed', '42', '--init-state', '0', '--out', str(episode)]
        print(f'Recording task {task_id}: {task["instruction"]}', flush=True)
        with (out / f'task_{task_id}.log').open('w') as log:
            process = subprocess.run(command, cwd=ROOT, env=env, stdout=log,
                                     stderr=subprocess.STDOUT, check=False)
        result_path = episode / 'result.json'
        result = json.loads(result_path.read_text()) if result_path.is_file() else {}
        row = {'task_id': task_id, 'instruction': task['instruction'],
               'exit_code': process.returncode, 'success': result.get('success'),
               'reason': result.get('reason'), 'steps': result.get('steps'),
               'wall_seconds': result.get('wall_seconds'),
               'video_available': (episode / 'demo.mp4').is_file()}
        rows.append(row)
        (out / 'manifest.json').write_text(json.dumps({'schema_version': 1,
            'recording_method': 'explicit task ID; one SmolVLA episode per task',
            'seed': 42, 'init_state': 0, 'steps_per_attempt': 200,
            'max_attempts': 1, 'task_runs': rows}, ensure_ascii=False, indent=2) + '\n')
        print(f'Task {task_id}: exit={process.returncode}, success={row["success"]}, '
              f'video={row["video_available"]}', flush=True)
    print(f'Saved clips under {out}; review every result and video before publication.')


if __name__ == '__main__':
    main()
