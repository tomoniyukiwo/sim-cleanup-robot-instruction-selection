import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location(
    'build_physical_comparison_video', ROOT / 'scripts/build_physical_comparison_video.py')
video = importlib.util.module_from_spec(spec)
spec.loader.exec_module(video)


class PhysicalComparisonVideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.measured_run = ROOT / 'outputs/comparison/20261028T172007_51bd6b16'
        if cls.measured_run.is_dir():
            cls.cases, cls.rows, _, _ = video.load_run(
                cls.measured_run, ROOT / 'tasks/comparison_cases_qwen35.json',
                ROOT / 'tasks/libero_object.json')

    def test_indirect_subset_has_each_task_once_without_questions(self):
        if not self.measured_run.is_dir():
            self.skipTest('Measured run unavailable in public source package')
        cases = video.selected_cases(self.cases, self.rows)
        self.assertEqual([case['expected_task_id'] for case in cases], list(range(1, 10)))
        self.assertEqual(sum(self.rows[case['id'], 'qwen']['assessment']['correct'] for case in cases), 9)
        self.assertEqual(sum(self.rows[case['id'], 'minilm']['assessment']['correct'] for case in cases), 8)
        subtitle = video.case_subtitles(cases[0], self.rows,
                                        {'success': True, 'wall_seconds': 10.4}, 1)
        self.assertNotIn('確認質問', subtitle)
        self.assertIn('選択推論', subtitle)
        self.assertIn('共通のSmolVLA実行映像', subtitle)
        self.assertIn('共通のSmolVLA操作時間 10.4秒', subtitle)

    def test_missing_physical_clips_fail_before_render(self):
        if not self.measured_run.is_dir():
            self.skipTest('Measured run unavailable in public source package')
        cases = video.selected_cases(self.cases, self.rows)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'manifest.json').write_text(
                '{"recording_method":"explicit task ID; one SmolVLA episode per task",'
                '"task_runs":[]}')
            with self.assertRaises(FileNotFoundError):
                video.load_clips(root, cases)


if __name__ == '__main__':
    unittest.main()
