import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('merge_ros_step_extension', ROOT / 'scripts/merge_ros_step_extension.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def row(task, method, request):
    return {'expected_task_id': task, 'method': method, 'request_id': request,
            'case_id': f'case_{task}', 'instruction': f'instruction {task}',
            'decision': 'execute', 'selected_task_id': task, 'success': task != 7}


class MergeStepExtensionTests(unittest.TestCase):
    def setUp(self):
        common = {'input_transport': 'ROS 2 /cleanup/instruction', 'methods': ['qwen', 'minilm'],
                  'seed': 42, 'init_state': 0, 'max_attempts': 1}
        self.base = dict(common, steps_per_attempt=200, task_ids=list(range(1, 10)),
                         config='configs/ros_comparison.json',
                         runs=[row(task, method, f'old_{task}_{method}')
                               for task in range(1, 10) for method in ('qwen', 'minilm')])
        self.extended = dict(common, steps_per_attempt=300, task_ids=[7],
                             config='configs/ros_comparison_300.json',
                             runs=[dict(row(7, method, f'new_7_{method}'), success=True)
                                   for method in ('qwen', 'minilm')])

    def test_replaces_only_task7_and_records_mixed_budgets(self):
        result = module.merge(self.base, self.extended)
        self.assertEqual(result['steps_per_attempt_by_task']['7'], 300)
        self.assertEqual(result['steps_per_attempt_by_task']['6'], 200)
        self.assertEqual(result['summary']['qwen']['physical_goal_satisfied'], 9)
        self.assertEqual(result['summary']['minilm']['physical_goal_satisfied'], 9)
        self.assertEqual(len(result['runs']), 18)
        self.assertEqual([r['request_id'] for r in result['runs'] if r['expected_task_id'] == 7],
                         ['new_7_qwen', 'new_7_minilm'])

    def test_rejects_changed_instruction(self):
        self.extended['runs'][0]['instruction'] = 'different'
        with self.assertRaisesRegex(ValueError, 'instruction differs'):
            module.merge(self.base, self.extended)


if __name__ == '__main__':
    unittest.main()
