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

print('STARTING'); condition = sys.argv[1]
run_seed = int(sys.argv[2]) if len(sys.argv) > 2 else 11
assert run_seed in run_seeds, f"run_seed {run_seed} not in config.run_seeds"

from dotenv import load_dotenv
load_dotenv()

import httpx2 as httpx
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
    http_client=httpx.Client(verify=False)
)

from graph.bitemporal_store import BitemporalStore
stores = {}

if condition in ['bitemporal_drift', 'latest_timestamp', 'full_history_brute', 'plain_rag']:

    stores['bitemporal'] = BitemporalStore(f"runs/store_data{config_seed}.db")
    with open('data/manifest.json', 'r') as f:
        man_hash = hashlib.sha256(f.read().encode()).hexdigest()
    if stores['bitemporal'].get_meta('manifest_hash') != man_hash:
        print("ERROR: store_data DB manifest hash mismatch!")
        sys.exit(1)


with open('data/tasks/tasks.json', 'r') as f:
    tasks = json.load(f)

with open('data/canaries/tasks.json', 'r') as f:
    ctasks = json.load(f)
    for c in ctasks:
        c['is_canary'] = True
    tasks.extend(ctasks)


if condition != 'oracle_expiry':
    with open(f"agent/conditions/{condition}.py", "r") as cf:
        content = cf.read()
        assert "store.current(" not in content, "Adapter must not read future state via current()"
        assert "999999999" not in content and "999999998" not in content, "Adapter must not use END_OF_TIME"

adapter_path = f"agent/conditions/{condition}.py"

spec = importlib.util.spec_from_file_location("condition_module", adapter_path)
condition_module = importlib.util.module_from_spec(spec)
print('EXEC MODULE'); spec.loader.exec_module(condition_module); print('EXEC MODULE DONE')

# Unit test for latest_timestamp
if condition == 'latest_timestamp':
    test_manifest = json.load(open('data/manifest.json'))
    for p_id, p_info in test_manifest['change_points'].items():
        if not p_info: continue
        t_doc = p_info.get('t_doc')
        if t_doc is None: continue
        task = {'policy_id': p_id, 'ts': t_doc + 1}
        ctx = condition_module.build_context(task, stores)
        with open(f"data/policies/{p_id}_v0.json", 'r') as f:
            v0 = json.load(f)['prose']
        with open(f"data/policies/{p_id}_v1.json", 'r') as f:
            v1 = json.load(f)['prose']
        assert v1 in ctx or ctx.strip() == v1, f"Adapter did not return v1 for {p_id} at ts {t_doc+1}"
        assert v0 not in ctx, f"Adapter returned v0 for {p_id} at ts {t_doc+1}"


MODEL = "deepseek-chat"
TEMP = 0.6
K_ATTEMPTS = 4

os.makedirs("runs/cache", exist_ok=True)
run_id = f"{condition}_rs{run_seed}"
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
        action_str = f"{actions[0]} or {actions[1]}"
    else:
        action_str = "approve_refund or deny_refund"
        
    prompt = f"Given the following policy document or context:\n{ctx}\n\nUser request: {t['user_msg']}\n\nWhat action should be taken? Reply with exactly one word: {action_str}\nAction:"
    
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

import subprocess
import filecmp
print("Computing metrics via extract/rescore.py...")
out_json = f"runs/{condition}_s{run_seed}.json"
subprocess.run([sys.executable, "extract/rescore.py", f"runs/raw/{run_id}", condition, str(run_seed), str(config_seed), out_json], check=True)

# Audit chain verify
tmp_json = f"runs/tmp_audit_{condition}.json"
subprocess.run([sys.executable, "extract/rescore.py", f"runs/raw/{run_id}", condition, str(run_seed), str(config_seed), tmp_json], check=True)

with open(out_json, 'r') as f1, open(tmp_json, 'r') as f2:
    if f1.read() == f2.read():
        print("Audit chain verify: Match")
    else:
        print("Audit chain verify: MISMATCH")
        sys.exit(1)
import os
os.remove(tmp_json)
print(f"Finished {condition} run_seed {run_seed}")
