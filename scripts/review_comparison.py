"""Recount a saved comparison, treating rejected model output as an invalid case."""
import argparse
import hashlib
import json
from pathlib import Path

from cleanup_robot.comparison import score_case, summarize, validate_cases


def review(run, cases_path, catalog_path):
    run, cases_path, catalog_path = Path(run), Path(cases_path), Path(catalog_path)
    metadata = json.loads((run / 'metadata.json').read_text())
    for path, key in [(cases_path, 'cases_sha256'), (catalog_path, 'catalog_sha256')]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != metadata[key]:
            raise ValueError(f'{path} differs from the version used for this run')
    cases = validate_cases(json.loads(cases_path.read_text()), json.loads(catalog_path.read_text()))
    expected = {c['id']: c for c in cases}
    rows = []
    for line in (run / 'results.jsonl').read_text().splitlines():
        row = json.loads(line)
        case = expected[row['case_id']]
        if 'assessment' not in row:
            row['outcome'] = {'decision': 'invalid', 'task_id': None, 'question': None}
            row['assessment'] = score_case(case, row['outcome'])
            row['inference_seconds'] = None
        rows.append(row)
    for method in metadata['methods']:
        ids = [r['case_id'] for r in rows if r['method'] == method]
        if sorted(ids) != sorted(expected):
            raise ValueError(f'{method}: missing or duplicate cases')
    prior = json.loads((run / 'summary.json').read_text())
    return {'schema_version': 1, 'source_run': run.name,
            'review_note': 'Original files preserved. Rejected planner output counted as invalid and incorrect; no inference time was recorded for that case.',
            'load_seconds': prior['load_seconds'], 'errors': prior['errors'],
            'model_repos': metadata.get('model_repos', {}),
            'model_revisions': metadata.get('model_revisions', {}),
            'policy_revision': metadata.get('policy_revision'),
            'evaluation_task_ids': metadata.get('evaluation_task_ids', []),
            'fewshot_task_id': metadata.get('fewshot_task_id'),
            'completed_cases': len(rows), 'metrics': summarize(rows)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--cases', type=Path, default=Path('tasks/comparison_cases_qwen35.json'))
    ap.add_argument('--catalog', type=Path, default=Path('tasks/libero_object.json'))
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    result = review(args.run, args.cases, args.catalog)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(f'Saved {args.out}')


if __name__ == '__main__':
    main()
