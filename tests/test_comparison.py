import json
from pathlib import Path
import unittest

from cleanup_robot.comparison import normalize_minilm, score_case, summarize, validate_cases


ROOT = Path(__file__).resolve().parents[1]


class ComparisonTests(unittest.TestCase):
    def test_cases_are_fixed_to_real_catalog_tasks(self):
        catalog = json.loads((ROOT / 'tasks/libero_object.json').read_text())
        data = json.loads((ROOT / 'tasks/comparison_cases_qwen35.json').read_text())
        cases = validate_cases(data, catalog)
        self.assertEqual(len(cases), 24)
        self.assertEqual({c['expected_task_id'] for c in cases}, {None, *range(1, 10)})

    def test_ambiguous_execution_is_wrong_even_if_candidate_looks_plausible(self):
        case = {'expected_decision': 'clarify', 'expected_task_id': None}
        outcome = normalize_minilm({'accepted': True, 'task': {'task_id': 7},
                                    'score': .9, 'margin': .1, 'method': 'multilingual_embedding'})
        self.assertTrue(score_case(case, outcome)['wrong_execution'])
        held = normalize_minilm({'accepted': False, 'task': {'task_id': 7},
                                 'score': .5, 'margin': .01, 'method': 'multilingual_embedding'})
        self.assertTrue(score_case(case, held)['correct'])
        self.assertFalse(score_case(case, held)['clarification_question'])

    def test_wrong_task_and_hold_are_distinct(self):
        case = {'expected_decision': 'execute', 'expected_task_id': 9}
        self.assertTrue(score_case(case, {'decision': 'execute', 'task_id': 7})['wrong_execution'])
        self.assertFalse(score_case(case, {'decision': 'hold', 'task_id': None})['wrong_execution'])

    def test_summary_separates_kinds(self):
        rows = [{'method': 'qwen', 'kind': 'ambiguous', 'inference_seconds': 1.0,
                 'assessment': {'correct': True, 'wrong_execution': False,
                                'clarification_question': True, 'held': False}}]
        result = summarize(rows)['qwen']
        self.assertEqual(result['by_kind']['ambiguous']['correct'], 1)
        self.assertEqual(result['clarification_questions'], 1)

    def test_invalid_output_counts_in_denominator(self):
        case = {'expected_decision': 'execute', 'expected_task_id': 8}
        assessment = score_case(case, {'decision': 'invalid', 'task_id': None})
        rows = [{'method': 'qwen', 'kind': 'indirect', 'inference_seconds': None,
                 'assessment': assessment}]
        result = summarize(rows)['qwen']
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['correct'], 0)
        self.assertEqual(result['invalid'], 1)
        self.assertIsNone(result['median_inference_seconds'])


if __name__ == '__main__':
    unittest.main()
