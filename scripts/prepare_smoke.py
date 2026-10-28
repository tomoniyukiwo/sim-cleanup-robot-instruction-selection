"""Local checkpoint view with local tokenizer path; original cache stays unchanged."""
import json
import os
from pathlib import Path
lock=json.loads(Path('models/assets.lock.json').read_text())
src=Path(lock['policy']['path']);dst=Path('models/smoke_policy')
if dst.exists():
    print('Existing models/smoke_policy preserved. Rename it only if the assets lock changed.')
    raise SystemExit(0)
dst.mkdir(parents=True)
for path in src.iterdir():
    if path.name in ['policy_preprocessor.json','config.json']:continue
    (dst/path.name).symlink_to(path.resolve(),target_is_directory=path.is_dir())
processor=json.loads((src/'policy_preprocessor.json').read_text())
for step in processor['steps']:
    if step['registry_name']=='tokenizer_processor':step['config']['tokenizer_name']=lock['tokenizer']['path']
(dst/'policy_preprocessor.json').write_text(json.dumps(processor,indent=2))
print(dst)

config=json.loads((src/'config.json').read_text())
config['vlm_model_name']=lock['tokenizer']['path']
config['load_vlm_weights']=False
(dst/'config.json').write_text(json.dumps(config,indent=2))
