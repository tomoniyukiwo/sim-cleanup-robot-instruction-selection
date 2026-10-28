import json
from pathlib import Path
import tempfile
import unittest

from cleanup_robot.assets import ensure_planner_lock


class PlannerLockTests(unittest.TestCase):
    def test_creates_separate_lock_without_changing_base(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)/'assets.lock.json'
            target=Path(folder)/'assets.qwen35.lock.json'
            original={'schema_version':1,'assets_ready':True,'planner':{'repo':'old'}}
            base.write_text(json.dumps(original))
            ensure_planner_lock(target,base)
            self.assertEqual(json.loads(target.read_text()),original)
            self.assertEqual(json.loads(base.read_text()),original)
            target.write_text('{"existing":true}')
            ensure_planner_lock(target,base)
            self.assertEqual(target.read_text(),'{"existing":true}')

    def test_missing_target_gives_actionable_error(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(FileNotFoundError,'--base-lock'):
                ensure_planner_lock(Path(folder)/'missing.json')

    def test_refuses_base_as_target(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)/'base.json'
            base.write_text('{"assets_ready":true}')
            with self.assertRaises(ValueError):ensure_planner_lock(base,base)


if __name__=='__main__':
    unittest.main()
