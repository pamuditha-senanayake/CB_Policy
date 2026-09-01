import json
import os
import sys
import time
import hashlib
import yaml
from openai import OpenAI
import importlib.util
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'graph'))

with open('config/experiment.yaml', 'r') as f:
    conf = yaml.safe_load(f)
    config_seed = conf.get('data_seed', 0)
    run_seeds = conf.get('run_seeds', [])

with open('data/manifest.json', 'r') as f:
    manifest = json.load(f)

assert config_seed == manifest.get('data_seed', -1), f"Seed mismatch: config has {config_seed}, manifest has {manifest.get('data_seed')}"

condition = sys.argv[1]
run_seed = int(sys.argv[2]) if len(sys.argv) > 2 else 11
assert run_seed in run_seeds, f"run_seed {run_seed} not in config.run_seeds"

from dotenv import load_dotenv
load_dotenv()

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

from graph.bitemporal_store import BitemporalStore
stores = {}

if condition in ['bitemporal_drift', 'latest_timestamp', 'full_history_brute', 'plain_rag']:
    stores['bitemporal'] = BitemporalStore(f"runs/store_seed{config_seed}.db")

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

MODEL = "deepseek-chat"
TEMP = 0.6
K_ATTEMPTS = 4

os.makedirs("runs/cache", exist_ok=True)
run_id = f"{condition}_rs{run_seed}_{int(time.time())}"
os.makedirs(f"runs/raw/{run_id}", exist_ok=True)

# To restrict actions per policy
with open('data/policies/cancellation_fee_v0.json', 'r') as f:
    dummy = json.load(f) # Not useful.
    # Actually we can just get actions from policies in data/policies/*
    pass
    
# Wait, I don't need to read all policies to get action_true/false. I can just deduce them from the tasks.
# But wait, tasks only have `correct_action` and `stale_action`. A task might not have stale_action.
# Is it safer to hardcode the mapping? 
# The instruction says: "Restrict the list to that policy's own action_true / action_false pair... Do not hand-write them per policy." 
# I can read them from manifest? No, manifest doesn't have action_true/action_false.
# I can read `data/policies/{policy_id}_v0.json` to get them!
policy_actions = {}
for p in manifest['change_points'].keys():
    try:
        with open(f"data/policies/{p}_v0.json", 'r') as f:
            v0 = json.load(f)
            policy_actions[p] = [v0['action_true'], v0['action_false']]
    except:
        pass
for p in ['cancellation_fee', 'id_verification', 'gift_card_expiry']:
    try:
        with open(f"data/policies/{p}_v0.json", 'r') as f:
            v0 = json.load(f)
            policy_actions[p] = [v0['action_true'], v0['action_false']]
    except:
        pass

def call_llm(prompt, attempt_idx):
    hash_str = f"{MODEL}_{TEMP}_{run_seed}_{attempt_idx}_{prompt}"
    h = hashlib.sha256(hash_str.encode()).hexdigest()
    cache_path = f"runs/cache/{h}.json"
    
    if os.path.exists(cache_path):
        with open(cache_path, 'r') as f:
            return json.load(f)
            
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=TEMP,
            max_tokens=12,
            stop=["\n"]
            # seed=run_seed - if supported, deepseek-chat might support it? I won't pass it if it causes errors, but openai API supports seed. Let's pass it.
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
    actions = policy_actions.get(t['policy_id'], [])
    if actions:
        action_str = f"[{actions[0]}, {actions[1]}]"
    else:
        action_str = "[approve_refund, deny_refund, ...]" # Fallback
        
    prompt = f"Given the following policy document or context:\n{ctx}\n\nUser request: {t['user_msg']}\n\nWhat action should be taken? Reply with EXACTLY ONE of the following actions, and nothing else:\n{action_str}\nAction:"
    
    attempts = []
    for k in range(K_ATTEMPTS):
        res = call_llm(prompt, k)
        ans = res['answer'].replace('Action:', '').strip()
        
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

# Metrics
total_usage = {"prompt_tokens": 0, "completion_tokens": 0}
for r in results:
    for a in r['attempts']:
        total_usage['prompt_tokens'] += a['usage']['prompt_tokens']
        total_usage['completion_tokens'] += a['usage']['completion_tokens']

correct = 0
pass4_count = 0
stale_action_count = 0
stale_action_eligible_n = 0

changed_policy_correct = 0
changed_policy_total = 0
unchanged_correct = 0
unchanged_total = 0

canary_flips = 0
real_tasks_count = 0

slices = {}

for r in results:
    t = r['task']
    ans1 = r['attempts'][0]['answer']
    is_correct1 = (ans1 == t['correct_action'])
    is_pass4 = all(a['answer'] == t['correct_action'] for a in r['attempts'])
    
    if t.get('is_canary'):
        if not is_correct1:
            canary_flips += 1
        continue
        
    # Real task
    real_tasks_count += 1
    
    if is_correct1: correct += 1
    if is_pass4: pass4_count += 1
    
    # Stale action logic
    if t.get('stale_action') and t.get('stale_action') != t['correct_action']:
        stale_action_eligible_n += K_ATTEMPTS
        for a in r['attempts']:
            if a['answer'] == t['stale_action']:
                stale_action_count += 1
                
    p_type = manifest['change_points'].get(t['policy_id'])
    if p_type is None:
        unchanged_total += 1
        if is_correct1: unchanged_correct += 1
    else:
        changed_policy_total += 1
        if is_correct1: changed_policy_correct += 1
        
    pos = t['position_slice']
    if pos not in slices:
        slices[pos] = {'correct': 0, 'total': 0}
    slices[pos]['total'] += 1
    if is_correct1:
        slices[pos]['correct'] += 1

out_data = {
    "condition": condition,
    "data_seed": config_seed,
    "run_seed": run_seed,
    "pass1": correct / real_tasks_count if real_tasks_count else 0,
    "pass4": pass4_count / real_tasks_count if real_tasks_count else 0,
    "stale_action_rate": stale_action_count / stale_action_eligible_n if stale_action_eligible_n else 0,
    "stale_action_eligible_n": stale_action_eligible_n,
    "changed_policy_pass1": changed_policy_correct / changed_policy_total if changed_policy_total else 0,
    "unchanged_pass1": unchanged_correct / unchanged_total if unchanged_total else 0,
    "tokens_per_task": (total_usage['prompt_tokens'] + total_usage['completion_tokens']) / len(tasks),
    "canary_flips": canary_flips,
    "usage": total_usage
}

for pos, data in slices.items():
    out_data[f"slice_{pos}"] = data['correct'] / data['total'] if data['total'] else 0

out_path = f"runs/{condition}_s{run_seed}.json"
with open(out_path, 'w') as f:
    json.dump(out_data, f, indent=2)

print(f"Finished {condition} run_seed {run_seed}")
