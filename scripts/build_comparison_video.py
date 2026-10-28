"""Render a synchronized, side-by-side selection comparison from one measured run."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import unicodedata
import uuid


ROOT = Path(__file__).resolve().parents[1]
KINDS = {'standard': '標準指示', 'indirect': '遠回しな指示',
         'ambiguous': '情報不足', 'reply': '補足指示'}


def ass_escape(value):
    return str(value).replace('\\', '＼').replace('{', '｛').replace('}', '｝').replace('\n', r'\N')


def wrap_text(value, width=55):
    lines, line, length = [], '', 0
    for char in str(value):
        size = 2 if unicodedata.east_asian_width(char) in {'F', 'W'} else 1
        if line and length + size > width:
            lines.append(line)
            line, length = '', 0
        line += char
        length += size
    if line:
        lines.append(line)
    return '\n'.join(lines)


def timestamp(seconds):
    centiseconds = round(seconds * 100)
    hours, rem = divmod(centiseconds, 360000)
    minutes, rem = divmod(rem, 6000)
    whole, cents = divmod(rem, 100)
    return f'{hours}:{minutes:02}:{whole:02}.{cents:02}'


def event(start, end, style, x, y, value):
    return (f'Dialogue: 0,{timestamp(start)},{timestamp(end)},{style},,0,0,0,,'
            f'{{\\an8\\pos({x},{y})}}{ass_escape(value)}')


def outcome_text(row):
    result = row['outcome']
    decision = result['decision']
    if decision == 'execute':
        label = f'実行  task {result["task_id"]}'
    else:
        label = {'clarify': '確認質問', 'hold': '保留', 'reject': '拒否',
                 'invalid': '無効出力'}.get(decision, decision)
    status = '正答' if row['assessment']['correct'] else '誤答'
    return label, status


def load_run(run, cases_path, catalog_path):
    metadata = json.loads((run / 'metadata.json').read_text())
    summary = json.loads((run / 'summary.json').read_text())
    cases_data = json.loads(cases_path.read_text())
    for path, key in ((cases_path, 'cases_sha256'), (catalog_path, 'catalog_sha256')):
        if hashlib.sha256(path.read_bytes()).hexdigest() != metadata[key]:
            raise ValueError(f'{path} differs from the recorded experiment')
    if metadata['model_repos']['qwen'] != 'Qwen/Qwen3.5-2B':
        raise ValueError('This video requires a measured Qwen3.5 comparison')
    cases = cases_data['cases']
    rows = [json.loads(line) for line in (run / 'results.jsonl').read_text().splitlines()]
    indexed = {}
    for row in rows:
        key = row['case_id'], row['method']
        if key in indexed:
            raise ValueError(f'Duplicate result: {key}')
        indexed[key] = row
    expected = {(case['id'], method) for case in cases for method in ('qwen', 'minilm')}
    if set(indexed) != expected:
        raise ValueError('Result rows do not exactly cover both methods for every case')
    if summary['completed_cases'] != len(rows):
        raise ValueError('Summary row count differs from results')
    return cases, indexed, summary, metadata


def make_ass(cases, rows, summary):
    header = '''[Script Info]
Title: Qwen3.5 versus MiniLM
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,Noto Sans CJK JP,46,&H00FFFFFF,&H00FFFFFF,&H00060B1B,&H00000000,1,0,0,0,100,100,0,0,1,2,0,8,20,20,10,1
Style: Header,Noto Sans CJK JP,30,&H00FFFFFF,&H00FFFFFF,&H00060B1B,&H00000000,1,0,0,0,100,100,0,0,1,2,0,8,20,20,10,1
Style: Body,Noto Sans CJK JP,27,&H00F5F7FA,&H00FFFFFF,&H00060B1B,&H00000000,0,0,0,0,100,100,0,0,1,1,0,8,20,20,10,1
Style: Small,Noto Sans CJK JP,21,&H00BAC8D5,&H00FFFFFF,&H00060B1B,&H00000000,0,0,0,0,100,100,0,0,1,1,0,8,20,20,10,1
Style: Good,Noto Sans CJK JP,36,&H0088EFAB,&H00FFFFFF,&H00060B1B,&H00000000,1,0,0,0,100,100,0,0,1,1,0,8,20,20,10,1
Style: Bad,Noto Sans CJK JP,36,&H007999FF,&H00FFFFFF,&H00060B1B,&H00000000,1,0,0,0,100,100,0,0,1,1,0,8,20,20,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    lines = [header]
    lines.extend([
        event(0, 4, 'Title', 640, 90, '指示選択を同じ時間軸で比較'),
        event(0, 4, 'Header', 640, 175, 'Qwen3.5-2B  /  多言語MiniLM'),
        event(0, 4, 'Body', 640, 280, 'task 0を例示、task 1〜9の24指示で評価'),
        event(0, 4, 'Small', 640, 610, '選択のみの比較。ロボット操作の成功率は含まない。'),
    ])
    for index, case in enumerate(cases, 1):
        start = 4 + (index - 1) * 5
        end = start + 5
        key = case['id']
        reference = (f'期待: 実行 task {case["expected_task_id"]}'
                     if case['expected_decision'] == 'execute' else '期待: 確認・保留')
        lines.extend([
            event(start, end, 'Header', 640, 28, f'{index:02}/{len(cases):02}  {KINDS[case["kind"]]}'),
            event(start, end, 'Body', 640, 105, wrap_text(case['instruction'])),
            event(start, end, 'Small', 640, 255, reference),
        ])
        if case['kind'] == 'reply':
            lines.append(event(start, end, 'Small', 640, 225,
                               '前の依頼: ' + wrap_text(case['context'][0]['request'], 65)))
        for method, x, heading in (('qwen', 330, 'Qwen3.5-2B'),
                                   ('minilm', 950, '多言語MiniLM')):
            row = rows[key, method]
            label, status = outcome_text(row)
            style = 'Good' if row['assessment']['correct'] else 'Bad'
            seconds = row.get('inference_seconds')
            duration = ('<0.01 秒' if seconds < .005 else f'{seconds:.2f} 秒') if seconds is not None else '計測なし'
            lines.extend([
                event(start, end, 'Header', x, 338, heading),
                event(start, end, style, x, 405, f'{label}  /  {status}'),
                event(start, end, 'Body', x, 470, f'推論時間  {duration}'),
            ])
            if row['outcome'].get('question'):
                lines.append(event(start, end, 'Small', x, 535,
                                   wrap_text(row['outcome']['question'], 34)))
            if row['assessment']['wrong_execution']:
                lines.append(event(start, end, 'Small', x, 575, '情報不足・誤選択で実行判断'))
        lines.append(event(start, end, 'Small', 640, 664,
                           '表示を同期。実際の推論は順番に実行。'))
    start, end = 4 + len(cases) * 5, 12 + len(cases) * 5
    qwen = summary['metrics']['qwen']
    minilm = summary['metrics']['minilm']
    lines.extend([
        event(start, end, 'Title', 640, 70, '指示選択の集計'),
        event(start, end, 'Header', 640, 155,
              f'Qwen3.5  {qwen["correct"]}/{qwen["count"]}    MiniLM  {minilm["correct"]}/{minilm["count"]}'),
        event(start, end, 'Body', 640, 265,
              f'誤実行判断  {qwen["wrong_execution"]}件  /  {minilm["wrong_execution"]}件'),
        event(start, end, 'Body', 640, 325,
              f'確認質問  {qwen["clarification_questions"]}件  /  {minilm["clarification_questions"]}件'),
        event(start, end, 'Body', 640, 385,
              f'MiniLMの保留  {minilm["held"]}件（質問文は生成しない）'),
        event(start, end, 'Small', 640, 475, '1回の逐次実行。速度差や一般的な正答率は示さない。'),
        event(start, end, 'Small', 640, 610, '物理操作は未測定。曖昧な依頼の誤実行判断が残る。'),
    ])
    return '\n'.join(lines) + '\n', end


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--cases', type=Path, default=Path('tasks/comparison_cases_qwen35.json'))
    ap.add_argument('--catalog', type=Path, default=Path('tasks/libero_object.json'))
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    run, cases_path, catalog_path = args.run.resolve(), args.cases.resolve(), args.catalog.resolve()
    cases, rows, summary, metadata = load_run(run, cases_path, catalog_path)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = args.out or Path(f'outputs/video/{stamp}_{uuid.uuid4().hex[:8]}')
    out.mkdir(parents=True, exist_ok=False)
    subtitles, duration = make_ass(cases, rows, summary)
    ass_path = out / 'comparison.ass'
    ass_path.write_text(subtitles)
    video_path = out / 'comparison.mp4'
    font_dir = ROOT / 'submission/fonts'
    case_end = 4 + len(cases) * 5
    panel_time = f"between(t\\,4\\,{case_end})"
    filters = (f"drawbox=x=40:y=310:w=590:h=315:color=0x182D42:t=fill:enable='{panel_time}',"
               f"drawbox=x=650:y=310:w=590:h=315:color=0x182D42:t=fill:enable='{panel_time}',"
               f"ass={ass_path}:fontsdir={font_dir}")
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
               '-f', 'lavfi', '-i', f'color=c=0x071423:s=1280x720:r=30:d={duration}',
               '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
               '-vf', filters, '-t', str(duration), '-c:v', 'libx264',
               '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p',
               '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart',
               str(video_path)]
    subprocess.run(command, check=True)
    manifest = {'source_run': run.name, 'source_summary_sha256': hashlib.sha256(
        (run / 'summary.json').read_bytes()).hexdigest(), 'cases_sha256': metadata['cases_sha256'],
        'case_count': len(cases), 'duration_seconds': duration,
        'presentation_note': 'Both methods are shown together per case; original inference was sequential.',
        'physical_execution': False, 'audio': 'silent AAC track'}
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(f'Saved {video_path} ({duration} seconds, {len(cases)} synchronized cases)')


if __name__ == '__main__':
    main()
