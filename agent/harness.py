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

with open('config/experiment.yaml', 'rb') as f:
    import hashlib
    config_hash = hashlib.sha256(f.read()).hexdigest()


with open('data/manifest.json', 'r') as f:
    manifest = json.load(f)

assert config_seed == manifest.get('data_seed', -1), f"Seed mismatch: config has {config_seed}, manifest has {manifest.get('data_seed')}"

print('STARTING'); condition = sys.argv[1]
run_seed = int(sys.argv[2]) if len(sys.argv) > 2 else 11
assert run_seed in run_seeds, f"run_seed {run_seed} not in config.run_seeds"

from dotenv import load_dotenv
load_dotenv()

from agent.providers import complete, EmptyResponse, ProviderUnavailable
from agent.validate_models import is_validated
from agent import spend
provider = sys.argv[3] if len(sys.argv) > 3 else "deepseek"
MODEL = sys.argv[4] if len(sys.argv) > 4 else "deepseek-v4-flash"

# Refuse to spend anything on a model that has not passed validation recently.
if os.environ.get("SKIP_VALIDATION_GATE") != "1":
    ok, why = is_validated(provider, MODEL)
    if not ok:
        print(f"REFUSING TO RUN: {why}")
        print("Run: python3 agent/validate_models.py --models "
              f"{provider}/{MODEL}")
        sys.exit(2)
    print(f"Validation gate: {provider}/{MODEL} {why}")

try:
    spend.check_cap(provider)
except spend.BudgetExceeded as e:
    print(f"REFUSING TO RUN: {e}")
    sys.exit(3)


from graph.bitemporal_store import BitemporalStore
stores = {}

# Any adapter that reads the bitemporal store needs it opened, including the
# A2-A5 ablations. Detect from the adapter source rather than a hardcoded list.
try:
    _adapter_src = open(f"agent/conditions/{condition}.py").read()
except FileNotFoundError:
    _adapter_src = ""
_needs_store = "stores['bitemporal']" in _adapter_src or 'stores["bitemporal"]' in _adapter_src

if _needs_store:

    stores['bitemporal'] = BitemporalStore(f"runs/store_data{config_seed}.db")
    with open('data/manifest.json', 'r') as f:
        man_hash = hashlib.sha256(f.read().encode()).hexdigest()
    if stores['bitemporal'].get_meta('manifest_hash') != man_hash:
        print("ERROR: store_data DB manifest hash mismatch!")
        sys.exit(1)
    # The requirement: "The harness must refuse to run if the config hash in the store metadata disagrees with the config on disk."
    db_config_hash = stores['bitemporal'].get_meta('config_hash')
    if db_config_hash and db_config_hash != config_hash:
        print("ERROR: store_data DB config hash mismatch!")
        sys.exit(1)


with open('data/tasks/tasks.json', 'r') as f:
    tasks = json.load(f)

with open('data/canaries/tasks.json', 'r') as f:
    ctasks = json.load(f)
    for c in ctasks:
        c['is_canary'] = True
    tasks.extend(ctasks)


# Conditions that are privileged by design (PREREG): oracle_expiry uses true
# expiry dates; A3 uses oracle change timing with real mining; A4's definition
# is "remove temporal indexing -- always serve the most recently mined rule",
# which requires current(). Every other adapter must not read future state.
ORACLE_PRIVILEGED = {'oracle_expiry', 'a3', 'a4'}

if condition not in ORACLE_PRIVILEGED:
    with open(f"agent/conditions/{condition}.py", "r") as cf:
        content = cf.read()
        assert "store.current(" not in content, "Adapter must not read future state via current()"
        assert "999999999" not in content and "999999998" not in content, "Adapter must not use END_OF_TIME"
elif condition != 'oracle_expiry':
    # Still forbid END_OF_TIME sentinels even in the privileged ablations.
    with open(f"agent/conditions/{condition}.py", "r") as cf:
        content = cf.read()
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



TEMP = 0.6
K_ATTEMPTS = 4
# Answer is a single action word. 32 is ample for every validated model
# (measured mean output: 6.5-7.9 tokens). Never raise this globally: an
# oversized ceiling is what let reasoning models burn 1000 tokens and
# return nothing. providers.complete() escalates per-call when a model
# genuinely stops on `length` with no text.
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "32"))
EXTRACTION_VERSION = "v2"

