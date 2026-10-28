"""Extract selected result fields for publication; never copy raw logs or paths."""
import argparse
import json
from pathlib import Path


def summarize(result):
    request = result.get('request', {})
    plan = result.get('plan', {})
    task = plan.get('task', {})
    cfg = result.get('config', {})
    models = {}
    for role in ('planner', 'policy', 'tokenizer', 'embedding', 'environment_assets'):
        entry = result.get('assets', {}).get(role)
        if isinstance(entry, dict):
            models[role] = {k: entry[k] for k in ('repo', 'revision') if k in entry}
    return {
        'schema_version': 1,
        'record_type': 'exported_runtime_result_not_independent_verification',
        'instruction': request.get('instruction'),
        'task_id': plan.get('task_id'),
        'canonical_instruction': task.get('instruction'),
        'planner_decision': plan.get('decision'),
        'seed': request.get('seed'), 'init_state': request.get('init_state'),
        'success': result.get('success'), 'reason': result.get('reason'),
        'steps': result.get('steps'), 'attempts': result.get('attempts'),
        'control_loop_wall_seconds': result.get('wall_seconds'),
        'timing_note': 'Control loop only; excludes planner and executor model loading.',
        'success_source': result.get('success_source'),
        'catalog_sha256': result.get('catalog_sha256'),
        'parameters': {k: cfg[k] for k in ('suite', 'steps_per_attempt', 'max_attempts',
                        'n_action_steps', 'playback_speed', 'video_fps') if k in cfg},
        'models': models,
        'events_observed': sorted({e['event'] for e in result.get('events', [])
                                   if isinstance(e, dict) and isinstance(e.get('event'), str)}),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    source = args.run / 'result.json'
    summary = summarize(json.loads(source.read_text()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(f'Saved {args.out}. Review instruction text before publication.')
    print('This exports a recorded result; it does not independently validate success.')


if __name__ == '__main__':
    main()
