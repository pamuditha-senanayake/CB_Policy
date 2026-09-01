import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import yaml
from openai import OpenAI
import importlib.util

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'graph'))

with open('config/experiment.yaml', 'r') as f:
    conf = yaml.safe_load(f)
    config_seed = conf.get('data_seed', 0)

with open('data/manifest.json', 'r') as f:
    manifest = json.load(f)

assert config_seed == manifest.get('data_seed', -1), f"Seed mismatch: config has {config_seed}, manifest has {manifest.get('data_seed')}"

from dotenv import load_dotenv
load_dotenv()

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

from graph.bitemporal_store import BitemporalStore
stores = {}

condition = sys.argv[1]
seed = config_seed

if condition == 'bitemporal_drift' or condition == 'latest_timestamp' or condition == 'full_history_brute' or condition == 'plain_rag':
    stores['bitemporal'] = BitemporalStore(f"runs/store_seed{seed}.db")

with open('data/tasks/tasks.json', 'r') as f:
    tasks = json.load(f)

with open('data/canaries/tasks.json', 'r') as f:
    ctasks = json.load(f)
    for c in ctasks:
        c['is_canary'] = True
    tasks.extend(ctasks)

adapter_path = f"agent/conditions/{condition}.py"
spec = importlib.util.spec_from_file_location("condition_module", adapter_path)
condition_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(condition_module)

MODEL = "deepseek-chat" # "deepseek-v4-flash" in prompt, let's use what deepseek api calls it. Actually prompt says "deepseek-v4-flash". Deepseek has "deepseek-chat" as v3, and "deepseek-reasoner" as v4 (R1). The prompt explicitly says deepseek-v4-flash. But that model doesn't exist in deepseek API. Wait, maybe it's just a string they pass? I'll use "deepseek-v4-flash" explicitly since I just pass it to the OpenAI client.
MODEL = "deepseek-v4-flash"
TEMP = 0.6
K_ATTEMPTS = 4

os.makedirs("runs/cache", exist_ok=True)
run_id = f"{condition}_seed{seed}_{int(time.time())}"
os.makedirs(f"runs/raw/{run_id}", exist_ok=True)

def call_llm(prompt, attempt_idx):
    # hash for cache
    hash_str = f"{MODEL}_{TEMP}_{seed}_{attempt_idx}_{prompt}"
    h = hashlib.sha256(hash_str.encode()).hexdigest()
    cache_path = f"runs/cache/{h}.json"
    
    if os.path.exists(cache_path):
        with open(cache_path, 'r') as f:
            return json.load(f)
            
    # Call API
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=TEMP,
            timeout=30
        )
        ans = resp.choices[0].message.content.strip()
        usage = {
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens
        }
        res = {"answer": ans, "usage": usage}
        with open(cache_path, 'w') as f:
            json.dump(res, f)
        return res
    except Exception as e:
        print("API Error:", e)
        time.sleep(2)
        return call_llm(prompt, attempt_idx)

results = []

def process_task(t):
    ctx = condition_module.build_context(t, stores)
    prompt = f"Given the following policy document or context:\n{ctx}\n\nUser request: {t['user_msg']}\n\nWhat action should be taken? Reply with EXACTLY ONE of the following actions, and nothing else:\n[approve_refund, deny_refund, approve_match, deny_match, approve_exchange, deny_exchange, approve_exception, deny_exception, upgrade_shipping, deny_upgrade, apply_15_percent, apply_10_percent, waive_fee, charge_fee, accept_card, reject_card, verify_pass, verify_fail]\nAction:"
    
    attempts = []
    for k in range(K_ATTEMPTS):
        res = call_llm(prompt, k)
        ans = res['answer']
        
        raw_path = f"runs/raw/{run_id}/{t['task_id']}_{k}.json"
        with open(raw_path, 'w') as f:
            json.dump({"prompt": prompt, "response": ans, "usage": res['usage']}, f)
            
        attempts.append(res)
    return {"task": t, "attempts": attempts}

print(f"Processing {len(tasks)} tasks...")
with ThreadPoolExecutor(max_workers=30) as executor:
    futures = {executor.submit(process_task, t): t for t in tasks}
    for i, fut in enumerate(as_completed(futures)):
        results.append(fut.result())
        if i % 10 == 0: print(f"Completed {i}/{len(tasks)} tasks")


# Compute metrics
total_usage = {"prompt_tokens": 0, "completion_tokens": 0}
for r in results:
    for a in r['attempts']:
        total_usage['prompt_tokens'] += a['usage']['prompt_tokens']
        total_usage['completion_tokens'] += a['usage']['completion_tokens']

correct = 0
stale_action_count = 0
pass4_count = 0
changed_policy_correct = 0
changed_policy_total = 0
unchanged_correct = 0
unchanged_total = 0

canary_flips = 0

for r in results:
    t = r['task']
    ans1 = r['attempts'][0]['answer']
    
    is_correct1 = (ans1 == t['correct_action'])
    is_stale1 = (ans1 == t.get('stale_action', ''))
    
    is_pass4 = all(a['answer'] == t['correct_action'] for a in r['attempts'])
    
    if is_correct1: correct += 1
    for a in r['attempts']:
        if a['answer'] == t.get('stale_action'):
            stale_action_count += 1
    if is_pass4: pass4_count += 1
    
    if t.get('is_canary'):
        if not is_correct1:
            canary_flips += 1
        continue
        
    p_type = manifest['change_points'].get(t['policy_id'])
    if p_type is None:
        unchanged_total += 1
        if is_correct1: unchanged_correct += 1
    else:
        changed_policy_total += 1
        if is_correct1: changed_policy_correct += 1

out_path = f"runs/{condition}_s{seed}.json"

slices = {}
for r in results:
    if r['task'].get('is_canary'): continue
    pos = r['task']['position_slice']
    ans1 = r['attempts'][0]['answer']
    is_correct1 = (ans1 == r['task']['correct_action'])
    if pos not in slices:
        slices[pos] = {'correct': 0, 'total': 0}
    slices[pos]['total'] += 1
    if is_correct1:
        slices[pos]['correct'] += 1

out_data = {
    "condition": condition,
    "seed": seed,
    "pass1": correct / len(tasks),
    "pass4": pass4_count / len(tasks),
    "stale_action_rate": stale_action_count / (len(tasks) * K_ATTEMPTS),
    "changed_policy_pass1": changed_policy_correct / changed_policy_total if changed_policy_total else 0,
    "unchanged_pass1": unchanged_correct / unchanged_total if unchanged_total else 0,
    "tokens_per_task": (total_usage['prompt_tokens'] + total_usage['completion_tokens']) / len(tasks),
    "canary_flips": canary_flips,
    "usage": total_usage
}

for pos, data in slices.items():
    out_data[f"slice_{pos}"] = data['correct'] / data['total'] if data['total'] else 0

with open(out_path, 'w') as f:
    json.dump(out_data, f, indent=2)

print(f"Finished {condition} seed {seed}")
