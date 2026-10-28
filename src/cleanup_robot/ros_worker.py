"""ML process: no rclpy import. JSON lines connect it to the ROS process."""
import argparse
from contextlib import redirect_stdout
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time

PREFIX='CLEANUP_EVENT '

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--request',type=Path,required=True);args=ap.parse_args()
    request=json.loads(args.request.read_text());out=args.request.parent
    wire=sys.stdout
    event_file=(out/'events.jsonl').open('w')
    def emit(event,**fields):
        value={'event':event,'request_id':request['request_id'],'wall_time':time.time(),**fields}
        line=json.dumps(value,ensure_ascii=False)
        event_file.write(line+'\n');event_file.flush();wire.write(PREFIX+line+'\n');wire.flush()
    from .worker_control import WorkerControl
    control=WorkerControl(emit)
    threading.Thread(target=control.read,args=(sys.stdin,),daemon=True).start()
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    backend=None;recorder=None;report={'success':False,'reason':'initialization_error'}
    cfg=json.loads(Path(request['config']).read_text())
    catalog=json.loads(Path(request['catalog']).read_text())
    lock=json.loads(Path(request['lock']).read_text())
    try:
        if catalog['suite']!=cfg['suite']:raise ValueError('Catalog/config suite mismatch')
        with redirect_stdout(sys.stderr):
            from .planner import plan_local
            emit('planning_started')
            plan,raw=plan_local(request['instruction'],request.get('context',[]),catalog,cfg,lock,
                                cancelled=control.cancelled.is_set)
            (out/'plan.json').write_text(json.dumps({'plan':plan,'raw_output':raw},ensure_ascii=False,indent=2))
            emit('plan_ready',plan=plan)
            if plan['decision']!='execute':
                report={'success':False,'reason':plan['decision'],'plan':plan};return
            if control.cancelled.is_set():raise InterruptedError('Cancelled before execution')
            from .backend import LiberoBackend
            from .controller import execute
            from .video import Recorder
            emit('loading_executor',planner_released=True)
            backend=LiberoBackend(cfg,lock,plan['task'],request.get('seed',42),request.get('init_state',0))
            if control.cancelled.is_set():raise InterruptedError('Cancelled during executor loading')
            recorder=Recorder(out/'demo.mp4',cfg['video_fps'],backend.control_hz,plan['task']['instruction'],
                              speed=cfg.get('playback_speed',1))
            last_progress=[-1]
            def on_step(obs,step,attempt,status):
                recorder(obs,step,attempt,status)
                if step//20!=last_progress[0]:
                    last_progress[0]=step//20;emit('progress',step=step,attempt=attempt,status=status)
            emit('execution_started',task_id=plan['task_id'])
            report=execute(backend,request['instruction'],plan['task']['instruction'],
                steps_per_attempt=cfg['steps_per_attempt'],max_attempts=cfg['max_attempts'],
                on_event=lambda event:emit(event['event'],**{k:v for k,v in event.items() if k!='event'}),
                on_step=on_step,before_action=control.before_action,on_retry=control.request_retry)
            recorder.finish(report['success'])
            report['plan']=plan
    except InterruptedError:
        report={'success':False,'reason':'cancelled'}
    except Exception as exc:
        if hasattr(exc,'raw_output'):(out/'planner_raw.txt').write_text(exc.raw_output)
        report={'success':False,'reason':'runtime_error','exception':repr(exc)}
        emit('worker_error',message=repr(exc))
        raise
    finally:
        if recorder is not None:recorder.close()
        if backend is not None:backend.close()
        report.update(request=request,config=cfg,assets=lock,
            catalog_sha256=hashlib.sha256(Path(request['catalog']).read_bytes()).hexdigest(),
            success_source='LIBERO goal predicate',retry_mode='ROS-authorized continuation; no environment reset')
        (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        emit('finished',success=report['success'],reason=report['reason'])
        event_file.close()

if __name__=='__main__':main()
