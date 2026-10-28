"""Compose real task videos beside the two selection outcomes, one task at a time."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import uuid

from build_comparison_video import event, load_run, wrap_text


ROOT = Path(__file__).resolve().parents[1]
ASS_HEADER = '''[Script Info]
Title: Task selection with shared LIBERO execution
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,Noto Sans CJK JP,46,&H00FFFFFF,&H00FFFFFF,&H00060B1B,&H00000000,1,0,0,0,100,100,0,0,1,2,0,8,20,20,10,1
Style: Header,Noto Sans CJK JP,30,&H00FFFFFF,&H00FFFFFF,&H00060B1B,&H00000000,1,0,0,0,100,100,0,0,1,2,0,8,20,20,10,1
Style: Body,Noto Sans CJK JP,26,&H00F5F7FA,&H00FFFFFF,&H00060B1B,&H00000000,0,0,0,0,100,100,0,0,1,1,0,8,20,20,10,1
Style: Small,Noto Sans CJK JP,20,&H00BAC8D5,&H00FFFFFF,&H00060B1B,&H00000000,0,0,0,0,100,100,0,0,1,1,0,8,20,20,10,1
Style: Good,Noto Sans CJK JP,26,&H0088EFAB,&H00FFFFFF,&H00060B1B,&H00000000,1,0,0,0,100,100,0,0,1,1,0,8,20,20,10,1
Style: Hold,Noto Sans CJK JP,30,&H007999FF,&H00FFFFFF,&H00060B1B,&H00000000,1,0,0,0,100,100,0,0,1,1,0,8,20,20,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''


def selected_cases(cases, rows):
    """Use one indirect request per task and never label a wrong choice as task footage."""
    selected = [case for case in cases if case['kind'] == 'indirect']
    if len(selected) != 9 or {case['expected_task_id'] for case in selected} != set(range(1, 10)):
        raise ValueError('Expected one indirect test for each task 1–9')
    for case in selected:
        for method in ('qwen', 'minilm'):
            outcome = rows[case['id'], method]['outcome']
            if outcome['decision'] == 'execute' and outcome['task_id'] != case['expected_task_id']:
                raise ValueError(f'Wrong-task execution cannot reuse task {case["expected_task_id"]} footage')
            if outcome['decision'] not in {'execute', 'hold'}:
                raise ValueError(f'Unexpected nonexecution outcome for {case["id"]}: {method}')
    return selected


def load_clips(clips_root, selected):
    manifest = json.loads((clips_root / 'manifest.json').read_text())
    if manifest.get('recording_method') != 'explicit task ID; one SmolVLA episode per task':
        raise ValueError('Use task clips recorded with record_task_clips.py')
    clips = {}
    records = {item['task_id']: item for item in manifest['task_runs']}
    for case in selected:
        task_id = case['expected_task_id']
        record = records.get(task_id)
        video = clips_root / f'task_{task_id}' / 'demo.mp4'
        result_path = clips_root / f'task_{task_id}' / 'result.json'
        if record is None or not video.is_file() or not result_path.is_file():
            raise FileNotFoundError(f'Actual LIBERO video/result missing for task {task_id}')
        result = json.loads(result_path.read_text())
        if result.get('route', {}).get('task', {}).get('task_id') != task_id:
            raise ValueError(f'Task {task_id} clip route does not match its task ID')
        if result.get('success') is None:
            raise ValueError(f'Task {task_id} has no measured goal result')
        clips[task_id] = (video, result)
    return clips


def scene_ass(lines):
    return ASS_HEADER + '\n'.join(lines) + '\n'


def result_label(row):
    result = row['outcome']
    if result['decision'] == 'hold':
        return '保留（操作なし）'
    return f'実行 task {result["task_id"]}'


def case_subtitles(case, rows, result, index):
    lines = [
        event(0, 12, 'Header', 640, 18, f'{index:02}/09  task {case["expected_task_id"]}'),
        event(0, 12, 'Body', 640, 75, wrap_text(case['instruction'], 65)),
    ]
    for method, x, name in (('qwen', 335, 'Qwen3.5-2B'), ('minilm', 945, '多言語MiniLM')):
        row = rows[case['id'], method]
        duration = row.get('inference_seconds')
        timing = ('<0.01秒' if duration < .005 else f'{duration:.2f}秒') if duration is not None else '計測なし'
        lines.extend([
            event(0, 12, 'Header', x, 145, name),
            event(0, 12, 'Small', x, 186, f'選択推論 {timing}   /   {result_label(row)}'),
        ])
        if row['outcome']['decision'] == 'hold':
            lines.append(event(0, 12, 'Hold', x, 390, '選択を保留\n操作動画なし'))
    operation_seconds = result.get('wall_seconds')
    if isinstance(operation_seconds, (int, float)):
        lines.append(event(0, 12, 'Small', 640, 225,
                           f'共通のSmolVLA操作時間 {operation_seconds:.1f}秒（モデル読込を除く）'))
    goal = '目標達成' if result['success'] else '目標未達'
    lines.extend([
        event(0, 12, 'Small', 640, 624,
              f'共通のSmolVLA実行映像を両側に再掲 / LIBERO: {goal}'),
        event(0, 12, 'Small', 640, 663,
              'シーンはタスクごとに初期化。選択方法ごとの独立した操作試行ではない。'),
    ])
    return scene_ass(lines)


def render_segment(path, subtitles, duration, clip=None, show_right=True):
    ass_path = path.with_suffix('.ass')
    ass_path.write_text(subtitles)
    font_dir = ROOT / 'submission/fonts'
    background = f'color=c=0x071423:s=1280x720:r=30:d={duration}'
    if clip is None:
        command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                   '-f', 'lavfi', '-i', background,
                   '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
                   '-vf', f'ass={ass_path}:fontsdir={font_dir}',
                   '-map', '0:v', '-map', '1:a']
    else:
        command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                   '-i', str(clip), '-f', 'lavfi', '-i', background,
                   '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
        source = ('[0:v]fps=30,scale=560:314:force_original_aspect_ratio=decrease:force_divisible_by=2,'
                  'pad=560:314:(ow-iw)/2:(oh-ih)/2,tpad=stop_mode=clone:stop_duration=12,'
                  'trim=duration=12,setpts=PTS-STARTPTS')
        if show_right:
            filters = (source + ',split=2[left][right];'
                       '[1:v]drawbox=x=40:y=255:w=590:h=335:color=0x182D42:t=fill,'
                       'drawbox=x=650:y=255:w=590:h=335:color=0x182D42:t=fill[bg];'
                       '[bg][left]overlay=55:265:shortest=1[v1];'
                       '[v1][right]overlay=665:265:shortest=1[v2];'
                       f'[v2]ass={ass_path}:fontsdir={font_dir}[video]')
        else:
            filters = (source + '[left];'
                       '[1:v]drawbox=x=40:y=255:w=590:h=335:color=0x182D42:t=fill,'
                       'drawbox=x=650:y=255:w=590:h=335:color=0x182D42:t=fill[bg];'
                       '[bg][left]overlay=55:265:shortest=1[v1];'
                       f'[v1]ass={ass_path}:fontsdir={font_dir}[video]')
        command += ['-filter_complex', filters, '-map', '[video]', '-map', '2:a']
    command += ['-t', str(duration), '-c:v', 'libx264', '-preset', 'veryfast',
                '-crf', '22', '-pix_fmt', 'yuv420p', '-r', '30',
                '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', str(path)]
    subprocess.run(command, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--clips', type=Path, required=True)
    ap.add_argument('--cases', type=Path, default=Path('tasks/comparison_cases_qwen35.json'))
    ap.add_argument('--catalog', type=Path, default=Path('tasks/libero_object.json'))
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    run, clips_root = args.run.resolve(), args.clips.resolve()
    cases, rows, _, _ = load_run(run, args.cases.resolve(), args.catalog.resolve())
    selected = selected_cases(cases, rows)
    clips = load_clips(clips_root, selected)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = args.out or Path(f'outputs/video/{stamp}_{uuid.uuid4().hex[:8]}')
    out.mkdir(parents=True, exist_ok=False)
    segments = []
    intro = out / 'segment_00.mp4'
    render_segment(intro, scene_ass([
        event(0, 4, 'Title', 640, 160, '遠回しな指示を9タスクで比較'),
        event(0, 4, 'Body', 640, 250, 'Qwen3.5-2B  /  多言語MiniLM'),
        event(0, 4, 'Small', 640, 480, 'task 0を例示に使用。操作映像は共通のSmolVLA試行。'),
    ]), 4)
    segments.append(intro)
    for index, case in enumerate(selected, 1):
        task_id = case['expected_task_id']
        clip, result = clips[task_id]
        path = out / f'segment_{index:02}.mp4'
        show_right = rows[case['id'], 'minilm']['outcome']['decision'] == 'execute'
        render_segment(path, case_subtitles(case, rows, result, index), 12,
                       clip=clip, show_right=show_right)
        segments.append(path)
        print(f'Rendered task {task_id}', flush=True)
    summary_path = out / 'segment_10.mp4'
    minilm_correct = sum(rows[case['id'], 'minilm']['assessment']['correct'] for case in selected)
    physical_successes = sum(bool(clips[case['expected_task_id']][1]['success']) for case in selected)
    failed_tasks = [case['expected_task_id'] for case in selected
                    if not clips[case['expected_task_id']][1]['success']]
    failure_note = ('未達: task ' + ', '.join(map(str, failed_tasks))) if failed_tasks else '全件達成'
    render_segment(summary_path, scene_ass([
        event(0, 8, 'Title', 640, 120, '遠回しな指示9件の比較'),
        event(0, 8, 'Header', 640, 240, f'Qwen3.5  9/9   MiniLM  {minilm_correct}/9'),
        event(0, 8, 'Body', 640, 330, 'MiniLMは1件で選択を保留'),
        event(0, 8, 'Body', 640, 400,
              f'共通のSmolVLA目標達成  {physical_successes}/9（{failure_note}）'),
        event(0, 8, 'Small', 640, 515, '操作映像は同じSmolVLA試行を再掲。独立した成功率比較ではない。'),
        event(0, 8, 'Small', 640, 625, '推論時間は選択のみ。モデル読み込み時間を含まない。'),
    ]), 8)
    segments.append(summary_path)
    concat = out / 'segments.txt'
    concat.write_text(''.join(f"file '{path.resolve()}'\n" for path in segments))
    output = out / 'comparison_with_simulation.mp4'
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                    '-f', 'concat', '-safe', '0', '-i', str(concat),
                    '-c', 'copy', '-movflags', '+faststart', str(output)], check=True)
    (out / 'manifest.json').write_text(json.dumps({'selection_run': run.name,
        'physical_clips': clips_root.name, 'task_ids': [c['expected_task_id'] for c in selected],
        'duration_seconds': 120, 'shared_physical_footage': True,
        'selection_subset_correct': {'qwen': 9, 'minilm': minilm_correct},
        'physical_goal_satisfied': physical_successes,
        'physical_failures': failed_tasks,
        'confirmation_cases_included': False}, ensure_ascii=False, indent=2) + '\n')
    print(f'Saved {output} (120 seconds, actual LIBERO footage).')


if __name__ == '__main__':
    main()
