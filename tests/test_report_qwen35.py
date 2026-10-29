import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_docx', ROOT / 'scripts/build_docx.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Qwen35ReportTests(unittest.TestCase):
    def test_unmeasured_draft_does_not_claim_new_results(self):
        data = json.loads((ROOT / 'submission/report_data.json').read_text())
        document = module.build(data, planner_repo_override='Qwen/Qwen3.5-2B')['word/document.xml']
        self.assertIn('Qwen3.5: 未取得', document)
        self.assertIn('未測定。実行結果が得られたら', document)
        self.assertIn('ROS統合経路での物理実行は未測定', document)

    def test_new_model_label_and_held_out_tasks(self):
        data = json.loads((ROOT / 'submission/report_data.json').read_text())
        summary = {'model_repos': {'qwen': 'Qwen/Qwen3.5-2B'},
                   'model_revisions': {'qwen': {'planner': 'new-revision'}},
                   'policy_revision': 'old-policy',
                   'evaluation_task_ids': list(range(1, 10)),
                   'metrics': {}, 'errors': []}
        document = module.build(data, summary)['word/document.xml']
        self.assertIn('Qwen/Qwen3.5-2B', document)
        self.assertIn('task 0の2例のみ', document)
        self.assertIn('ROS統合経路での物理実行は未測定', document)
        self.assertIn('new-revision', document)

    def test_shared_physical_video_does_not_double_count_results(self):
        data = json.loads((ROOT / 'submission/report_data.json').read_text())
        summary = {'model_repos': {'qwen': 'Qwen/Qwen3.5-2B'},
                   'model_revisions': {'qwen': {'planner': 'revision'}},
                   'metrics': {'qwen': {'correct': 1, 'count': 1, 'wrong_execution': 0,
                                        'clarification_questions': 0, 'held': 0,
                                        'median_inference_seconds': 1.0, 'by_kind': {}},
                               'minilm': {'correct': 1, 'count': 1, 'wrong_execution': 0,
                                          'clarification_questions': 0, 'held': 0,
                                          'median_inference_seconds': 1.0, 'by_kind': {}}},
                   'load_seconds': {'qwen': 1.0, 'minilm': 1.0}}
        document = module.build(data, summary)['word/document.xml']
        self.assertIn('task 1〜9の遠回しな指示', document)
        self.assertIn('同じSmolVLA試行の映像を両側に再掲', document)
        self.assertIn('task 7は200ステップで未達', document)

    def test_ros_experiment_reports_independent_physical_results(self):
        data = json.loads((ROOT / 'submission/report_data.json').read_text())
        selection = {'correct': 1, 'count': 1, 'wrong_execution': 0,
                     'clarification_questions': 0, 'held': 0,
                     'median_inference_seconds': 1.0, 'by_kind': {}}
        summary = {'model_repos': {'qwen': 'Qwen/Qwen3.5-2B'},
                   'model_revisions': {'qwen': {'planner': 'revision'}},
                   'metrics': {'qwen': selection, 'minilm': selection},
                   'load_seconds': {'qwen': 1.0, 'minilm': 1.0}, 'errors': []}
        metrics = {'requests': 9, 'correct_selection': 9, 'wrong_selection': 0,
                   'held_or_clarified': 0, 'physical_executions': 9,
                   'physical_goal_satisfied': 8, 'end_to_end_success': 8}
        ros = {'input_transport': 'ROS 2 /cleanup/instruction',
               'summary': {'qwen': metrics, 'minilm': metrics}, 'runs': []}
        document = module.build(data, summary, ros_experiment=ros)['word/document.xml']
        self.assertIn('別々のROSリクエストとして実行', document)
        self.assertIn('各モデルから独立に行った操作映像', document)
        self.assertNotIn('同じSmolVLA試行の映像を両側に再掲', document)
        self.assertNotIn('ROS統合経路での物理実行は未測定', document)

    def test_ros_experiment_reports_task7_extended_budget(self):
        data = json.loads((ROOT / 'submission/report_data.json').read_text())
        metrics = {'requests': 9, 'correct_selection': 9, 'wrong_selection': 0,
                   'held_or_clarified': 0, 'physical_executions': 9,
                   'physical_goal_satisfied': 8, 'end_to_end_success': 8}
        ros = {'input_transport': 'ROS 2 /cleanup/instruction',
               'steps_per_attempt_by_task': {str(i): 300 if i == 7 else 200 for i in range(1, 10)},
               'summary': {'qwen': metrics, 'minilm': metrics}, 'runs': []}
        document = module.build(data, planner_repo_override='Qwen/Qwen3.5-2B',
                                ros_experiment=ros)['word/document.xml']
        self.assertIn('task 7は最大300ステップ、他のtaskは最大200ステップ', document)


if __name__ == '__main__':
    unittest.main()
