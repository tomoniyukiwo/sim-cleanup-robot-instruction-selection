"""JSON-line Qwen3.5 runner. Launched by the existing AI worker as a child process."""
import gc
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from cleanup_robot.fewshot import build_messages, load_examples


def emit(value):
    sys.stdout.write(json.dumps(value, ensure_ascii=False) + '\n')
    sys.stdout.flush()


def main():
    init = json.loads(sys.stdin.readline())
    cfg, catalog = init['cfg'], init['catalog']
    fewshot_path = ROOT / cfg['fewshot_path']
    examples = load_examples(fewshot_path, catalog)
    import torch
    from transformers import AutoModelForMultimodalLM, AutoProcessor
    device = cfg.get('planner_device', 'cuda')
    if device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('Planner CUDA unavailable')
    start = time.perf_counter()
    path = Path(init['planner_path'])
    processor = AutoProcessor.from_pretrained(path, local_files_only=True, trust_remote_code=False)
    model = AutoModelForMultimodalLM.from_pretrained(
        path, local_files_only=True, trust_remote_code=False,
        dtype=torch.float16 if device == 'cuda' else torch.float32,
        device_map={'': device}, low_cpu_mem_usage=True).eval()
    emit({'ready': True, 'load_seconds': time.perf_counter() - start})
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            messages = build_messages(request['instruction'], request.get('context', []),
                                      catalog, examples)
            start = time.perf_counter()
            inputs = processor.apply_chat_template(
                messages, add_generation_prompt=True, tokenize=True,
                return_dict=True, return_tensors='pt', enable_thinking=False).to(model.device)
            with torch.inference_mode():
                output = model.generate(
                    **inputs, max_new_tokens=cfg.get('planner_max_new_tokens', 256),
                    do_sample=False, pad_token_id=processor.tokenizer.eos_token_id)
            seconds = time.perf_counter() - start
            raw = processor.decode(output[0, inputs['input_ids'].shape[1]:],
                                   skip_special_tokens=True)
            emit({'raw': raw, 'inference_seconds': seconds})
        except Exception as exc:
            emit({'error': repr(exc)})
    del model, processor
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        emit({'error': repr(exc)})
        raise
