import json
from pathlib import Path

def prepare(cfg,out):
    from huggingface_hub import HfApi,snapshot_download,hf_hub_download
    from .contracts import validate_libero_smol_config
    out=Path(out)
    if out.exists():raise ValueError('Asset lock exists: choose another --out')
    out.parent.mkdir(parents=True,exist_ok=True)
    api=HfApi();lock={'schema_version':1,'assets_ready':False}
    # hf-libero needs meshes/textures even for inference. Prepare these before
    # run enables offline mode; no demonstration/training dataset is downloaded.
    assets_repo='lerobot/libero-assets'
    assets_info=api.dataset_info(assets_repo,revision='main')
    assets_dir=Path.home()/'.cache/libero/assets'
    print('Preparing LIBERO environment meshes/textures',flush=True)
    snapshot_download(assets_repo,repo_type='dataset',revision=assets_info.sha,
                      local_dir=str(assets_dir))
    lock['environment_assets']={'repo':assets_repo,'revision':assets_info.sha,'path':str(assets_dir)}
    # Check tokenizer access first, before downloading multi-GB policy weights.
    entries=[('tokenizer','tokenizer_repo','tokenizer_revision',
              ['tokenizer*','special_tokens_map.json','added_tokens.json','config.json','vocab*','merges.txt','*processor*','chat_template*']),
             ('embedding','embedding_repo','embedding_revision',None),
             ('policy','policy_repo','policy_revision',None)]
    for name,repo_key,revision_key,patterns in entries:
        repo=cfg[repo_key];info=api.model_info(repo,revision=cfg[revision_key])
        if name=='policy':
            config_path=hf_hub_download(repo,'config.json',revision=info.sha)
            validate_libero_smol_config(json.loads(Path(config_path).read_text()))
        print(f'Downloading {name}: {repo}@{info.sha}',flush=True)
        path=snapshot_download(repo,revision=info.sha,allow_patterns=patterns)
        lock[name]={'repo':repo,'revision':info.sha,'path':str(Path(path).resolve())}
    lock['assets_ready']=True
    out.write_text(json.dumps(lock,indent=2))
    print(f'Assets ready; resolved revisions recorded: {out}')

def load_lock(path):
    lock=json.loads(Path(path).read_text())
    if not lock.get('assets_ready'):raise ValueError('Incomplete assets lock')
    for name in ['policy','embedding','tokenizer','environment_assets']:
        if not Path(lock[name]['path']).is_dir():raise FileNotFoundError(f'{name} cache missing; prepare assets on this PC')
    return lock


def ensure_planner_lock(lock_path,base_lock_path=None):
    """Create a separate planner lock from an existing asset lock, never overwriting it."""
    path=Path(lock_path)
    if base_lock_path is None:
        if not path.is_file():
            raise FileNotFoundError(f'Planner lock missing: {path}. Pass --base-lock models/assets.lock.json to create it.')
        return path
    base=Path(base_lock_path)
    if path.resolve()==base.resolve():
        raise ValueError('--lock and --base-lock must differ to protect the working asset lock')
    if path.exists():
        if not path.is_file():raise ValueError(f'Planner lock path is not a file: {path}')
        return path
    if not base.is_file():raise FileNotFoundError(f'Base asset lock missing: {base}')
    data=json.loads(base.read_text())
    if not data.get('assets_ready'):
        raise ValueError('Base asset lock is incomplete')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:
        json.dump(data,stream,indent=2)
    print(f'Created separate planner lock from {base}: {path}',flush=True)
    return path


def prepare_planner(cfg,lock_path,base_lock_path=None):
    from datetime import datetime,timezone
    import os
    import shutil
    import tempfile
    from huggingface_hub import HfApi,snapshot_download
    path=ensure_planner_lock(lock_path,base_lock_path)
    lock=json.loads(path.read_text())
    repo=cfg['planner_repo']
    info=HfApi().model_info(repo,revision=cfg.get('planner_revision','main'))
    folder=snapshot_download(repo,revision=info.sha)
    if lock.get('planner',{}).get('revision')==info.sha and Path(lock['planner']['path']).is_dir():
        print('Planner already prepared');return
    backup=path.with_name(path.name+'.backup_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f'))
    shutil.copy2(path,backup)
    lock['planner']={'repo':repo,'revision':info.sha,'path':str(Path(folder).resolve())}
    with tempfile.NamedTemporaryFile('w',dir=path.parent,delete=False) as tmp:
        json.dump(lock,tmp,indent=2);temp=tmp.name
    os.replace(temp,path)
    print('Planner prepared; existing manipulation model entries preserved.')
