"""Package source and documentation using an explicit publication allowlist."""
import argparse
from pathlib import Path
import zipfile

ROOT_FILES = {'.gitignore', 'LICENSE', 'README.md', 'pyproject.toml', 'uv.lock'}
SOURCE_DIRS = {'src', 'ros', 'scripts', 'tests', 'configs'}
EXACT = {'models/README.md', 'tasks/README.md', 'outputs/README.md', 'evidence/README.md',
         'submission/README.md', 'submission/report_data.json',
         'tasks/libero_object.json',
         'tasks/comparison_cases_qwen35.json', 'tasks/fewshot_task0.json',
         'planner_env/pyproject.toml', 'planner_env/runner.py', 'planner_env/uv.lock'}


def included(relative):
    p = Path(relative)
    if any(part.startswith('.') or part == '__pycache__' or part.endswith('.egg-info') for part in p.parts):
        return str(p) == '.gitignore'
    if len(p.parts) == 1:
        return p.name in ROOT_FILES
    if str(p) in EXACT:
        return True
    if p.parts[0] in SOURCE_DIRS:
        return p.suffix in {'.py', '.sh', '.json', '.md'}
    if p.parts[0] == 'docs':
        return p.suffix == '.md'
    # Evidence is deliberately opt-in after the user reviews each summary.
    return False


def available_output(path):
    """Choose a new filename while retaining every existing archive."""
    path = Path(path)
    if not path.exists():
        return path
    number = 1
    while True:
        candidate = path.with_name(f'{path.stem}_{number}{path.suffix}')
        if not candidate.exists():
            return candidate
        number += 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--evidence', action='append', type=Path, default=[],
                    help='Reviewed exporter JSON under evidence/; may repeat.')
    ap.add_argument('--require-planner-lock', action='store_true',
                    help='Fail unless the separate Qwen3.5 uv.lock has been generated')
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.require_planner_lock and not (root / 'planner_env/uv.lock').is_file():
        ap.error('planner_env/uv.lock missing; run env -u UV_PROJECT_ENVIRONMENT uv lock --project planner_env first')
    candidates = [root / name for name in ROOT_FILES]
    for dirname in SOURCE_DIRS | {'docs', 'models', 'tasks', 'outputs', 'evidence', 'submission', 'planner_env'}:
        folder = root / dirname
        if not folder.is_dir() or folder.is_symlink():
            continue
        import os
        for base, dirs, files in os.walk(folder, followlinks=False):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__'
                       and not d.endswith('.egg-info') and not (Path(base) / d).is_symlink()]
            candidates.extend(Path(base) / name for name in files)
    selected = [p for p in candidates if p.is_file() and not p.is_symlink()
                and included(p.relative_to(root))]
    for path in args.evidence:
        path = path.resolve()
        if path.parent != root / 'evidence' or path.suffix != '.json' or not path.is_file():
            ap.error('--evidence must be an existing JSON directly under this project evidence/')
        if path not in selected:
            selected.append(path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    output = available_output(args.out)
    if output != args.out:
        print(f'Output already exists; keeping it and using {output}.')
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(selected):
            archive.write(path, Path('cleanup_robot') / path.relative_to(root))
    print(f'Saved {output}: {len(selected)} source/documentation files; no weights or raw runs.')
    print('Evidence is included only when explicitly supplied with --evidence.')


if __name__ == '__main__':
    main()
