"""Override only saved video FPS before invoking the pinned official evaluator."""
import math
import os
import runpy
from lerobot.envs.libero import LiberoEnv
fps=float(os.environ.get('RECORD_FPS','20'))
if not math.isfinite(fps) or fps<=0:raise SystemExit('RECORD_FPS must be positive')
LiberoEnv.metadata={**LiberoEnv.metadata,'render_fps':fps}
print(f'Official evaluation: saved video FPS={fps:g} (standard LIBERO control is 20 Hz)',flush=True)
runpy.run_module('lerobot.scripts.lerobot_eval',run_name='__main__')
