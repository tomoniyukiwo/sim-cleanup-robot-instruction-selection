"""Show two independent ROS-triggered physical episodes for each fixed instruction."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import uuid

from build_comparison_video import event, wrap_text
from build_physical_comparison_video import ROOT, scene_ass

CANVAS_WIDTH, CANVAS_HEIGHT = 1920, 1080
CLIP_WIDTH, CLIP_HEIGHT = 928, 580
CLIP_Y = 391
CLIP_X = {'left': 20, 'right': 972}


def source_dimensions(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                             '-show_entries', 'stream=width,height', '-of', 'csv=p=0:s=x',
                             str(path)], check=True, capture_output=True, text=True)
    width, height = map(int, result.stdout.strip().split('x'))
    if width < CLIP_WIDTH or height < CLIP_HEIGHT:
        raise ValueError(f'Source video is smaller than the comparison panel: {path}')
    if width * CLIP_HEIGHT != height * CLIP_WIDTH:
        raise ValueError(f'Source video aspect ratio differs from the comparison panel: {path}')
    return width, height


def render_text_segment(path, subtitles, duration):
    ass = path.with_suffix('.ass')
    ass.write_text(subtitles)
    font_dir = ROOT / 'submission/fonts'
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                    '-f', 'lavfi', '-i', f'color=c=0x071423:s={CANVAS_WIDTH}x{CANVAS_HEIGHT}:r=30:d={duration}',
                    '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
                    '-vf', f'ass={ass}:fontsdir={font_dir}', '-map', '0:v', '-map', '1:a',
                    '-t', str(duration), '-c:v', 'libx264', '-preset', 'veryfast',
                    '-crf', '18', '-pix_fmt', 'yuv420p', '-r', '30',
                    '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', str(path)], check=True)


def load_rows(experiment, cases_path):
    manifest = json.loads((experiment / 'manifest.json').read_text())
    if manifest.get('input_transport') != 'ROS 2 /cleanup/instruction':
        raise ValueError('Video requires ROS topic input for every episode')
    cases = [c for c in json.loads(cases_path.read_text())['cases'] if c['kind'] == 'indirect']
    if len(cases) != 9 or {c['expected_task_id'] for c in cases} != set(range(1, 10)):
        raise ValueError('Expected one indirect case per task 1–9')
    rows = {(r['case_id'], r['method']): r for r in manifest['runs']}
    expected = {(c['id'], method) for c in cases for method in ('qwen', 'minilm')}
    if set(rows) != expected or len(manifest['runs']) != 18:
        raise ValueError('Expected 18 distinct ROS episodes, nine per method')
    ids = [r['request_id'] for r in manifest['runs']]
    if len(set(ids)) != 18:
        raise ValueError('Physical episodes must be independent for each method')
    for case in cases:
        for method in ('qwen', 'minilm'):
            row = rows[case['id'], method]
            if row['instruction'] != case['instruction'] or row['expected_task_id'] != case['expected_task_id']:
                raise ValueError('ROS instruction or expected task mismatch')
            run = ROOT / 'outputs/ros' / row['request_id']
            request = json.loads((run / 'request.json').read_text())
            plan = json.loads((run / 'plan.json').read_text())['plan']
            result = json.loads((run / 'result.json').read_text())
            if request['selector'] != method or request['instruction'] != case['instruction']:
                raise ValueError('ROS request does not match the manifest')
            if plan['decision'] != row['decision'] or plan['task_id'] != row['selected_task_id']:
                raise ValueError('ROS plan does not match the manifest')
            if result['selector'] != method or result['success'] != (row['success'] or False):
                raise ValueError('ROS result does not match the manifest')
            video = run / 'demo.mp4'
            if row['decision'] == 'execute' and not video.is_file():
                raise FileNotFoundError(f'Executed ROS episode has no video: {row["request_id"]}')
            if row['decision'] != 'execute' and video.exists():
                raise ValueError('Nonexecuting episode has operation video')
    return cases, rows, manifest


def subtitles(case, rows, index, step_budgets=None):
    budget = (step_budgets or {}).get(str(case['expected_task_id']), 200)
    duration = 18 if budget > 200 else 12
    lines = [
        event(0, duration, 'Header', 640, 18, f'{index:02}/09  入力 task {case["expected_task_id"]}'),
        event(0, duration, 'Body', 640, 75, wrap_text(case['instruction'], 65)),
    ]
    for method, x, name in (('qwen', 335, 'Qwen3.5-2B'), ('minilm', 945, '多言語MiniLM')):
        row = rows[case['id'], method]
        decision = row['decision']
        task = row['selected_task_id']
        selection = row['planning_wall_seconds']
        operation = row['operation_wall_seconds']
        if decision == 'execute':
            choice = f'実行 task {task}'
            goal = '目標達成' if row['success'] else '目標未達'
            if task != case['expected_task_id']:
                goal += '（誤選択）'
        else:
            choice, goal = {'hold':'保留','clarify':'確認','reject':'拒否'}.get(decision,decision), '操作なし'
        lines.extend([
            event(0, duration, 'Header', x, 145, name),
            event(0, duration, 'Small', x, 185, f'ROS入力 → {choice} / 選択処理 {selection:.1f}秒'),
            event(0, duration, 'Small', x, 220,
                  f'操作 {operation:.1f}秒 / {goal}' if operation is not None else goal),
        ])
        if decision != 'execute':
            lines.append(event(0, duration, 'Hold', x, 390, '操作動画なし'))
    lines.append(event(0, duration, 'Small', 640, 658,
                       f'各モデルで独立実行。seed 42 / 初期状態0 / 最大{budget}ステップ。'))
    return scene_ass(lines)


def render_pair(path, subtitle_text, left, right, duration=12):
    ass = path.with_suffix('.ass')
    ass.write_text(subtitle_text)
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
               '-f', 'lavfi', '-i', f'color=c=0x071423:s={CANVAS_WIDTH}x{CANVAS_HEIGHT}:r=30:d={duration}',
               '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
    clips = [clip for clip in (left,right) if clip is not None]
    for clip in clips:
        source_dimensions(clip)
        command += ['-i', str(clip)]
    filters = ['[0:v]drawbox=x=14:y=385:w=940:h=592:color=0x182D42:t=fill,'
               'drawbox=x=966:y=385:w=940:h=592:color=0x182D42:t=fill[bg]']
    current = 'bg'
    input_index = 2
    for label, clip in (('left', left), ('right', right)):
        if clip is None:
            continue
        filters.append(f'[{input_index}:v]fps=30,scale={CLIP_WIDTH}:{CLIP_HEIGHT}:flags=lanczos,'
                       f'tpad=stop_mode=clone:stop_duration={duration},trim=duration={duration},'
                       f'setpts=PTS-STARTPTS[{label}]')
        next_label = 'v1' if label == 'left' else 'v2'
        filters.append(f'[{current}][{label}]overlay={CLIP_X[label]}:{CLIP_Y}:shortest=1[{next_label}]')
        current = next_label
        input_index += 1
    font_dir = ROOT / 'submission/fonts'
    filters.append(f'[{current}]ass={ass}:fontsdir={font_dir}[video]')
    command += ['-filter_complex', ';'.join(filters), '-map', '[video]', '-map', '1:a',
                '-t', str(duration), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
                '-pix_fmt', 'yuv420p', '-r', '30', '-c:a', 'aac', '-b:a', '96k',
                '-movflags', '+faststart', str(path)]
    subprocess.run(command, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--experiment', type=Path, required=True)
    ap.add_argument('--cases', type=Path, default=ROOT / 'tasks/comparison_cases_qwen35.json')
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    cases, rows, manifest = load_rows(args.experiment.resolve(), args.cases.resolve())
    first_clip = ROOT / 'outputs/ros' / rows[cases[0]['id'], 'qwen']['request_id'] / 'demo.mp4'
    source_width, source_height = source_dimensions(first_clip)
    budgets = manifest.get('steps_per_attempt_by_task') or {
        str(task): manifest['steps_per_attempt'] for task in range(1, 10)}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = args.out or ROOT / 'outputs/video' / f'{stamp}_{uuid.uuid4().hex[:8]}'
    out.mkdir(parents=True, exist_ok=False)
    segments = []
    intro = out / 'segment_00.mp4'
    render_text_segment(intro, scene_ass([
        event(0, 4, 'Title', 640, 150, 'ROS指示入力から操作結果を比較'),
        event(0, 4, 'Body', 640, 260, 'Qwen3.5-2B  /  多言語MiniLM'),
        event(0, 4, 'Small', 640, 490, '各モデルが独立に判断し、SmolVLAを個別に実行。'),
    ]), 4)
    segments.append(intro)
    for index, case in enumerate(cases, 1):
        left = rows[case['id'], 'qwen']
        right = rows[case['id'], 'minilm']
        path = out / f'segment_{index:02}.mp4'
        def clip(row):
            return ROOT / 'outputs/ros' / row['request_id'] / 'demo.mp4' if row['decision'] == 'execute' else None
        render_pair(path, subtitles(case, rows, index, budgets), clip(left), clip(right),
                    18 if budgets[str(case['expected_task_id'])] > 200 else 12)
        segments.append(path)
        print(f'Rendered task {case["expected_task_id"]}', flush=True)
    totals = manifest['summary']
    def summary_line(method, label):
        m = totals[method]
        return (f'{label}: 選択 {m["correct_selection"]}/{m["requests"]}  '
                f'操作達成 {m["physical_goal_satisfied"]}/{m["physical_executions"]}  '
                f'一貫成功 {m["end_to_end_success"]}/{m["requests"]}')
    ending = out / 'segment_10.mp4'
    render_text_segment(ending, scene_ass([
        event(0, 8, 'Title', 640, 105, 'ROS入力 → 判断 → 物理操作'),
        event(0, 8, 'Header', 640, 240, summary_line('qwen','Qwen3.5')),
        event(0, 8, 'Header', 640, 335, summary_line('minilm','MiniLM')),
        event(0, 8, 'Small', 640, 550,
              f'各モデルで独立試行。task 7は{budgets["7"]}、他は{budgets["1"]}ステップ / 1試行。'),
        event(0, 8, 'Small', 640, 610, '選択処理時間はモデル読込を含む。映像はシミュレーション時間。'),
    ]), 8)
    segments.append(ending)
    concat = out / 'segments.txt'
    concat.write_text(''.join(f"file '{p.resolve()}'\n" for p in segments))
    video = out / 'comparison_ros_independent.mp4'
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                    '-f', 'concat', '-safe', '0', '-i', str(concat),
                    '-c', 'copy', '-movflags', '+faststart', str(video)], check=True)
    (out / 'manifest.json').write_text(json.dumps({'schema_version': 1,
        'source_experiment': args.experiment.name, 'transport': 'ROS 2 /cleanup/instruction',
        'independent_physical_episodes': True, 'task_ids': list(range(1, 10)),
        'summary': totals, 'confirmation_cases_included': False,
        'resolution': {'width': CANVAS_WIDTH, 'height': CANVAS_HEIGHT},
        'source_resolution': {'width': source_width, 'height': source_height},
        'task_panel_resolution': {'width': CLIP_WIDTH, 'height': CLIP_HEIGHT},
        'duration_seconds': 4 + sum(18 if budgets[str(task)] > 200 else 12
                                    for task in range(1, 10)) + 8}, ensure_ascii=False, indent=2) + '\n')
    print(f'Saved {video}', flush=True)


if __name__ == '__main__':
    main()
