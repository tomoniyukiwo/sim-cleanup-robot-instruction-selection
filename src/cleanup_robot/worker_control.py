"""Thread-safe commands from the ROS supervisor over worker stdin."""
import json
import threading
import time

class WorkerControl:
    def __init__(self,emit):
        self.emit=emit;self.cancelled=threading.Event();self.paused=threading.Event()
        self.retry_ready=threading.Event();self.retry_allowed=False
    def apply(self,command):
        kind=command.get('command')
        if kind=='cancel':self.cancelled.set();self.retry_ready.set()
        elif kind=='pause':self.paused.set()
        elif kind=='resume':self.paused.clear()
        elif kind=='retry':
            self.retry_allowed=command.get('allow') is True;self.retry_ready.set()
    def read(self,stream):
        for line in stream:
            try:self.apply(json.loads(line))
            except (ValueError,TypeError,AttributeError):self.emit('invalid_control_command')
        # Lost supervisor: stop before the next action, rather than run unattended.
        self.cancelled.set();self.retry_ready.set()
    def before_action(self):
        announced=False
        while self.paused.is_set() and not self.cancelled.is_set():
            if not announced:self.emit('paused');announced=True
            time.sleep(.05)
        if announced:self.emit('resumed')
        return not self.cancelled.is_set()
    def request_retry(self,attempt):
        self.retry_allowed=False;self.retry_ready.clear()
        self.emit('retry_requested',completed_attempt=attempt)
        deadline=time.monotonic()+30
        while not self.retry_ready.wait(.05):
            if self.cancelled.is_set() or time.monotonic()>=deadline:return False
        return self.retry_allowed and not self.cancelled.is_set()
