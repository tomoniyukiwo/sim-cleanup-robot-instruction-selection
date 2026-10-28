import unittest
from cleanup_robot.contracts import validate_libero_smol_config
class ContractTests(unittest.TestCase):
    def config(self,state=8,action=7):
        return {'type':'smolvla','input_features':{'observation.state':{'shape':[state]},'observation.images.camera1':{'shape':[3,256,256]},'observation.images.camera2':{'shape':[3,256,256]}},'output_features':{'action':{'shape':[action]}}}
    def test_libero_checkpoint_accepted(self):validate_libero_smol_config(self.config())
    def test_base_6d_checkpoint_rejected(self):
        with self.assertRaisesRegex(ValueError,'8 state'):validate_libero_smol_config(self.config(6,6))
    def test_action_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError,'7 action'):validate_libero_smol_config(self.config(8,6))
    def test_missing_camera_rejected(self):
        config=self.config();del config['input_features']['observation.images.camera2']
        with self.assertRaises(ValueError):validate_libero_smol_config(config)
