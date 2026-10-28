"""Run Qwen3.5 in its own Python environment, keeping the SmolVLA lock intact."""
import json
import os
from pathlib import Path
import select
import subprocess

from .planner import validate_plan


class BridgeSession:
    def __init__(self, catalog, cfg, lock, cancelled=lambda: False):
        root = Path(__file__).resolve().parents[2]
        python = root / 'planner_env/.venv/bin/python'
        if not python.is_file():
            raise FileNotFoundError('Qwen3.5 environment missing; run uv sync --project planner_env')
        if lock.get('planner', {}).get('repo') != 'Qwen/Qwen3.5-2B':
            raise ValueError('Use a separate lock prepared for Qwen/Qwen3.5-2B')
        if not Path(lock['planner']['path']).is_dir():
            raise FileNotFoundError('Qwen3.5 model cache missing')
        env = os.environ.copy()
        env['HF_HUB_OFFLINE'] = '1'
        env['TRANSFORMERS_OFFLINE'] = '1'
        env.pop('PYTHONPATH', None)
        self.cancelled = cancelled
        self.process = subprocess.Popen(
            [str(python), str(root / 'planner_env/runner.py')], cwd=root, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None,
            text=True, bufsize=1)
        try:
            self._send({'catalog': catalog, 'cfg': cfg, 'planner_path': lock['planner']['path']})
            ready = self._read()
            if ready.get('error'):
                raise RuntimeError(ready['error'])
            if not ready.get('ready'):
                raise RuntimeError('Qwen3.5 runner did not become ready')
            self.load_seconds = ready['load_seconds']
        except BaseException:
            self.close()
            raise

    def _send(self, value):
        self.process.stdin.write(json.dumps(value, ensure_ascii=False) + '\n')
        self.process.stdin.flush()

    def _read(self):
        while True:
            if self.cancelled():
                self.process.terminate()
                raise InterruptedError('Qwen3.5 planning cancelled')
            ready, _, _ = select.select([self.process.stdout], [], [], .1)
            if ready:
                line = self.process.stdout.readline()
                if not line:
                    raise RuntimeError('Qwen3.5 runner closed stdout')
                return json.loads(line)
            if self.process.poll() is not None:
                raise RuntimeError(f'Qwen3.5 runner exited with code {self.process.returncode}')

    def infer(self, instruction, context):
        self._send({'instruction': instruction, 'context': context})
        response = self._read()
        if response.get('error'):
            raise RuntimeError(response['error'])
        return response['raw'], response['inference_seconds']

    def close(self):
        if self.process.poll() is None:
            try:
                self.process.stdin.close()
                self.process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
        self.process.stdout.close()


def plan_via_bridge(instruction, context, catalog, cfg, lock, cancelled=lambda: False):
    session = BridgeSession(catalog, cfg, lock, cancelled)
    try:
        raw, _ = session.infer(instruction, context)
        try:
            return validate_plan(raw, catalog), raw
        except (ValueError, TypeError, KeyError) as exc:
            error = ValueError(f'Planner output rejected: {exc}')
            error.raw_output = raw
            raise error from exc
    finally:
        session.close()
