import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_comparison_video', ROOT / 'scripts/build_comparison_video.py')
video = importlib.util.module_from_spec(spec)
spec.loader.exec_module(video)


class ComparisonVideoTests(unittest.TestCase):
    def test_each_case_shows_both_methods_in_same_interval(self):
        run = ROOT / 'outputs/comparison/20261028T172007_51bd6b16'
        if not run.is_dir():
            self.skipTest('Measured local run unavailable in public source package')
        cases, rows, summary, _ = video.load_run(
            run, ROOT / 'tasks/comparison_cases_qwen35.json',
            ROOT / 'tasks/libero_object.json')
        subtitles, seconds = video.make_ass(cases, rows, summary)
        self.assertEqual(seconds, 132)
        self.assertIn('Qwen3.5  22/24', subtitles)
        self.assertIn('MiniLM  21/24', subtitles)
        # First case: both method headings and their outcomes share 0:00:04–0:00:09.
        interval = '0:00:04.00,0:00:09.00'
        first_case = [line for line in subtitles.splitlines() if interval in line]
        self.assertTrue(any('Qwen3.5-2B' in line for line in first_case))
        self.assertTrue(any('多言語MiniLM' in line for line in first_case))
        self.assertTrue(any('実行  task 1' in line for line in first_case))
        self.assertEqual(len([line for line in subtitles.splitlines() if '表示を同期。実際の推論は順番に実行。' in line]), 24)

    def test_duplicate_or_missing_result_is_rejected(self):
        run = ROOT / 'outputs/comparison/20261028T172007_51bd6b16'
        if not run.is_dir():
            self.skipTest('Measured local run unavailable in public source package')
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as folder:
            target = Path(folder)
            for name in ['metadata.json', 'summary.json', 'results.jsonl']:
                (target / name).write_bytes((run / name).read_bytes())
            rows = (target / 'results.jsonl').read_text().splitlines()
            (target / 'results.jsonl').write_text('\n'.join(rows[:-1]) + '\n')
            with self.assertRaises(ValueError):
                video.load_run(target, ROOT / 'tasks/comparison_cases_qwen35.json',
                               ROOT / 'tasks/libero_object.json')


if __name__ == '__main__':
    unittest.main()
