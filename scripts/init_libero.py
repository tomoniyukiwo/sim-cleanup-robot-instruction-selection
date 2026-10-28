"""Create project-local LIBERO paths before imports, avoiding an interactive prompt."""
import importlib.util
import os
from pathlib import Path
import yaml
spec=importlib.util.find_spec('libero')
if spec is None or not spec.submodule_search_locations:raise SystemExit('hf-libero is not installed')
root=Path(next(iter(spec.submodule_search_locations)))/'libero'
if not (root/'bddl_files').is_dir():raise SystemExit('Installed LIBERO layout is unexpected')
folder=Path(os.environ.get('LIBERO_CONFIG_PATH',str(Path.cwd()/'.libero')))
folder.mkdir(parents=True,exist_ok=True)
path=folder/'config.yaml'
if path.exists():
    print('Existing LIBERO config preserved.')
else:
    paths={'benchmark_root':str(root),'bddl_files':str(root/'bddl_files'),
           'init_states':str(root/'init_files'),'datasets':str(root.parent/'datasets'),'assets':str(root/'assets')}
    path.write_text(yaml.safe_dump(paths))
    print('Project-local LIBERO config initialized.')
