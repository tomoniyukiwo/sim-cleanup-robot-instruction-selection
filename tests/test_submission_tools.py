import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SubmissionToolsTests(unittest.TestCase):
    def test_existing_package_gets_a_new_name(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as folder:
            base = Path(folder) / 'public.zip'
            base.write_bytes(b'original')
            candidate = script('build_public_release').available_output(base)
            self.assertEqual(candidate.name, 'public_1.zip')
            candidate.write_bytes(b'new')
            self.assertEqual(script('build_public_release').available_output(base).name, 'public_2.zip')
            self.assertEqual(base.read_bytes(), b'original')

    def test_summary_omits_paths_and_unknown_fields(self):
        result = {'success': True, 'reason': 'environment_goal_satisfied',
                  'request': {'instruction': 'put can in basket', 'config': '/private/config'},
                  'assets': {'policy': {'repo': 'lerobot/smolvla_libero', 'revision': 'abc', 'path': '/private/model'}},
                  'exception': 'private-token', 'config': {'device': '/private/device'},
                  'plan': {'task_id': 0, 'task': {'instruction': 'put can in basket'}}}
        exported = script('export_run_summary').summarize(result)
        encoded = json.dumps(exported)
        self.assertNotIn('/private', encoded)
        self.assertNotIn('private-token', encoded)
        self.assertIs(exported['success'], True)
        self.assertEqual(exported['models']['policy']['revision'], 'abc')

    def test_public_package_excludes_runtime_and_media(self):
        include = script('build_public_release').included
        for path in ['models/assets.lock.json', '.env', '.venv-uv/lib/secrets.py',
                     'outputs/ros/id/result.json', 'examples/demo.mp4',
                     'src/cleanup_robot/__pycache__/test.py', 'submission/report_qwen35_pending.docx',
                     'evidence/private.json']:
            with self.subTest(path=path):
                self.assertFalse(include(path))
        for path in ['README.md', '.gitignore', 'uv.lock', 'ros/supervisor.py',
                     'scripts/build_report.py', 'docs/REPORT_TEMPLATE.md', 'evidence/README.md',
                     'tasks/libero_object.json',
                     'tasks/comparison_cases_qwen35.json', 'tasks/fewshot_task0.json',
                     'planner_env/pyproject.toml', 'planner_env/runner.py',
                     'src/cleanup_robot/comparison.py', 'scripts/compare_selection.py']:
            self.assertTrue(include(path))


if __name__ == '__main__':
    unittest.main()
