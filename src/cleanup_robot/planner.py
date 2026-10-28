"""Non-VLA local LLM selects a registered task or asks for clarification."""
import json

SYSTEM = """You are a robot task planner. Match the user's Japanese or English request to EXACTLY ONE task in the supplied catalog. The catalog is the ONLY set of available tasks. Preserve object names, destination and spatial relations. Do not invent tasks or claim to see a scene. If the request is ambiguous or missing object/destination, ask a short clarification question in Japanese; do not guess. Reject unrelated or impossible requests. Return ONE JSON object only, no markdown or analysis:
{"decision":"execute|clarify|reject","task_id":integer_or_null,"message":"brief Japanese explanation or question","retry_on_timeout":true_or_false}
For execute choose a catalog task_id. For clarify/reject task_id MUST be null and retry_on_timeout MUST be false. retry_on_timeout means that ROS may retry from the current physical state after a time budget, NOT that you have diagnosed the failure."""


def validate_plan(text,catalog):
    text=text.strip()
    if text.startswith('```'):
        lines=text.splitlines();text='\n'.join(lines[1:-1]) if lines[-1].startswith('```') else text
    plan=json.loads(text)
    if not isinstance(plan,dict) or set(plan)!={'decision','task_id','message','retry_on_timeout'}:
        raise ValueError('Planner output must contain exactly the four schema keys')
    if plan['decision'] not in ['execute','clarify','reject']:raise ValueError('Unknown planner decision')
    if not isinstance(plan['message'],str) or not 1<=len(plan['message'])<=600:raise ValueError('Invalid planner message')
    if type(plan['retry_on_timeout']) is not bool:raise ValueError('retry_on_timeout must be boolean')
    if plan['decision']=='execute':
        if type(plan['task_id']) is not int:raise ValueError('Integer task_id required')
        matches=[t for t in catalog['tasks'] if t['task_id']==plan['task_id']]
        if len(matches)!=1:raise ValueError('Planner chose an unregistered task')
        plan['task']=matches[0]
    elif plan['task_id'] is not None or plan['retry_on_timeout']:
        raise ValueError('Non-execution decisions cannot select a task or request retry')
    return plan


def plan_local(instruction, context, catalog, cfg, lock, cancelled=lambda: False):
    if cfg.get('planner_backend') != 'qwen35_bridge':
        raise ValueError('Qwen3.5 bridge config required')
    from .planner_bridge import plan_via_bridge
    return plan_via_bridge(instruction, context, catalog, cfg, lock, cancelled)
