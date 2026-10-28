import json
from pathlib import Path
import unittest
from unittest.mock import patch

from cleanup_robot.comparison import validate_cases
from cleanup_robot.fewshot import build_messages, load_examples
from cleanup_robot.planner import plan_local


ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / 'tasks/libero_object.json').read_text())


class Qwen35FewshotTests(unittest.TestCase):
    def test_examples_are_task_zero_only(self):
        examples = load_examples(ROOT / 'tasks/fewshot_task0.json', CATALOG)
        self.assertEqual(len(examples), 2)
        self.assertTrue(all(e['answer']['task_id'] == 0 for e in examples))
        self.assertEqual(examples[0]['instruction'], CATALOG['tasks'][0]['instruction'])

    def test_all_other_tasks_are_held_out_and_covered(self):
        data = json.loads((ROOT / 'tasks/comparison_cases_qwen35.json').read_text())
        cases = validate_cases(data, CATALOG)
        self.assertEqual({c['expected_task_id'] for c in cases if c['expected_task_id'] is not None}, set(range(1, 10)))
        examples = load_examples(ROOT / 'tasks/fewshot_task0.json', CATALOG)
        self.assertFalse({e['instruction'] for e in examples} & {c['instruction'] for c in cases})

    def test_prompt_order_and_answer_visibility(self):
        examples = load_examples(ROOT / 'tasks/fewshot_task0.json', CATALOG)
        messages = build_messages('牛乳をかごへ', [], CATALOG, examples)
        self.assertEqual([m['role'] for m in messages], ['system', 'user', 'assistant', 'user', 'assistant', 'user'])
        self.assertEqual(json.loads(messages[-1]['content'])['request'], '牛乳をかごへ')
        self.assertEqual(json.loads(messages[2]['content'])['task_id'], 0)

    def test_planner_dispatches_to_separate_environment(self):
        with patch('cleanup_robot.planner_bridge.plan_via_bridge', return_value=('plan', 'raw')) as bridge:
            result = plan_local('test', [], CATALOG, {'planner_backend': 'qwen35_bridge'}, {})
        self.assertEqual(result, ('plan', 'raw'))
        bridge.assert_called_once()


if __name__ == '__main__':
    unittest.main()
