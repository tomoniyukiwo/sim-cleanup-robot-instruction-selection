import unittest
from cleanup_robot.controller import execute

class FakeBackend:
    def __init__(self,success_at=None,terminate_at=None):
        self.success_at=success_at;self.terminate_at=terminate_at;self.resets=0;self.policy_resets=0
        self.state=0;self.instructions=[]
    def reset_environment(self):self.resets+=1;self.state=0;return self.state
    def reset_policy(self):self.policy_resets+=1
    def predict(self,obs,instruction):
        assert obs==self.state
        self.instructions.append(instruction);return 1
    def step(self,action):
        self.state+=action
        return self.state,self.state==self.success_at,self.state==self.terminate_at,{}

class ControllerTests(unittest.TestCase):
    def test_success_stops(self):
        b=FakeBackend(success_at=2)
        result=execute(b,'raw','canonical',steps_per_attempt=3,max_attempts=3)
        self.assertTrue(result['success']);self.assertEqual(result['steps'],2)
        self.assertEqual(b.resets,1)
    def test_retry_preserves_environment_and_switches_instruction(self):
        b=FakeBackend(success_at=3)
        result=execute(b,'raw','canonical',steps_per_attempt=2,max_attempts=3,instruction_mode='raw')
        self.assertTrue(result['success']);self.assertEqual(result['attempts'],2)
        self.assertEqual(b.resets,1);self.assertEqual(b.policy_resets,2)
        self.assertEqual(b.instructions,['raw','raw','canonical'])
        self.assertEqual(sum(e['event']=='retry_current_state' for e in result['events']),1)
    def test_all_budgets_exhausted(self):
        b=FakeBackend()
        result=execute(b,'raw','canonical',steps_per_attempt=2,max_attempts=3)
        self.assertFalse(result['success']);self.assertEqual(result['steps'],6)
        self.assertEqual(b.state,6);self.assertEqual(b.resets,1)
    def test_terminated_does_not_retry(self):
        b=FakeBackend(terminate_at=1)
        result=execute(b,'raw','canonical',steps_per_attempt=2,max_attempts=3)
        self.assertEqual(result['reason'],'environment_terminated')
        self.assertEqual(b.policy_resets,1)
    def test_invalid_budgets(self):
        with self.assertRaises(ValueError):execute(FakeBackend(),'a','b',steps_per_attempt=0,max_attempts=3)
