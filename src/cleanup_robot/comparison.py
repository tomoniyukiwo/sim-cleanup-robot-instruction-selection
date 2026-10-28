"""Selection-only comparison. No LIBERO backend or robot actions are imported."""
import gc
import hashlib
import json
import os
from pathlib import Path
import statistics
import time

from .planner import validate_plan


def validate_cases(data, catalog):
    if data.get('suite') != catalog.get('suite') or data.get('schema_version') != 1:
        raise ValueError('Case suite/schema mismatch')
    registered = {t['task_id']: t for t in catalog['tasks']}
    seen = set()
    for case in data['cases']:
        if case['id'] in seen:
            raise ValueError('Duplicate case id')
        seen.add(case['id'])
        if case['kind'] not in {'standard', 'indirect', 'ambiguous', 'reply'}:
            raise ValueError('Unknown case kind')
        if not isinstance(case['instruction'], str) or not case['instruction'].strip():
            raise ValueError('Empty instruction')
        if not isinstance(case['context'], list):
            raise ValueError('Context must be a list')
        if case['kind'] == 'reply' and not case['context']:
            raise ValueError('Reply must carry the preceding request')
        if case['kind'] != 'reply' and case['context']:
            raise ValueError('Only reply cases may carry context')
        expected = case['expected_decision']
        task_id = case['expected_task_id']
        if expected == 'execute' and task_id not in registered:
            raise ValueError('Expected task is not registered')
        if expected == 'clarify' and task_id is not None:
            raise ValueError('Clarify cannot select a task')
        if expected not in {'execute', 'clarify'}:
            raise ValueError('Unexpected reference decision')
        if case['kind'] == 'standard' and case['instruction'] != registered[task_id]['instruction']:
            raise ValueError('Standard instruction differs from catalog')
        if data.get('fewshot_task_id') is not None and task_id == data['fewshot_task_id']:
            raise ValueError('Few-shot task leaked into evaluation')
    if data.get('fewshot_task_id') is not None:
        held_out = set(registered) - {data['fewshot_task_id']}
        tested = {c['expected_task_id'] for c in data['cases'] if c['expected_task_id'] is not None}
        if tested != held_out:
            raise ValueError('Evaluation must cover every non-example task')
    return data['cases']


def normalize_qwen(plan):
    return {'decision': plan['decision'], 'task_id': plan['task_id'],
            'question': plan['message'] if plan['decision'] == 'clarify' else None,
            'retry_on_timeout': plan['retry_on_timeout']}


def normalize_minilm(route):
    # A rejected similarity match is a hold, not a generated question.
    return {'decision': 'execute' if route['accepted'] else 'hold',
            'task_id': route['task']['task_id'] if route['accepted'] else None,
            'question': None, 'score': route['score'], 'margin': route['margin'],
            'candidate_task_id': route['task']['task_id'], 'method': route['method']}


def score_case(case, outcome):
    expected = case['expected_decision']
    decision = outcome['decision']
    if expected == 'execute':
        correct = decision == 'execute' and outcome['task_id'] == case['expected_task_id']
        unsafe = decision == 'execute' and not correct
    else:
        correct = decision in {'clarify', 'hold'}
        unsafe = decision == 'execute'
    return {'correct': correct, 'wrong_execution': unsafe,
            'clarification_question': decision == 'clarify' and bool(outcome.get('question')),
            'held': decision == 'hold', 'invalid': decision == 'invalid'}


def summarize(rows):
    result = {}
    for method in sorted({r['method'] for r in rows}):
        subset = [r for r in rows if r['method'] == method]
        timings = [r['inference_seconds'] for r in subset if r.get('inference_seconds') is not None]
        result[method] = {'count': len(subset),
                          'correct': sum(r['assessment']['correct'] for r in subset),
                          'wrong_execution': sum(r['assessment']['wrong_execution'] for r in subset),
                          'clarification_questions': sum(r['assessment']['clarification_question'] for r in subset),
                          'held': sum(r['assessment']['held'] for r in subset),
                          'invalid': sum(r['assessment'].get('invalid', False) for r in subset),
                          'median_inference_seconds': statistics.median(timings) if timings else None}
        result[method]['by_kind'] = {
            kind: {'count': len(group), 'correct': sum(r['assessment']['correct'] for r in group),
                   'wrong_execution': sum(r['assessment']['wrong_execution'] for r in group)}
            for kind in sorted({r['kind'] for r in subset})
            for group in [[r for r in subset if r['kind'] == kind]]}
    return result


class QwenBridgeSession:
    def __init__(self, catalog, cfg, lock):
        from .planner_bridge import BridgeSession
        self.catalog = catalog
        self.bridge = BridgeSession(catalog, cfg, lock)
        self.load_seconds = self.bridge.load_seconds

    def infer(self, case):
        raw, seconds = self.bridge.infer(case['instruction'], case['context'])
        try:
            outcome = normalize_qwen(validate_plan(raw, self.catalog))
        except (ValueError, TypeError, KeyError) as exc:
            outcome = {'decision': 'invalid', 'task_id': None, 'question': None,
                       'validation_error': str(exc)}
        return outcome, seconds, raw

    def close(self):
        self.bridge.close()


