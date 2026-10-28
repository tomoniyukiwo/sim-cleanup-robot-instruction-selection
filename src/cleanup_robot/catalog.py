import json
from pathlib import Path

def create_catalog(suite_name,out):
    from libero.libero import benchmark
    suite=benchmark.get_benchmark_dict()[suite_name]()
    out=Path(out)
    if out.exists():raise ValueError('Task catalog exists: choose another --out')
    tasks=[{'task_id':i,'name':suite.get_task(i).name,
            'instruction':suite.get_task(i).language,'aliases':[]} for i in range(len(suite.tasks))]
    payload={'suite':suite_name,'tasks':tasks}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    for t in tasks:print(f"{t['task_id']}: {t['instruction']}")
    return payload
