"""Create an editable Word draft with standard library only; never replace an existing file."""
import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape
import zipfile


def paragraph(text, style=None):
    props = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ''
    runs = ''.join(f'<w:r><w:t xml:space="preserve">{escape(line)}</w:t></w:r>'
                   for line in str(text).split('\n'))
    return f'<w:p>{props}{runs}</w:p>'


def build(data, summary=None, planner_repo_override=None, ros_experiment=None, video_info=None):
    parts = []
    planner_repo = (summary or {}).get('model_repos', {}).get('qwen') or planner_repo_override or 'Qwen/Qwen3.5-2B'
    qwen35 = planner_repo == 'Qwen/Qwen3.5-2B'
    def add(text, style=None):
        parts.append(paragraph(text, style))
    add('Physical AI 応用1 最終課題', 'Title')
    add('シミュレーション片付けロボットにおけるローカルLLMと類似度検索の指示選択比較', 'Heading1')
    add('提出者（OmniCampus名またはID）：' + data['account'])
    add('GitHub：' + data['github_url'])
    add('YouTube：' + data['youtube_url'])
    add('1. 目的・構成', 'Heading1')
    add('自然言語の依頼を登録済みのLIBEROタスクへ対応付け、MuJoCoのロボットアームで実行する。実機、外部推論API、独自の追加学習は使用しない。各リクエストでシーンを初期化する。')
    add(f'{planner_repo}は指示とタスク一覧のテキストだけを読み、実行・確認質問・拒否をJSONで返す。ROS 2 Humbleが指示受付と実行監視を担う。SmolVLAは選択後の英語標準指示、画像、状態から操作を推論する。目標達成はLIBEROの述語で判定する。')
    add('2. 実験条件', 'Heading1')
    revision_note = data['model_revisions']
    if qwen35:
        revision = (summary or {}).get('model_revisions', {}).get('qwen', {}).get('planner', '未取得')
        revision_note = ('Qwen3.5: ' + revision +
                         ' / SmolVLA: ' + str((summary or {}).get('policy_revision', '既存実行の記録を参照')))
    add('Ubuntu 22.04.5 LTS、RTX 4060 Ti 16GB、AI用Python 3.12.12、ROS 2 Humble。モデルrevision：' + revision_note)
    if qwen35:
        ids = (summary or {}).get('evaluation_task_ids', list(range(1, 10)))
        add(f'task 0の2例のみをfew-shotとして提示し、task {ids}を評価する。標準・遠回し・情報不足・補足を事前固定し、Qwen3.5と多言語MiniLMの登録タスク選択を比較する。MiniLMはLLM以外のAIであり、実行保留は確認質問とは別に記録する。')
    add('選択の正誤、誤実行判断、確認質問／保留、補足後の選択を比較し、操作成功とは分けて示す。')
    add('3. 物理実行', 'Heading1')
    if ros_experiment:
        if ros_experiment.get('input_transport') != 'ROS 2 /cleanup/instruction':
            raise ValueError('Physical comparison must use ROS instruction input')
        add('遠回しな指示9件をROS 2の/cleanup/instructionへモデルごとに送信し、選択結果からSmolVLAを独立に実行した。各回でシーンを初期化した。')
        add('入力：固定した日本語の遠回しな指示。操作モデルには選択タスクの英語標準指示を渡した。')
        budgets = ros_experiment.get('steps_per_attempt_by_task')
        step_text = ('task 7は最大300ステップ、他のtaskは最大200ステップ'
                     if budgets and budgets.get('7') == 300 else
                     f'最大{ros_experiment.get("steps_per_attempt", 200)}ステップ')
        add(f'実行条件：seed 42、初期状態0、{step_text}、1試行。Qwen3.5とMiniLMは別々のROSリクエストとして実行。')
        for method, label in (('qwen','Qwen3.5'),('minilm','MiniLM')):
            result=ros_experiment['summary'][method]
            add(f'{label}: 正選択 {result["correct_selection"]}/{result["requests"]}、誤選択 {result["wrong_selection"]}、確認・保留 {result["held_or_clarified"]}、物理試行 {result["physical_executions"]}、LIBERO目標達成 {result["physical_goal_satisfied"]}、正選択からの目標達成 {result["end_to_end_success"]}/{result["requests"]}。')
        failures=[f'{row["method"]} task {row["expected_task_id"]}（{row["reason"]}）'
                  for row in ros_experiment['runs'] if row['decision']=='execute' and not row['success']]
        if failures:
            add('目標未達：'+'、'.join(failures)+'。')
        add('選択処理の実時間にはモデル読み込みを含む。操作映像はシミュレーション時間で保存した。')
    else:
        add(data['result_note'])
        add('入力：' + data['input_instruction'])
        add('実行条件：' + data['conditions'])
        add('判定：' + data['result'])
        add('物理実行は登録済みtask_idを明示した共通のSmolVLA試行で撮影。Qwen3.5とMiniLMがそれぞれ独立に操作を成功させた結果ではない。ROS統合経路での物理実行は未測定。')
    add('4. 指示選択の比較結果', 'Heading1')
    if summary and summary.get('metrics'):
        for method, metrics in summary.get('metrics', {}).items():
            median = metrics['median_inference_seconds']
            median_text = f'{median:.3f}秒' if median is not None else '未測定'
            add(f'{method}: 正答 {metrics["correct"]}/{metrics["count"]}、誤実行判断 {metrics["wrong_execution"]}、確認質問 {metrics["clarification_questions"]}、保留 {metrics["held"]}、無効出力・推論エラー {metrics.get("invalid", 0)}、推論中央値 {median_text}。モデル読み込み {summary["load_seconds"][method]:.3f}秒。')
            add('条件別正答：' + '、'.join(
                f'{kind} {value["correct"]}/{value["count"]}'
                for kind, value in metrics['by_kind'].items()))
        if summary.get('errors'):
            add('評価エラー：' + str(summary['errors']))
        add('結果は1回の逐次測定であり、速度差の一般化には反復が必要。補足ケースの質問文は比較用に固定した文で、実際のQwenとの対話結果とは区別する。')
        if qwen35 and ros_experiment:
            add('比較動画は確認質問を含めず、task 1〜9のROS入力と判断、各モデルから独立に行った操作映像・LIBERO目標判定を左右並列に示す（約2分）。保留した場合は操作動画を表示しない。')
            if video_info:
                canvas = video_info['resolution']
                panel = video_info['task_panel_resolution']
                source = video_info['source_resolution']
                add(f'動画は横{canvas["width"]}×縦{canvas["height"]}。元映像は{source["width"]}×{source["height"]}で、縦横比を保持して各枠{panel["width"]}×{panel["height"]}に表示した。')
        elif qwen35:
            add('比較動画は確認質問を含めず、task 1〜9の遠回しな指示を左右並列に示す（約2分）。モデル名・選択推論時間・共通の操作時間を映像枠の上に置き、実測したLIBERO操作映像を枠内に置いた。同じSmolVLA試行の映像を両側に再掲し、task 4のMiniLM保留では操作映像を表示しない。物理操作は9件中8件で目標達成、task 7は200ステップで未達。')
    else:
        add('未測定。実行結果が得られたら scripts/build_docx.py の --summary に比較出力を渡して更新する。')
    add('5. 限界と考察', 'Heading1')
    add('Qwenは画像や物体位置を見ていない。登録外タスクや未知の物体には適用していない。曖昧な指示でタスクを推測して操作することは成功扱いにしない。')
    if ros_experiment:
        add('各モデルの操作を別のROSリクエストで実行し、保留を操作失敗とは区別した。停止・再開と再試行の効果は未検証。')
    else:
        add('選択方法が同じ標準指示へ到達した場合、同じ物理操作の結果を両方法の独立した成功例として数えない。')
        add(data['extra_checks'])
    add('再試行は追加学習や失敗原因の診断ではなく、現在状態からの再推論。実機、Gazebo、Genesisは使用していない。')
    add('6. 外部資源・自作部分', 'Heading1')
    add('Qwen、SmolVLA、LeRobot、LIBERO、ROS 2、MuJoCoは公開資源を利用。自作部分は登録タスク選択の検査、ROS監視とプロセス間通信、実行記録と比較集計。コードと資料の作成にはChatGPT/Codexを利用した。')
    add('参照：https://huggingface.co/Qwen/Qwen3.5-2B  https://huggingface.co/lerobot/smolvla_libero  https://github.com/huggingface/lerobot  https://github.com/Lifelong-Robot-Learning/LIBERO')
    add('公開commit：' + data['git_commit'])
    body = ''.join(parts)
    document = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + body + '<w:sectPr/></w:body></w:document>'
    content_types = '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
    rels = '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'
    return {'[Content_Types].xml': content_types, '_rels/.rels': rels, 'word/document.xml': document}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data', type=Path, default=Path('submission/report_data.json'))
    ap.add_argument('--summary', type=Path)
    ap.add_argument('--ros-experiment', type=Path, help='Manifest of independent ROS-triggered episodes')
    ap.add_argument('--video-manifest', type=Path, help='Rendered comparison video metadata')
    ap.add_argument('--config', type=Path, help='Use this planner model for an unmeasured draft')
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    data = json.loads(args.data.read_text())
    summary = json.loads(args.summary.read_text()) if args.summary else None
    ros_experiment = json.loads(args.ros_experiment.read_text()) if args.ros_experiment else None
    video_info = json.loads(args.video_manifest.read_text()) if args.video_manifest else None
    model = json.loads(args.config.read_text())['planner_repo'] if args.config else None
    if model and summary and summary.get('model_repos', {}).get('qwen') not in (None, model):
        ap.error('Config and summary planner models differ')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.out, 'x', zipfile.ZIP_DEFLATED) as archive:
        for name, content in build(data, summary, model, ros_experiment, video_info).items():
            archive.writestr(name, content)
    print(f'Saved editable draft: {args.out}')


if __name__ == '__main__':
    main()
