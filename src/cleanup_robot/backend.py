"""Adapter verified against LeRobot v0.4.4 source; hardware execution untested."""
from pathlib import Path
import numpy as np

class LiberoBackend:
    def __init__(self,cfg,lock,task,seed,init_state_index):
        import torch
        from lerobot.configs.policies import PreTrainedConfig
        from lerobot.envs.configs import LiberoEnv as EnvConfig
        from lerobot.envs.libero import LiberoEnv
        from lerobot.envs.factory import make_env_pre_post_processors
        from lerobot.envs.utils import preprocess_observation
        from lerobot.policies.factory import make_policy,make_pre_post_processors
        from libero.libero import benchmark
        from lerobot.utils.random_utils import set_seed
        self.torch=torch;self.cfg=cfg;self.seed=seed;self.preprocess_observation=preprocess_observation
        set_seed(seed)
        if not torch.cuda.is_available():raise RuntimeError('CUDA unavailable: use the Ubuntu NVIDIA PC')
        if cfg['device']!='cuda':raise ValueError('This initial backend targets CUDA inference')
        suite=benchmark.get_benchmark_dict()[cfg['suite']]()
        actual=suite.get_task(task['task_id']).language
        if actual!=task['instruction']:
            raise ValueError('Catalog instruction differs from installed LIBERO; regenerate the catalog')
        self.env=LiberoEnv(task_suite=suite,task_id=task['task_id'],task_suite_name=cfg['suite'],
            obs_type='pixels_agent_pos',observation_width=256,observation_height=256,
            init_states=True,episode_index=init_state_index,num_steps_wait=cfg['num_steps_wait'],
            control_mode=cfg['control_mode'])
        self.control_hz=float(getattr(self.env._env,'control_freq',20))
        try:
            env_cfg=EnvConfig(task=cfg['suite'],task_ids=[task['task_id']],
                              observation_width=256,observation_height=256,control_mode=cfg['control_mode'])
            path=lock['policy']['path']
            policy_cfg=PreTrainedConfig.from_pretrained(path,local_files_only=True)
            policy_cfg.pretrained_path=Path(path);policy_cfg.device='cuda'
            if policy_cfg.type!='smolvla':raise ValueError('This backend expects a LIBERO-trained SmolVLA checkpoint')
            if policy_cfg.input_features['observation.state'].shape[0]!=8 or policy_cfg.output_features['action'].shape[0]!=7:
                raise ValueError('Expected LIBERO state=8/action=7; smolvla_base is not a drop-in replacement')
            policy_cfg.vlm_model_name=lock['tokenizer']['path']
            # The full policy checkpoint already contains the VLM weights.
            # Instantiate from local config, then load the full policy weights once.
            policy_cfg.load_vlm_weights=False
            policy_cfg.n_action_steps=cfg['n_action_steps']
            policy_cfg.push_to_hub=False
            # The checkpoint's saved preprocessor performs this same rename at runtime.
            camera_map={'observation.images.image':'observation.images.camera1',
                        'observation.images.image2':'observation.images.camera2'}
            self.policy=make_policy(cfg=policy_cfg,env_cfg=env_cfg,rename_map=camera_map)
            self.policy.eval()
            self.env_pre,self.env_post=make_env_pre_post_processors(env_cfg=env_cfg,policy_cfg=policy_cfg)
            overrides={'device_processor':{'device':'cuda'},
                       'tokenizer_processor':{'tokenizer_name':lock['tokenizer']['path']}}
            self.pre,self.post=make_pre_post_processors(policy_cfg=policy_cfg,pretrained_path=path,
                                                       preprocessor_overrides=overrides)
        except Exception:
            self.env.close();raise
    def reset_environment(self):return self.env.reset(seed=self.seed)[0]
    def reset_policy(self):
        self.policy.reset()
        for processor in [self.pre,self.post,self.env_pre,self.env_post]:
            if hasattr(processor,'reset'):processor.reset()
    def predict(self,obs,instruction):
        # Match the official vectorized preprocessing shapes, including state tensors.
        def batch(value):
            if isinstance(value,dict):return {k:batch(v) for k,v in value.items()}
            return np.expand_dims(value,0)
        observation=self.preprocess_observation(batch(obs));observation['task']=[instruction]
        observation=self.pre(self.env_pre(observation))
        with self.torch.inference_mode(): action=self.policy.select_action(observation)
        action=self.post(action);action=self.env_post({'action':action})['action']
        array=action.detach().cpu().numpy()
        if array.shape!=(1,7) or not np.isfinite(array).all():raise ValueError('Invalid action from policy')
        return np.clip(array[0],-1,1).astype(np.float32)
    def step(self,action):
        # v0.4.4 LiberoEnv.step() auto-resets after success. Bypass ONLY that wrapper
        # so the success frame and same-state retries are preserved. Pinned internal API.
        raw,reward,done,info=self.env._env.step(action)
        success=bool(self.env._env.check_success())
        return self.env._format_raw_obs(raw),success,bool(done or success),info
    def close(self):self.env.close()
