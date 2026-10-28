"""Fixed task-0 prompt examples for the Qwen3.5 held-out evaluation."""
import json
from pathlib import Path

from .planner import SYSTEM, validate_plan


def load_examples(path, catalog):
    data = json.loads(Path(path).read_text())
    if data.get('schema_version') != 1 or data.get('suite') != catalog.get('suite'):
        raise ValueError('Few-shot suite/schema mismatch')
    if data.get('example_task_id') != 0:
        raise ValueError('Few-shot file must use task 0 only')
    task0 = next((t for t in catalog['tasks'] if t['task_id'] == 0), None)
    if task0 is None or not data.get('examples'):
        raise ValueError('Task 0 or examples missing')
    examples = []
    for item in data['examples']:
        if not isinstance(item['instruction'], str) or not item['instruction'].strip():
            raise ValueError('Empty few-shot instruction')
        answer = dict(item['answer'])
        validate_plan(json.dumps(answer, ensure_ascii=False), catalog)
        if answer['decision'] != 'execute' or answer['task_id'] != 0:
            raise ValueError('Few-shot answers must execute task 0')
        examples.append({'instruction': item['instruction'], 'answer': answer})
    if examples[0]['instruction'] != task0['instruction']:
        raise ValueError('First example must be canonical task 0')
    return examples


def build_messages(instruction, context, catalog, examples):
    registered = [{'task_id': t['task_id'], 'instruction': t['instruction']}
                  for t in catalog['tasks']]
    messages = [{'role': 'system', 'content': SYSTEM}]
    for item in examples:
        payload = {'request': item['instruction'], 'clarification_context': [],
                   'catalog': registered}
        messages.append({'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)})
        messages.append({'role': 'assistant', 'content': json.dumps(item['answer'], ensure_ascii=False)})
    payload = {'request': instruction, 'clarification_context': context,
               'catalog': registered}
    messages.append({'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)})
    return messages