class MiniLMSession:
    def __init__(self, catalog, cfg, lock):
        from .routing import Router
        start = time.perf_counter()
        self.router = Router(catalog, lock['embedding']['path'], cfg)
        self.load_seconds = time.perf_counter() - start

    def infer(self, case):
        # MiniLM has no dialogue state; concatenate the original request and reply.
        text = ' '.join([c['request'] for c in case['context']] + [case['instruction']])
        start = time.perf_counter()
        route = self.router.route(text)
        return normalize_minilm(route), time.perf_counter() - start, None

    def close(self):
        del self.router
        gc.collect()


def run_comparison(cases_path, catalog_path, config_path, lock_path, out, methods=('qwen', 'minilm')):
    cases_path, catalog_path = Path(cases_path), Path(catalog_path)
    catalog = json.loads(catalog_path.read_text())
    cases = validate_cases(json.loads(cases_path.read_text()), catalog)
    cfg = json.loads(Path(config_path).read_text())
    if cfg['suite'] != catalog['suite']:
        raise ValueError('Config/catalog suite mismatch')
    if cfg.get('planner_backend') != 'qwen35_bridge':
        raise ValueError('Comparison requires the Qwen3.5 bridge config')
    lock_path = Path(lock_path)
    if not lock_path.is_file():
        raise FileNotFoundError(f'Planner lock missing: {lock_path}. Run prepare-planner with --base-lock models/assets.lock.json first.')
    lock = json.loads(lock_path.read_text())
    if 'qwen' in methods and lock.get('planner', {}).get('repo') != cfg['planner_repo']:
        raise ValueError('Qwen3.5 model is not prepared in the selected lock; run prepare-planner first')
    fewshot_hash = None
    if cfg.get('planner_backend') == 'qwen35_bridge' and 'qwen' in methods:
        from .fewshot import load_examples
        root = Path(__file__).resolve().parents[2]
        fewshot_path = root / cfg['fewshot_path']
        examples = load_examples(fewshot_path, catalog)
        if any(case['instruction'] in {item['instruction'] for item in examples} for case in cases):
            raise ValueError('Few-shot example appears in evaluation instructions')
        if not all(case['expected_task_id'] != 0 for case in cases):
            raise ValueError('Task 0 appears in evaluation labels')
        fewshot_hash = hashlib.sha256(fewshot_path.read_bytes()).hexdigest()
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    meta = {'schema_version': 1, 'cases_sha256': hashlib.sha256(cases_path.read_bytes()).hexdigest(),
            'catalog_sha256': hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
            'methods': list(methods), 'model_revisions': {
                method: {key: lock[key]['revision'] for key in (['planner'] if method == 'qwen' else ['embedding'])}
                for method in methods},
            'model_repos': {'qwen': lock.get('planner', {}).get('repo'),
                            'minilm': lock.get('embedding', {}).get('repo')},
            'policy_revision': lock.get('policy', {}).get('revision'),
            'evaluation_task_ids': sorted({c['expected_task_id'] for c in cases
                                           if c['expected_task_id'] is not None}),
            'fewshot_task_id': 0 if fewshot_hash is not None else None,
            'timing_note': 'Model load and per-case inference measured separately. One sequential run; no speed generalization.',
            'physical_execution': False, 'fewshot_sha256': fewshot_hash,
            'planner_backend': cfg.get('planner_backend', 'qwen35_bridge')}
    (out / 'metadata.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    rows = []
    load_times = {}
    with (out / 'results.jsonl').open('x') as stream:
        for method in methods:
            session_type = QwenBridgeSession if method == 'qwen' else MiniLMSession
            session = session_type(catalog, cfg, lock)
            load_times[method] = session.load_seconds
            try:
                for case in cases:
                    try:
                        outcome, seconds, raw = session.infer(case)
                        row = {'case_id': case['id'], 'kind': case['kind'], 'method': method,
                               'instruction': case['instruction'], 'context': case['context'],
                               'expected_decision': case['expected_decision'],
                               'expected_task_id': case['expected_task_id'],
                               'outcome': outcome, 'inference_seconds': seconds,
                               'assessment': score_case(case, outcome)}
                        if raw is not None:
                            row['raw_output'] = raw
                    except Exception as exc:
                        row = {'case_id': case['id'], 'kind': case['kind'], 'method': method,
                               'instruction': case['instruction'], 'context': case['context'],
                               'expected_decision': case['expected_decision'],
                               'expected_task_id': case['expected_task_id'],
                               'outcome': {'decision': 'invalid', 'task_id': None, 'question': None},
                               'inference_seconds': None, 'error': repr(exc)}
                        row['assessment'] = score_case(case, row['outcome'])
                    stream.write(json.dumps(row, ensure_ascii=False) + '\n')
                    stream.flush()
                    rows.append(row)
                    print(method, case['id'], row.get('outcome', row.get('error')), flush=True)
            finally:
                session.close()
    summary = {'load_seconds': load_times, 'completed_cases': len(rows),
               'model_repos': meta['model_repos'], 'model_revisions': meta['model_revisions'],
               'policy_revision': meta['policy_revision'],
               'evaluation_task_ids': meta['evaluation_task_ids'],
               'fewshot_task_id': meta['fewshot_task_id'],
               'errors': [{'method': r['method'], 'case_id': r['case_id'], 'error': r['error']}
                          for r in rows if 'error' in r], 'metrics': summarize(rows)}
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary
