#!/usr/bin/env python3
"""Run with ROS's system Python; ML lives in a separate uv Python process."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import uuid
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import SetBool,Trigger

PREFIX='CLEANUP_EVENT '

class Supervisor(Node):
    def __init__(self,root,config_path=None,lock_path=None):
        super().__init__('cleanup_supervisor')
        self.root=root;self.process=None;self.mail=queue.Queue();self.reader_done=threading.Event()
        self.config_path=config_path or root/'configs/default.json'
        self.lock_path=lock_path or root/'models/assets.qwen35.lock.json'
        self.plan=None;self.dialogue_context=[];self.last_instruction='';self.cancel_pending=False;self.log=None
        self.status_pub=self.create_publisher(String,'/cleanup/status',10)
        self.plan_pub=self.create_publisher(String,'/cleanup/plan',10)
        self.event_pub=self.create_publisher(String,'/cleanup/events',50)
        self.create_subscription(String,'/cleanup/instruction',self.on_instruction,10)
        self.create_service(SetBool,'/cleanup/pause',self.on_pause)
        self.create_service(Trigger,'/cleanup/cancel',self.on_cancel)
        self.create_timer(.1,self.poll)
        self.status('ready')
    def publish(self,pub,value):
        msg=String();msg.data=json.dumps(value,ensure_ascii=False);pub.publish(msg)
    def status(self,state,**fields):
        value={'state':state,**fields};self.publish(self.status_pub,value)
        self.get_logger().info(json.dumps(value,ensure_ascii=False))
    def command(self,value):
        if self.process is None or self.process.poll() is not None:return False
        try:
            self.process.stdin.write(json.dumps(value)+'\n');self.process.stdin.flush();return True
        except (BrokenPipeError,OSError):return False
    def on_instruction(self,msg):
        if self.process is not None:
            self.status('busy',message='Wait for the current request or cancel it first.');return
        text=msg.data.strip()
        if not text or len(text)>4000:self.status('invalid_instruction');return
        worker=self.root/'.venv-uv/bin/python'
        if not worker.is_file():self.status('setup_required',message='Run uv setup first');return
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
        rid=f'{stamp}_{uuid.uuid4().hex[:8]}'
        out=self.root/'outputs/ros'/rid;out.mkdir(parents=True)
        request={'request_id':rid,'instruction':text,'context':self.dialogue_context,
                 'config':str(self.config_path),'catalog':str(self.root/'tasks/libero_object.json'),
                 'lock':str(self.lock_path),'seed':42,'init_state':0}
        path=out/'request.json';path.write_text(json.dumps(request,ensure_ascii=False,indent=2))
        self.last_instruction=text;self.plan=None;self.cancel_pending=False;self.reader_done.clear()
        env=os.environ.copy()
        for key in ['PYTHONPATH','PYTHONHOME','VIRTUAL_ENV','AMENT_PREFIX_PATH','COLCON_PREFIX_PATH']:
            env.pop(key,None)
        # Avoid ROS's bundled libraries shadowing the ML environment's CUDA/video libraries.
        if 'LD_LIBRARY_PATH' in env:
            env['LD_LIBRARY_PATH']=':'.join(x for x in env['LD_LIBRARY_PATH'].split(':') if '/opt/ros/' not in x)
        self.log=(out/'worker.log').open('w')
        try:
            self.process=subprocess.Popen([str(worker),'-m','cleanup_robot.ros_worker','--request',str(path)],
                cwd=self.root,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,
                text=True,bufsize=1)
        except Exception as exc:
            self.log.close();self.log=None;self.status('worker_start_error',message=repr(exc));return
        process=self.process
        def read():
            try:
                for line in process.stdout:
                    if line.startswith(PREFIX):
                        try:self.mail.put(json.loads(line[len(PREFIX):]))
                        except json.JSONDecodeError:pass
            finally:self.reader_done.set()
        threading.Thread(target=read,daemon=True).start()
        self.status('planning',request_id=rid,output=str(out))
    def on_pause(self,request,response):
        command='pause' if request.data else 'resume'
        response.success=self.command({'command':command})
        response.message='Requested; applies at next action boundary' if response.success else 'No active worker'
        if response.success:self.status(command+'_requested')
        return response
    def on_cancel(self,request,response):
        self.cancel_pending=True
        response.success=self.command({'command':'cancel'})
        response.message='Cancellation requested' if response.success else 'No active worker'
        if response.success:self.status('cancel_requested')
        return response
    def poll(self):
        while True:
            try:event=self.mail.get_nowait()
            except queue.Empty:break
            self.publish(self.event_pub,event);kind=event['event']
            if kind=='plan_ready':
                self.plan=event['plan'];self.publish(self.plan_pub,self.plan)
                self.status(self.plan['decision'],message=self.plan['message'])
            elif kind=='retry_requested':
                # ROS authorizes retries; the worker cannot proceed on its own.
                allow=bool(self.plan and self.plan['retry_on_timeout'] and not self.cancel_pending)
                self.command({'command':'retry','allow':allow})
                self.status('retry_authorized' if allow else 'retry_declined',attempt=event['completed_attempt'])
            elif kind=='finished':
                if event['reason']=='clarify' and self.plan:
                    self.dialogue_context=(self.dialogue_context+[{'request':self.last_instruction,'question':self.plan['message']}])[-2:]
                else:self.dialogue_context=[]
                self.status('finished',success=event['success'],reason=event['reason'])
            elif kind in ['paused','resumed','execution_started','worker_error','loading_executor','progress']:
                self.status(kind,**{k:v for k,v in event.items() if k!='event'})
        if self.process is not None and self.process.poll() is not None and self.reader_done.is_set():
            code=self.process.returncode
            self.process.stdin.close();self.process.stdout.close();self.process=None
            if self.log:self.log.close();self.log=None
            if code:self.status('worker_failed',exit_code=code,message='See worker.log in the run folder')
            self.status('ready')
    def close(self):
        if self.process is not None:
            self.command({'command':'cancel'})
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
            if self.log:self.log.close()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument('--config',type=Path,default=Path('configs/default.json'))
    ap.add_argument('--lock',type=Path,default=Path('models/assets.qwen35.lock.json'))
    args,ros_args=ap.parse_known_args();root=args.root.resolve()
    config=args.config if args.config.is_absolute() else root/args.config
    lock=args.lock if args.lock.is_absolute() else root/args.lock
    rclpy.init(args=ros_args);node=Supervisor(root,config,lock)
    try:rclpy.spin(node)
    except KeyboardInterrupt:pass
    finally:
        node.close();node.destroy_node()
        if rclpy.ok():rclpy.shutdown()

if __name__=='__main__':main()
