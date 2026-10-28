import os
from pathlib import Path
import runpy
import sys
import types
import unittest
from unittest.mock import patch
import numpy as np
from cleanup_robot.video import Recorder

class FakeWriter:
    def __init__(self):self.count=0
    def append_data(self,image):self.count+=1

class TimingTests(unittest.TestCase):
    def recorder(self,speed):
        r=Recorder.__new__(Recorder);r.writer=FakeWriter();r.fps=20;r.control_hz=20
        r.speed=speed;r.written=0;r.canonical='test task';r.last=None
        return r
    def test_independent_recorder_speed(self):
        obs={'pixels':{'image':np.zeros((256,256,3),dtype=np.uint8),'image2':np.zeros((256,256,3),dtype=np.uint8)}}
        normal=self.recorder(1);slow=self.recorder(.5)
        normal(obs,20,1,'TEST');slow(obs,20,1,'TEST')
        self.assertEqual(normal.writer.count,21)
        self.assertEqual(slow.writer.count,41)
    def test_official_wrapper_uses_requested_rate(self):
        env=type('LiberoEnv',(),{'metadata':{'render_fps':80}})
        module=types.ModuleType('lerobot.envs.libero');module.LiberoEnv=env
        with patch.dict(sys.modules,{'lerobot.envs.libero':module}),patch.dict(os.environ,{'RECORD_FPS':'10'}):
            with patch('runpy.run_module') as invoke:
                runpy.run_path(str(Path(__file__).resolve().parents[1]/'scripts/official_eval_video.py'),run_name='__main__')
                self.assertEqual(env.metadata['render_fps'],10)
                invoke.assert_called_once_with('lerobot.scripts.lerobot_eval',run_name='__main__')
