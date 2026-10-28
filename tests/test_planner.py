import json
import unittest
from cleanup_robot.planner import validate_plan

CATALOG={'tasks':[{'task_id':0,'instruction':'put soup in basket'}]}
class PlannerTests(unittest.TestCase):
    def output(self,**fields):
        plan={'decision':'execute','task_id':0,'message':'缶をかごへ運びます','retry_on_timeout':True}
        plan.update(fields);return json.dumps(plan,ensure_ascii=False)
    def test_registered_task(self):
        self.assertEqual(validate_plan(self.output(),CATALOG)['task']['task_id'],0)
    def test_clarification_cannot_execute(self):
        p=validate_plan(self.output(decision='clarify',task_id=None,retry_on_timeout=False),CATALOG)
        self.assertNotIn('task',p)
    def test_unregistered_task_rejected(self):
        with self.assertRaises(ValueError):validate_plan(self.output(task_id=99),CATALOG)
    def test_boolean_is_not_integer_task_id(self):
        with self.assertRaises(ValueError):validate_plan(self.output(task_id=True),CATALOG)
    def test_clarification_with_task_is_rejected(self):
        with self.assertRaises(ValueError):validate_plan(self.output(decision='clarify'),CATALOG)
    def test_extra_executable_code_field_rejected(self):
        with self.assertRaises(ValueError):validate_plan(self.output(code='print(1)'),CATALOG)
    def test_code_fence_with_newlines(self):
        self.assertEqual(validate_plan('```json\n'+self.output()+'\n```',CATALOG)['decision'],'execute')
