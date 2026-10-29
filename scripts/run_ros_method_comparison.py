#!/usr/bin/python3
"""Send fixed indirect cases over ROS and record independent runs for each selector."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import uuid

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

ROOT = Path(__file__).resolve().parents[1]


def indirect_cases(path, task_ids):
    cases = json.loads(path.read_text())['cases']
    selected = [case for case in cases if case['kind'] == 'indirect'
                and case['expected_task_id'] in task_ids]
    if len(selected) != len(task_ids) or {c['expected_task_id'] for c in selected} != set(task_ids):
        raise ValueError('Expected one indirect case per selected task')
    if any(c['expected_decision'] != 'execute' or c['context'] for c in selected):
        raise ValueError('Comparison only supports fixed independent execute cases')
    return selected


def summarize(rows):
    result = {}
    for method in sorted({row['method'] for row in rows}):
        group = [row for row in rows if row['method'] == method]
        result[method] = {
            'requests': len(group),
            'correct_selection': sum(r['decision'] == 'execute' and
                                     r['selected_task_id'] == r['expected_task_id'] for r in group),
            'wrong_selection': sum(r['decision'] == 'execute' and
                                   r['selected_task_id'] != r['expected_task_id'] for r in group),
            'held_or_clarified': sum(r['decision'] != 'execute' for r in group),
            'physical_executions': sum(r['decision'] == 'execute' for r in group),
            'physical_goal_satisfied': sum(bool(r['success']) for r in group),
            'end_to_end_success': sum(r['decision'] == 'execute' and
                                      r['selected_task_id'] == r['expected_task_id'] and
                                      r['success'] is True for r in group),
        }
    return result


class Client(Node):
    def __init__(self):
        super().__init__('cleanup_comparison_client')
        self.publisher = self.create_publisher(String, '/cleanup/instruction', 10)
        self.messages = []
        self.create_subscription(String, '/cleanup/status', self.on_status, 50)

    def on_status(self, msg):
        try:
            self.messages.append(json.loads(msg.data))
        except ValueError:
            pass

    def wait_for(self, predicate, timeout, process):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            rclpy.spin_once(self, timeout_sec=.2)
            if process.poll() is not None:
                raise RuntimeError(f'ROS supervisor exited with {process.returncode}')
            found = next((m for m in self.messages if predicate(m)), None)
            if found is not None:
                return found
        raise TimeoutError('Timed out waiting for ROS status')


def run_case(client, process, case, method):
    client.messages.clear()
    message = String()
    message.data = case['instruction']
    client.publisher.publish(message)
    started = client.wait_for(lambda m: m.get('state') == 'planning' and
                              m.get('selector') == method, 30, process)
    request_id = started['request_id']
    client.wait_for(lambda m: m.get('state') == 'finished' and
                    m.get('request_id') == request_id, 900, process)
    client.wait_for(lambda m: m.get('state') == 'ready', 30, process)
    return load_result(request_id, case, method)


def load_result(request_id, case, method):
    run = ROOT / 'outputs/ros' / request_id
    request = json.loads((run / 'request.json').read_text())
    plan_file = json.loads((run / 'plan.json').read_text())
    result = json.loads((run / 'result.json').read_text())
    plan = plan_file['plan']
    if request['instruction'] != case['instruction'] or request['selector'] != method:
        raise ValueError('ROS request does not match the submitted case/method')
    if result['selector'] != method or result['request']['request_id'] != request_id:
        raise ValueError('ROS result does not match request/method')
    video = run / 'demo.mp4'
    if plan['decision'] == 'execute' and not video.is_file():
        raise FileNotFoundError(f'Executed request has no video: {request_id}')
    if plan['decision'] != 'execute' and video.exists():
        raise ValueError(f'Non-execution request unexpectedly has a video: {request_id}')
    return {'method': method, 'case_id': case['id'],
            'instruction': case['instruction'], 'expected_task_id': case['expected_task_id'],
            'request_id': request_id, 'decision': plan['decision'],
            'selected_task_id': plan['task_id'], 'planning_wall_seconds': result['planning_wall_seconds'],
            'success': result['success'] if plan['decision'] == 'execute' else None,
            'reason': result['reason'], 'steps': result.get('steps'),
            'operation_wall_seconds': result.get('wall_seconds'),
            'video_available': video.is_file()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cases', type=Path, default=ROOT / 'tasks/comparison_cases_qwen35.json')
    ap.add_argument('--config', type=Path, default=Path('configs/ros_comparison.json'))
    ap.add_argument('--task-ids', type=int, nargs='+', default=list(range(1, 10)))
    ap.add_argument('--methods', nargs='+', choices=['qwen', 'minilm'], default=['qwen', 'minilm'])
    ap.add_argument('--out', type=Path)
    ap.add_argument('--resume', action='store_true', help='Continue a saved partial manifest')
    ap.add_argument('--recover-request-id', action='append', default=[],
                    help='Add a finished ROS request that was saved before a runner interruption')
    ap.add_argument('--ros-domain-id', type=int,
                    help='ROS domain for this comparison; defaults to an isolated random domain')
    args = ap.parse_args()
    if len(set(args.task_ids)) != len(args.task_ids) or len(set(args.methods)) != len(args.methods):
        ap.error('Task IDs and methods must be unique')
    cases_path = args.cases.resolve()
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text())
    steps_per_attempt = config['steps_per_attempt']
    max_attempts = config['max_attempts']
    if max_attempts != 1 or not isinstance(steps_per_attempt, int) or steps_per_attempt <= 0:
        ap.error('ROS comparison requires one attempt and a positive step budget')
    cases = indirect_cases(cases_path, args.task_ids)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = args.out or ROOT / 'outputs/ros_comparison' / f'{stamp}_{uuid.uuid4().hex[:8]}'
    if args.resume:
        if not (out / 'manifest.json').is_file():
            ap.error('--resume requires an existing manifest.json')
        manifest = json.loads((out / 'manifest.json').read_text())
        if manifest['methods'] != args.methods or manifest['task_ids'] != args.task_ids:
            ap.error('Saved methods/task IDs differ from this invocation')
        if manifest['steps_per_attempt'] != steps_per_attempt or manifest['config'] != str(config_path.relative_to(ROOT)):
            ap.error('Saved step budget/config differs from this invocation')
        rows = manifest['runs']
    else:
        out.mkdir(parents=True, exist_ok=False)
        rows = []
        manifest = {'schema_version': 1, 'input_transport': 'ROS 2 /cleanup/instruction',
                    'cases': str(cases_path.relative_to(ROOT)),
                    'config': str(config_path.relative_to(ROOT)), 'seed': 42, 'init_state': 0,
                    'steps_per_attempt': steps_per_attempt, 'max_attempts': max_attempts,
                    'methods': args.methods, 'task_ids': args.task_ids, 'runs': rows}
    for request_id in args.recover_request_id:
        request = json.loads((ROOT / 'outputs/ros' / request_id / 'request.json').read_text())
        method = request['selector']
        matches = [case for case in cases if case['instruction'] == request['instruction']]
        if method not in args.methods or len(matches) != 1:
            raise ValueError(f'Recovered request is outside this experiment: {request_id}')
        case = matches[0]
        if any(row['case_id'] == case['id'] and row['method'] == method for row in rows):
            raise ValueError(f'Already recorded: {method} {case["id"]}')
        rows.append(load_result(request_id, case, method))
        manifest['summary'] = summarize(rows)
        (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    env = os.environ.copy()
    env['ROS_DOMAIN_ID'] = str(args.ros_domain_id if args.ros_domain_id is not None
                               else 20 + uuid.uuid4().int % 60)
    env['ROS_LOCALHOST_ONLY'] = '1'
    os.environ.update(ROS_DOMAIN_ID=env['ROS_DOMAIN_ID'], ROS_LOCALHOST_ONLY='1')
    rclpy.init()
    client = Client()
    try:
        for method in args.methods:
            pending = [case for case in cases if not any(row['case_id'] == case['id'] and
                       row['method'] == method for row in rows)]
            if not pending:
                continue
            log_path = out / f'supervisor_{method}.log'
            if log_path.exists():
                suffix = 1
                while (out / f'supervisor_{method}_{suffix}.log').exists():
                    suffix += 1
                log_path = out / f'supervisor_{method}_{suffix}.log'
            with log_path.open('x') as log:
                process = subprocess.Popen(['bash', 'scripts/run_ros.sh',
                    '--config', str(config_path),
                    '--lock', 'models/assets.qwen35.lock.json', '--selector', method],
                    cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=True)
                try:
                    client.messages.clear()
                    client.wait_for(lambda m: client.publisher.get_subscription_count() > 0,
                                    30, process)
                    for case in pending:
                        row = run_case(client, process, case, method)
                        rows.append(row)
                        manifest['summary'] = summarize(rows)
                        (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False,
                            indent=2) + '\n')
                        print(f'{method} task {row["expected_task_id"]}: {row["decision"]} '
                              f'task={row["selected_task_id"]} success={row["success"]}', flush=True)
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGINT)
                        try: process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGTERM)
                            try: process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                os.killpg(process.pid, signal.SIGKILL)
                                process.wait(timeout=5)
        print(f'Saved {out}: {len(rows)} ROS requests', flush=True)
    finally:
        client.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
