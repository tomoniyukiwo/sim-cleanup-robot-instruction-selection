"""Inspect cached model metadata without network or loading model weights."""
import argparse
import json
import os
from pathlib import Path
ap=argparse.ArgumentParser()
ap.add_argument('--cache-dir',default=os.environ.get('HF_HUB_CACHE',str(Path(os.environ.get('HF_HOME',str(Path.home()/'.cache/huggingface')))/'hub')))
args=ap.parse_args();root=Path(args.cache_dir).expanduser()
if not root.is_dir():raise SystemExit('Hugging Face cache directory was not found. Set --cache-dir.')
found=0
for repo in sorted(root.glob('models--*')):
    if not any(x in repo.name.lower() for x in ['lerobot','smolvla','smolvlm','minilm','paligemma']):continue
    for config in sorted(repo.glob('snapshots/*/config.json')):
        try:cfg=json.loads(config.read_text())
        except (OSError,json.JSONDecodeError):continue
        record={'repo':repo.name.removeprefix('models--').replace('--','/'),
                'revision':config.parent.name,'policy_type':cfg.get('type',cfg.get('model_type')),
                'input_features':cfg.get('input_features'),'output_features':cfg.get('output_features'),
                'has_weights':any(config.parent.glob('*.safetensors')) or any(config.parent.glob('pytorch_model*.bin')),
                'has_preprocessor':(config.parent/'policy_preprocessor.json').is_file()}
        print(json.dumps(record,ensure_ascii=False,indent=2));found+=1
if found==0:print('No matching cached configs found. This does not prove model weights are absent elsewhere.')
print('Cache presence alone does not establish that a model is trained for LIBERO.')
