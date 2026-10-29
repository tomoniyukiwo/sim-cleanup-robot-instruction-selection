import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from cleanup_robot.ros_worker import main,PREFIX,select_plan
from test_controller import FakeBackend

class DummyRecorder:
    def __init__(self,*args,**kwargs):pass
    def __call__(self,*args):pass
    def finish(self,*args):pass
    def close(self):pass

class WorkerProtocolTests(unittest.TestCase):
    def test_minilm_selection_maps_execute_and_hold_without_question(self):
        task={'task_id':2,'instruction':'put the item away'}
        routing=types.ModuleType('cleanup_robot.routing')
        class FakeRouter:
            accepted=True
            def __init__(self,catalog,path,cfg):pass
            def route(self,text):
                self.last_text=text
                return {'accepted':self.accepted,'task':task,'score':.6,'margin':.1}
        routing.Router=FakeRouter
        with patch.dict(sys.modules,{'cleanup_robot.routing':routing}):
            plan,raw=select_plan('指示',[],{'tasks':[task]}, {},{'embedding':{'path':'unused'}},
                                 'minilm',lambda:False)
            self.assertEqual((plan['decision'],plan['task_id']),('execute',2))
            self.assertFalse(plan['retry_on_timeout'])
            self.assertIn('accepted',raw)
            FakeRouter.accepted=False
            plan,_=select_plan('曖昧',[],{'tasks':[task]}, {},{'embedding':{'path':'unused'}},
                               'minilm',lambda:False)
            self.assertEqual((plan['decision'],plan['task_id']),('hold',None))
            self.assertFalse(plan['retry_on_timeout'])
    def run_worker(self,decision):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'config.json').write_text(json.dumps({'suite':'test','video_fps':20,'steps_per_attempt':3,'max_attempts':2}))
            (root/'catalog.json').write_text(json.dumps({'suite':'test','tasks':[]}))
            (root/'lock.json').write_text('{}')
            request={'request_id':'unit-test','instruction':'test','config':str(root/'config.json'),
                     'catalog':str(root/'catalog.json'),'lock':str(root/'lock.json')}
            path=root/'request.json';path.write_text(json.dumps(request))
            plan={'decision':decision,'task_id':0 if decision=='execute' else None,
                  'message':'test','retry_on_timeout':True,'task':{'task_id':0,'instruction':'test'}}
            planner=types.ModuleType('cleanup_robot.planner');planner.plan_local=lambda *a,**kw:(plan,'test')
            backend=types.ModuleType('cleanup_robot.backend');called=[]
            def make_backend(*args):
                called.append(True);b=FakeBackend(success_at=2);b.control_hz=20;b.close=lambda:None;return b
            backend.LiberoBackend=make_backend
            video=types.ModuleType('cleanup_robot.video');video.Recorder=DummyRecorder
            output=io.StringIO()
            with patch.dict(sys.modules,{'cleanup_robot.planner':planner,'cleanup_robot.backend':backend,'cleanup_robot.video':video}):
                with patch.object(sys,'argv',['worker','--request',str(path)]),patch.object(sys,'stdout',output),patch('threading.Thread'):
                    main()
            lines=output.getvalue().splitlines()
            self.assertTrue(all(line.startswith(PREFIX) for line in lines))
            events=[json.loads(line[len(PREFIX):]) for line in lines]
            self.assertEqual(events[-1]['event'],'finished')
            self.assertEqual(len((root/'events.jsonl').read_text().splitlines()),len(events))
            report=json.loads((root/'result.json').read_text())
            return report,called
    def test_execute_protocol_and_result(self):
        report,called=self.run_worker('execute')
        self.assertTrue(report['success']);self.assertEqual(report['steps'],2);self.assertTrue(called)
    def test_clarification_never_loads_executor(self):
        report,called=self.run_worker('clarify')
        self.assertEqual(report['reason'],'clarify');self.assertFalse(called)
