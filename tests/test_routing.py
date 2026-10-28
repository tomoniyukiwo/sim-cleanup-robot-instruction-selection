import unittest
import numpy as np
from cleanup_robot.routing import choose,normalize,Router

class FakeEmbedding:
    def encode(self,texts,**kwargs):return np.array([[1.,0.]])

class RoutingTests(unittest.TestCase):
    def test_ambiguous_tie(self):self.assertFalse(choose([.8,.8],.45,.04)['accepted'])
    def test_low_similarity(self):self.assertFalse(choose([.2,.1],.45,.04)['accepted'])
    def test_clear_candidate(self):
        result=choose([.2,.8],.45,.04)
        self.assertTrue(result['accepted']);self.assertEqual(result['index'],1)
    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):choose([float('nan')],.45,.04)
    def test_unicode_normalization(self):self.assertEqual(normalize('ＡＢＣ  DEF'),'abc def')
    def router(self):
        r=Router.__new__(Router)
        r.tasks=[{'task_id':0,'instruction':'pick A'},{'task_id':1,'instruction':'pick B'}]
        r.texts=['pick A','pick B'];r.owners=[0,1];r.vectors=np.eye(2)
        r.model=FakeEmbedding();r.cfg={'min_similarity':.45,'min_margin':.04};return r
    def test_forced_selection_is_labelled(self):
        result=self.router().route('anything',1)
        self.assertEqual(result['method'],'explicit_task_id');self.assertEqual(result['task']['task_id'],1)
    def test_exact_selection_is_labelled(self):self.assertEqual(self.router().route('pick A')['method'],'registered_exact')
    def test_unknown_task_id(self):
        with self.assertRaises(ValueError):self.router().route('anything',999)
    def test_semantic_route(self):
        result=self.router().route('unregistered paraphrase')
        self.assertTrue(result['accepted']);self.assertEqual(result['method'],'multilingual_embedding')