os.makedirs("runs/cache", exist_ok=True)
# Smoke-test mode: subsample tasks to prove the pipeline cheaply. Output is
# namespaced with a SMOKE_ prefix so it can never overwrite a real run record.
SMOKE_TASKS = int(os.environ.get("SMOKE_TASKS", "0"))
if SMOKE_TASKS:
    step = max(1, len(tasks) // SMOKE_TASKS)
    tasks = tasks[::step][:SMOKE_TASKS]
    print(f"SMOKE TEST MODE: {len(tasks)} tasks (not a valid run record)")

run_id = f"{'SMOKE_' if SMOKE_TASKS else ''}{MODEL}_{condition}_rs{run_seed}"
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
    # Cache key must pin everything that changes the answer, including the
    # token ceiling and the extraction logic -- omitting them is what let
    # empty 12-token responses from an earlier run be silently reused.
    hash_str = (f"{provider}_{MODEL}_{TEMP}_{run_seed}_{attempt_idx}_"
                f"{MAX_TOKENS}_{EXTRACTION_VERSION}_{prompt}")
    h = hashlib.sha256(hash_str.encode()).hexdigest()
    cache_path = f"runs/cache/{h}.json"

    if os.path.exists(cache_path):
        with open(cache_path, 'r') as f:
            cached = json.load(f)
        # Only reuse real answers. A cached failure would make a momentary
        # network blip permanent for every task sharing this prompt.
        if cached.get("answer", "").strip():
            return cached

    try:
        raw_res = complete(provider, MODEL, prompt, TEMP, MAX_TOKENS, seed=run_seed)
        ans = raw_res['text']
        usage = {
            "prompt_tokens": raw_res['prompt_tokens'],
            "completion_tokens": raw_res['completion_tokens']
        }
        res = {"answer": ans, "usage": usage,
               "salvaged_from_reasoning": raw_res.get("salvaged_from_reasoning", False),
               "escalated": raw_res.get("escalated", False)}
    except EmptyResponse as e:
        # Never score an empty answer as a wrong answer.
        print(f"UNPARSEABLE (empty after escalation): {e}")
        res = {"answer": "", "usage": {"prompt_tokens": 0, "completion_tokens": 0},
               "unparseable": True, "reason": str(e)}
    except ProviderUnavailable as e:
        if getattr(e, "fatal", True):
            # Auth, balance or unknown model: the provider is dead, stop now.
            print(f"PROVIDER UNAVAILABLE (fatal), aborting run: {e}")
            with open("failures.txt", "a") as f:
                f.write(f"{provider}/{MODEL} on {condition} seed {run_seed}: {e}\n")
            os._exit(4)
        # Transient (connection reset, 5xx): lose the task, not the sweep.
        print(f"TRANSIENT FAILURE, recording task as unparseable: {e}")
        with open("failures.txt", "a") as f:
            f.write(f"{provider}/{MODEL} on {condition} seed {run_seed} "
                    f"(transient, task dropped): {e}\n")
        res = {"answer": "", "usage": {"prompt_tokens": 0, "completion_tokens": 0},
               "unparseable": True, "reason": f"transient: {e}"}

    total = spend.record(provider, MODEL, res['usage']['prompt_tokens'],
                         res['usage']['completion_tokens'])
    cap = spend.CAPS.get(provider)
    if cap is not None and total >= cap:
        print(f"BUDGET CAP HIT: {provider} ${total:.2f} >= ${cap:.2f}, aborting")
        with open("failures.txt", "a") as f:
            f.write(f"{provider}/{MODEL} on {condition} seed {run_seed}: budget cap ${total:.2f}\n")
        os._exit(3)

    if not res.get("unparseable"):
        with open(cache_path, 'w') as f:
            json.dump(res, f)
    return res

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
            json.dump({"model": MODEL, "provider": provider, "prompt": prompt,
                       "response": ans, "usage": res['usage'],
                       "unparseable": res.get("unparseable", False),
                       "salvaged_from_reasoning": res.get("salvaged_from_reasoning", False)}, f)
            
        attempts.append(res)
    return {"task": t, "attempts": attempts}

print(f"Processing {len(tasks)} tasks...")
MAX_WORKERS = int(os.environ.get('MAX_WORKERS', '12'))
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(process_task, t): t for t in tasks}
    for i, fut in enumerate(as_completed(futures)):
        results.append(fut.result())
        if i % 10 == 0: print(f"Completed {i}/{len(tasks)} tasks")

import subprocess
import filecmp
print("Computing metrics via extract/rescore.py...")
out_json = f"runs/{'SMOKE_' if SMOKE_TASKS else ''}{MODEL}_{condition}_rs{run_seed}.json"
subprocess.run([sys.executable, "extract/rescore.py", f"runs/raw/{run_id}", condition, str(run_seed), str(config_seed), out_json, provider, MODEL, config_hash], check=True)

# Audit chain verify
tmp_json = f"runs/tmp_audit_{MODEL}_{condition}.json"
subprocess.run([sys.executable, "extract/rescore.py", f"runs/raw/{run_id}", condition, str(run_seed), str(config_seed), tmp_json, provider, MODEL, config_hash], check=True)

with open(out_json, 'r') as f1, open(tmp_json, 'r') as f2:
    if f1.read() == f2.read():
        print("Audit chain verify: Match")
    else:
        print("Audit chain verify: MISMATCH")
        sys.exit(1)
import os
os.remove(tmp_json)
print(f"Finished {condition} run_seed {run_seed}")
print("Cumulative spend:")
print(spend.summary())
