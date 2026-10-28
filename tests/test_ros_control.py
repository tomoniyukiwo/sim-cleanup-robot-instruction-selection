import io
import threading
import time
import unittest
from cleanup_robot.controller import execute
from cleanup_robot.worker_control import WorkerControl
from test_controller import FakeBackend

class ControlTests(unittest.TestCase):
    def test_cancel_prevents_action(self):
        b=FakeBackend();control=WorkerControl(lambda *a,**kw:None);control.apply({'command':'cancel'})
        report=execute(b,'x','x',steps_per_attempt=2,max_attempts=2,before_action=control.before_action)
        self.assertEqual(report['reason'],'cancelled');self.assertEqual(b.state,0)
    def test_retry_needs_supervisor_permission(self):
        b=FakeBackend()
        report=execute(b,'x','x',steps_per_attempt=2,max_attempts=3,on_retry=lambda attempt:False)
        self.assertEqual(report['reason'],'retry_declined');self.assertEqual(b.state,2)
        self.assertEqual(b.resets,1)
    def test_permission_continues_same_state(self):
        b=FakeBackend(success_at=3);requests=[]
        report=execute(b,'x','x',steps_per_attempt=2,max_attempts=2,on_retry=lambda a:requests.append(a) or True)
        self.assertTrue(report['success']);self.assertEqual(requests,[1]);self.assertEqual(b.resets,1)
    def test_pause_blocks_until_resume(self):
        events=[];control=WorkerControl(lambda e,**kw:events.append(e));control.apply({'command':'pause'})
        result=[];thread=threading.Thread(target=lambda:result.append(control.before_action()))
        thread.start();time.sleep(.08);self.assertTrue(thread.is_alive())
        control.apply({'command':'resume'});thread.join(timeout=1)
        self.assertEqual(result,[True]);self.assertIn('paused',events);self.assertIn('resumed',events)
    def test_retry_command_roundtrip(self):
        events=[];control=None
        def emit(event,**kw):
            events.append(event)
            if event=='retry_requested':control.apply({'command':'retry','allow':True})
        control=WorkerControl(emit)
        self.assertTrue(control.request_retry(1));self.assertEqual(events,['retry_requested'])
    def test_eof_cancels_worker(self):
        control=WorkerControl(lambda *a,**kw:None);control.read(io.StringIO(''))
        self.assertTrue(control.cancelled.is_set())
