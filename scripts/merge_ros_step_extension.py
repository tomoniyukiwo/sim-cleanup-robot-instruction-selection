"""Replace only task 7's 200-step ROS episodes with independent 300-step episodes."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid


ROOT = Path(__file__).resolve().parents[1]


def merge(base, extended):
    if base['input_transport'] != 'ROS 2 /cleanup/instruction' or extended['input_transport'] != base['input_transport']:
        raise ValueError('Both experiments must use ROS instruction input')
    if base['steps_per_attempt'] != 200 or extended['steps_per_attempt'] != 300:
        raise ValueError('Expected 200-step base and 300-step extension')
    if base['max_attempts'] != extended['max_attempts'] != 1:
        raise ValueError('Expected one attempt per episode')
    if base['seed'] != extended['seed'] or base['init_state'] != extended['init_state']:
        raise ValueError('Seed or initial state differs')
    if set(base['methods']) != set(extended['methods']) != {'qwen', 'minilm'}:
        raise ValueError('Expected both methods')
    if set(base['task_ids']) != set(range(1, 10)) or extended['task_ids'] != [7]:
        raise ValueError('Expected base tasks 1–9 and extension task 7')
    if len(base['runs']) != 18 or len(extended['runs']) != 2:
        raise ValueError('Unexpected episode count')
    base_rows = {(r['expected_task_id'], r['method']): r for r in base['runs']}
    new_rows = {(r['expected_task_id'], r['method']): r for r in extended['runs']}
    expected = {(task, method) for task in range(1, 10) for method in ('qwen', 'minilm')}
    if len(base_rows) != 18 or set(base_rows) != expected or set(new_rows) != {(7, 'qwen'), (7, 'minilm')}:
        raise ValueError('Duplicate or missing task/method episodes')
    for key, new in new_rows.items():
        old = base_rows[key]
        if new['case_id'] != old['case_id'] or new['instruction'] != old['instruction']:
            raise ValueError('Extension instruction differs from the fixed case')
        if new['request_id'] == old['request_id']:
            raise ValueError('Extension reused a ROS request')
    rows = [new_rows.get((r['expected_task_id'], r['method']), r) for r in base['runs']]
    if len({r['request_id'] for r in rows}) != 18:
        raise ValueError('ROS requests must remain independent')
    summary = {}
    for method in ('qwen', 'minilm'):
        group = [r for r in rows if r['method'] == method]
        summary[method] = {
            'requests': len(group),
            'correct_selection': sum(r['decision'] == 'execute' and r['selected_task_id'] == r['expected_task_id'] for r in group),
            'wrong_selection': sum(r['decision'] == 'execute' and r['selected_task_id'] != r['expected_task_id'] for r in group),
            'held_or_clarified': sum(r['decision'] != 'execute' for r in group),
            'physical_executions': sum(r['decision'] == 'execute' for r in group),
            'physical_goal_satisfied': sum(r['success'] is True for r in group),
            'end_to_end_success': sum(r['decision'] == 'execute' and r['selected_task_id'] == r['expected_task_id'] and r['success'] is True for r in group),
        }
    result = dict(base)
    result.pop('steps_per_attempt')
    result.pop('config')
    result['steps_per_attempt_by_task'] = {str(task): 300 if task == 7 else 200 for task in range(1, 10)}
    result['config_by_task'] = {str(task): extended['config'] if task == 7 else base['config'] for task in range(1, 10)}
    result['runs'] = rows
    result['summary'] = summary
    result['source_experiments'] = {'base_200': base.get('experiment_id'), 'task7_300': extended.get('experiment_id')}
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', type=Path, required=True)
    ap.add_argument('--extended', type=Path, required=True)
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    base = json.loads((args.base / 'manifest.json').read_text())
    extended = json.loads((args.extended / 'manifest.json').read_text())
    base['experiment_id'] = args.base.name
    extended['experiment_id'] = args.extended.name
    result = merge(base, extended)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = args.out or ROOT / 'outputs/ros_comparison' / f'{stamp}_{uuid.uuid4().hex[:8]}'
    out.mkdir(parents=True, exist_ok=False)
    (out / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(f'Saved {out}: 18 ROS requests; task 7 uses 300 steps')


if __name__ == '__main__':
    main()
