import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location(
    'build_ros_comparison_video', ROOT / 'scripts/build_ros_comparison_video.py')
video = importlib.util.module_from_spec(spec)
spec.loader.exec_module(video)


class ROSComparisonVideoTests(unittest.TestCase):
    def test_full_hd_layout_keeps_source_aspect(self):
        self.assertEqual((video.CANVAS_WIDTH, video.CANVAS_HEIGHT), (1920, 1080))
        self.assertEqual(video.CLIP_WIDTH * 640, video.CLIP_HEIGHT * 1024)
        self.assertLess(video.CLIP_X['left'] + video.CLIP_WIDTH,
                        video.CLIP_X['right'])
        self.assertLessEqual(video.CLIP_X['right'] + video.CLIP_WIDTH,
                             video.CANVAS_WIDTH)

    def fixture(self, root):
        cases = [{'id': f'indirect_{i}', 'kind': 'indirect',
                  'instruction': f'指示{i}', 'expected_task_id': i}
                 for i in range(1, 10)]
        cases_file = root / 'cases.json'
        cases_file.write_text(json.dumps({'cases': cases}))
        experiment = root / 'experiment'
        experiment.mkdir()
        rows = []
        for case in cases:
            for method in ('qwen', 'minilm'):
                task = case['expected_task_id']
                decision = 'hold' if method == 'minilm' and task == 4 else 'execute'
                request_id = f'{method}_{task}'
                run = root / 'outputs/ros' / request_id
                run.mkdir(parents=True)
                (run / 'request.json').write_text(json.dumps(
                    {'selector': method, 'instruction': case['instruction']}))
                (run / 'plan.json').write_text(json.dumps(
                    {'plan': {'decision': decision,
                              'task_id': task if decision == 'execute' else None}}))
                (run / 'result.json').write_text(json.dumps(
                    {'selector': method, 'success': decision == 'execute'}))
                if decision == 'execute':
                    (run / 'demo.mp4').write_bytes(b'video')
                rows.append({'method': method, 'case_id': case['id'],
                             'instruction': case['instruction'], 'expected_task_id': task,
                             'request_id': request_id, 'decision': decision,
                             'selected_task_id': task if decision == 'execute' else None,
                             'success': True if decision == 'execute' else None,
                             'planning_wall_seconds': 2.0,
                             'operation_wall_seconds': 10.0 if decision == 'execute' else None})
        (experiment / 'manifest.json').write_text(json.dumps(
            {'input_transport': 'ROS 2 /cleanup/instruction', 'runs': rows}))
        return experiment, cases_file, rows

    def test_independent_episodes_and_hold(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            experiment, cases_file, _ = self.fixture(root)
            with patch.object(video, 'ROOT', root):
                cases, rows, _ = video.load_rows(experiment, cases_file)
            self.assertEqual(len(cases), 9)
            self.assertIn('操作動画なし', video.subtitles(cases[3], rows, 4))
            self.assertIn('選択処理 2.0秒', video.subtitles(cases[0], rows, 1))
            self.assertIn('最大300ステップ', video.subtitles(cases[6], rows, 7, {'7': 300}))

    def test_reused_physical_episode_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            experiment, cases_file, rows = self.fixture(root)
            rows[1]['request_id'] = rows[0]['request_id']
            (experiment / 'manifest.json').write_text(json.dumps(
                {'input_transport': 'ROS 2 /cleanup/instruction', 'runs': rows}))
            with patch.object(video, 'ROOT', root):
                with self.assertRaises(ValueError):
                    video.load_rows(experiment, cases_file)


if __name__ == '__main__':
    unittest.main()
