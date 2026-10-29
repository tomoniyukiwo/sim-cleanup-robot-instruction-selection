"""Export reviewed ROS comparison fields without local paths or raw logs."""
import argparse
import json
from pathlib import Path


def public_summary(manifest, lock):
    if manifest.get('input_transport') != 'ROS 2 /cleanup/instruction':
        raise ValueError('Expected ROS instruction input')
    rows = manifest['runs']
    keys = [(r['case_id'], r['method']) for r in rows]
    if len(rows) != 18 or len(set(keys)) != 18 or set(manifest['methods']) != {'qwen', 'minilm'}:
        raise ValueError('Expected nine unique cases for both methods')
    if len({r['request_id'] for r in rows}) != 18:
        raise ValueError('Physical episodes were reused')
    for method in ('qwen', 'minilm'):
        subset = [r for r in rows if r['method'] == method]
        if {r['expected_task_id'] for r in subset} != set(range(1, 10)):
            raise ValueError(f'Incomplete task coverage for {method}')
        measured = {
            'requests': len(subset),
            'correct_selection': sum(r['decision'] == 'execute' and
                                     r['selected_task_id'] == r['expected_task_id'] for r in subset),
            'wrong_selection': sum(r['decision'] == 'execute' and
                                   r['selected_task_id'] != r['expected_task_id'] for r in subset),
            'held_or_clarified': sum(r['decision'] != 'execute' for r in subset),
            'physical_executions': sum(r['decision'] == 'execute' for r in subset),
            'physical_goal_satisfied': sum(bool(r['success']) for r in subset),
            'end_to_end_success': sum(r['decision'] == 'execute' and
                                      r['selected_task_id'] == r['expected_task_id'] and
                                      r['success'] is True for r in subset),
        }
        if manifest['summary'].get(method) != measured:
            raise ValueError(f'Manifest summary differs from case results: {method}')
    safe_rows = [{key: row.get(key) for key in
                  ('method', 'case_id', 'expected_task_id', 'decision',
                   'selected_task_id', 'success', 'reason', 'steps',
                   'planning_wall_seconds', 'operation_wall_seconds')}
                 for row in rows]
    step_conditions = ({'steps_per_attempt_by_task': manifest['steps_per_attempt_by_task']}
                       if 'steps_per_attempt_by_task' in manifest else
                       {'steps_per_attempt': manifest['steps_per_attempt']})
    return {'schema_version': 1, 'input_transport': manifest['input_transport'],
            'model_revisions': {'qwen': lock['planner']['revision'],
                                'minilm': lock['embedding']['revision'],
                                'smolvla': lock['policy']['revision']},
            'conditions': {'seed': manifest['seed'], 'init_state': manifest['init_state'],
                           **step_conditions,
                           'max_attempts': manifest['max_attempts'],
                           'scene_reset_per_request': True},
            'summary': manifest['summary'], 'cases': safe_rows,
            'timing_note': 'Planning wall time includes model load; operation wall time excludes planning. Video follows simulation time.',
            'interpretation_note': 'Independent ROS requests and physical episodes per method; a held request has no physical execution.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--experiment', type=Path, required=True)
    ap.add_argument('--lock', type=Path, default=Path('models/assets.qwen35.lock.json'))
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    manifest = json.loads((args.experiment / 'manifest.json').read_text())
    lock = json.loads(args.lock.read_text())
    data = public_summary(manifest, lock)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(f'Saved {args.out}; review before publication.')


if __name__ == '__main__':
    main()
