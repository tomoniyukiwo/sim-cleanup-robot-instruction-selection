import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'export_ros_comparison', ROOT / 'scripts/export_ros_comparison.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ExportROSComparisonTests(unittest.TestCase):
    def test_export_removes_request_ids_instructions_and_paths(self):
        rows = []
        for method in ('qwen', 'minilm'):
            for task in range(1, 10):
                rows.append({'method': method, 'case_id': f'indirect_{task}',
                             'expected_task_id': task, 'request_id': f'{method}_{task}',
                             'instruction': 'private instruction',
                             'decision': 'execute', 'selected_task_id': task,
                             'success': True, 'reason': 'environment_goal_satisfied',
                             'steps': 10, 'planning_wall_seconds': 1.0,
                             'operation_wall_seconds': 2.0,
                             'local_path': '/home/private/model'})
        manifest = {'input_transport': 'ROS 2 /cleanup/instruction',
                    'methods': ['qwen', 'minilm'], 'seed': 42, 'init_state': 0,
                    'steps_per_attempt': 200, 'max_attempts': 1,
                    'summary': {method: {'requests': 9, 'correct_selection': 9,
                              'wrong_selection': 0, 'held_or_clarified': 0,
                              'physical_executions': 9, 'physical_goal_satisfied': 9,
                              'end_to_end_success': 9}
                                for method in ('qwen', 'minilm')}, 'runs': rows}
        lock = {'planner': {'revision': 'q'}, 'embedding': {'revision': 'm'},
                'policy': {'revision': 's'}}
        exported = module.public_summary(manifest, lock)
        text = str(exported)
        self.assertNotIn('private instruction', text)
        self.assertNotIn('/home/private', text)
        self.assertNotIn('request_id', text)
        self.assertEqual(len(exported['cases']), 18)

    def test_export_records_mixed_step_budgets(self):
        rows = []
        for method in ('qwen', 'minilm'):
            for task in range(1, 10):
                rows.append({'method': method, 'case_id': f'case_{task}',
                             'expected_task_id': task, 'request_id': f'{method}_{task}',
                             'decision': 'execute', 'selected_task_id': task,
                             'success': True})
        summary = {method: {'requests': 9, 'correct_selection': 9,
                   'wrong_selection': 0, 'held_or_clarified': 0,
                   'physical_executions': 9, 'physical_goal_satisfied': 9,
                   'end_to_end_success': 9} for method in ('qwen', 'minilm')}
        manifest = {'input_transport': 'ROS 2 /cleanup/instruction', 'methods': ['qwen', 'minilm'],
                    'seed': 42, 'init_state': 0, 'max_attempts': 1,
                    'steps_per_attempt_by_task': {str(i): 300 if i == 7 else 200 for i in range(1, 10)},
                    'summary': summary, 'runs': rows}
        lock = {'planner': {'revision': 'q'}, 'embedding': {'revision': 'm'},
                'policy': {'revision': 's'}}
        exported = module.public_summary(manifest, lock)
        self.assertEqual(exported['conditions']['steps_per_attempt_by_task']['7'], 300)
        self.assertNotIn('steps_per_attempt', exported['conditions'])


if __name__ == '__main__':
    unittest.main()
