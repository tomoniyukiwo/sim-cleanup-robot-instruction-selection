import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path


def main():
    ap=argparse.ArgumentParser(description='Local instruction -> manipulation -> goal check -> retry')
    ap.add_argument('--config',default='configs/default.json')
    sub=ap.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('prepare');p.add_argument('--out',default='models/assets.lock.json')
    p=sub.add_parser('prepare-planner');p.add_argument('--lock',default='models/assets.qwen35.lock.json')
    p.add_argument('--base-lock',default='models/assets.lock.json',help='Base asset lock used if the planner lock is missing')
    p=sub.add_parser('catalog');p.add_argument('--out',default='tasks/libero_object.json')
    p=sub.add_parser('doctor')
    for name in ['route','run']:
        p=sub.add_parser(name)
        p.add_argument('--catalog',default='tasks/libero_object.json')
        p.add_argument('--lock',default='models/assets.lock.json')
        p.add_argument('--instruction',required=True)
        p.add_argument('--task-id',type=int,help='Explicit user selection; bypass semantic routing')
        if name=='run':
            p.add_argument('--instruction-mode',choices=['raw','canonical'],default='canonical')
            p.add_argument('--seed',type=int,default=42)
            p.add_argument('--init-state',type=int,default=0)
            p.add_argument('--out',required=True)
            p.add_argument('--steps-per-attempt',type=int)
            p.add_argument('--max-attempts',type=int)
            p.add_argument('--playback-speed',type=float,help='Saved video speed: 1=simulation speed, .5=half speed')
    args=ap.parse_args();cfg=json.loads(Path(args.config).read_text())
    if args.cmd=='run':
        for key in ['steps_per_attempt','max_attempts']:
            if getattr(args,key) is not None:cfg[key]=getattr(args,key)
        if cfg['steps_per_attempt']<1 or cfg['max_attempts']<1:ap.error('Positive step/attempt budgets required')
        if args.playback_speed is not None:cfg['playback_speed']=args.playback_speed
    if args.cmd=='prepare':
        from .assets import prepare
        prepare(cfg,args.out);return
    if args.cmd=='prepare-planner':
        from .assets import prepare_planner
        prepare_planner(cfg,args.lock,args.base_lock);return
    if args.cmd=='catalog':
        from .catalog import create_catalog
        create_catalog(cfg['suite'],args.out);return
    if args.cmd=='doctor':
        doctor();return
    # Local inference only. Network is used only by setup/prepare.
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    from .assets import load_lock
    from .routing import Router
    lock=load_lock(args.lock);catalog=json.loads(Path(args.catalog).read_text())
    if catalog['suite']!=cfg['suite']:raise ValueError('Config/catalog suite mismatch')
    decision=Router(catalog,lock['embedding']['path'],cfg).route(args.instruction,args.task_id)
    print(json.dumps(decision,ensure_ascii=False,indent=2),flush=True)
    if args.cmd=='route':return
    out=Path(args.out)
    if out.exists():raise ValueError('Output exists: choose a new --out')
    out.mkdir(parents=True)
    (out/'route.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2))
    if not decision['accepted']:
        (out/'result.json').write_text(json.dumps({'success':False,'reason':'instruction_ambiguous','route':decision},ensure_ascii=False,indent=2))
        raise SystemExit('Instruction ambiguous. Review ranking/task list; clarify instruction or explicitly choose --task-id.')
    from .backend import LiberoBackend
    from .controller import execute
    from .video import Recorder
    backend=None;recorder=None;report={'success':False,'reason':'initialization_error'}
    with (out/'events.jsonl').open('w') as events:
        def log(event):
            line=json.dumps(event,ensure_ascii=False);events.write(line+'\n');events.flush();print(line,flush=True)
        try:
            backend=LiberoBackend(cfg,lock,decision['task'],args.seed,args.init_state)
            recorder=Recorder(out/'demo.mp4',cfg['video_fps'],backend.control_hz,decision['task']['instruction'],speed=cfg.get('playback_speed',1.0))
            report=execute(backend,args.instruction,decision['task']['instruction'],
                steps_per_attempt=cfg['steps_per_attempt'],max_attempts=cfg['max_attempts'],
                instruction_mode=args.instruction_mode,on_event=log,on_step=recorder)
            recorder.finish(report['success'])
        except KeyboardInterrupt:
            report={'success':False,'reason':'interrupted'};raise
        except Exception as exc:
            report={'success':False,'reason':'runtime_error','exception':repr(exc)};raise
        finally:
            if recorder is not None:recorder.close()
            if backend is not None:backend.close()
            report.update(instruction=args.instruction,route=decision,config=cfg,
                          seed=args.seed,init_state=args.init_state,instruction_mode=args.instruction_mode,
                          assets=lock,success_source='LIBERO built-in goal predicate; not image AI',
                          retry_mode='continue_current_state; no environment reset between attempts',
                          catalog_sha256=hashlib.sha256(Path(args.catalog).read_bytes()).hexdigest(),
                          python=platform.python_version())
            (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(f'Result: {report["reason"]}; output: {out}')

def doctor():
    import torch
    print('Python:',platform.python_version())
    for name in ['lerobot','torch','torchvision','transformers','hf-libero','sentence-transformers']:
        try:print(name,importlib.metadata.version(name))
        except importlib.metadata.PackageNotFoundError:print(name,'MISSING')
    if importlib.metadata.version('lerobot')!='0.4.4':raise RuntimeError('Expected LeRobot 0.4.4')
    print('CUDA available:',torch.cuda.is_available())
    if torch.cuda.is_available():print('GPU:',torch.cuda.get_device_name(0))
    from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy
    from lerobot.envs.libero import LiberoEnv
    print('Policy/environment imports OK (weights not loaded; rendering not tested)')

if __name__=='__main__':main()
