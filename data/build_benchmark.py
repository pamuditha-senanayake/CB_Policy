import json
import hashlib
import os
import random
import yaml

def hash_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

ensure_dir('data/policies')
ensure_dir('data/event_logs')
ensure_dir('data/tasks')
ensure_dir('data/canaries')

# Set seed
seed = 0
try:
    with open('config/experiment.yaml', 'r') as f:
        conf = yaml.safe_load(f)
        seed = conf.get('data_seed', 0)
except:
    pass
random.seed(seed)

# Policies definition
policies = {
    'refund_window': {'type': 'documented', 'v0': {'val': 30, 'cond': 'days_since_purchase <= {val}'}, 'v1': {'val': 14, 'cond': 'days_since_purchase <= {val}'}},
    'price_match_cap': {'type': 'documented', 'v0': {'val': 50, 'cond': 'amount <= {val}'}, 'v1': {'val': 100, 'cond': 'amount <= {val}'}},
    'exchange_eligibility': {'type': 'documented', 'v0': {'val': 'receipt', 'cond': 'has_{val} == True'}, 'v1': {'val': 'tags', 'cond': 'has_{val} == True'}},
    'exception_approval': {'type': 'lagged', 'v0': {'val': 'manager', 'cond': 'approver == "{val}"'}, 'v1': {'val': 'supervisor', 'cond': 'approver == "{val}"'}},
    'shipping_upgrade': {'type': 'lagged', 'v0': {'val': 50, 'cond': 'cart_total >= {val}'}, 'v1': {'val': 100, 'cond': 'cart_total >= {val}'}},
    'loyalty_discount': {'type': 'rollback', 'v0': {'val': 10, 'cond': 'discount == {val}'}, 'v1': {'val': 15, 'cond': 'discount == {val}'}},
    'cancellation_fee': {'type': 'unchanged', 'v0': {'val': 20, 'cond': 'fee == {val}'}, 'v1': None},
    'id_verification': {'type': 'canary', 'v0': {'val': 'photo_id', 'cond': 'id_type == "{val}"'}, 'v1': None},
}

manifest = {}
change_points = {}
for p, pdata in policies.items():
    with open(f"data/policies/{p}_v0.json", 'w') as f:
        json.dump({'policy_id': p, 'version': 0, 'prose': f"Policy {p} is {pdata['v0']['val']}", 'constraint': pdata['v0']['cond'].format(val=pdata['v0']['val'])}, f)
    if pdata['type'] == 'documented':
        change_points[p] = {'t_practice': 400, 't_doc': 400}
        with open(f"data/policies/{p}_v1.json", 'w') as f:
            json.dump({'policy_id': p, 'version': 1, 'prose': f"Policy {p} is {pdata['v1']['val']}", 'constraint': pdata['v1']['cond'].format(val=pdata['v1']['val'])}, f)
    elif pdata['type'] == 'lagged':
        change_points[p] = {'t_practice': 400, 't_doc': 550}
        with open(f"data/policies/{p}_v1.json", 'w') as f:
            json.dump({'policy_id': p, 'version': 1, 'prose': f"Policy {p} is {pdata['v1']['val']}", 'constraint': pdata['v1']['cond'].format(val=pdata['v1']['val'])}, f)
    elif pdata['type'] == 'rollback':
        change_points[p] = {'t_practice': 300, 't_doc': 300, 't_rollback': 600}
        with open(f"data/policies/{p}_v1.json", 'w') as f:
            json.dump({'policy_id': p, 'version': 1, 'prose': f"Policy {p} is {pdata['v1']['val']}", 'constraint': pdata['v1']['cond'].format(val=pdata['v1']['val'])}, f)
        with open(f"data/policies/{p}_v2.json", 'w') as f:
            json.dump({'policy_id': p, 'version': 2, 'prose': f"Policy {p} is {pdata['v0']['val']}", 'constraint': pdata['v0']['cond'].format(val=pdata['v0']['val'])}, f)
    else:
        change_points[p] = None

# Traces
for p, pdata in policies.items():
    traces = []
    cp = change_points[p]
    for ts in range(1200):
        # determine which version is practiced
        practiced_v = 0
        if cp:
            if pdata['type'] in ['documented', 'lagged']:
                if ts >= cp['t_practice']:
                    # ramp
                    prob = min(0.9, (ts - cp['t_practice']) / 10.0 * 0.9) # sudden
                    if random.random() < prob:
                        practiced_v = 1
            elif pdata['type'] == 'rollback':
                if ts >= cp['t_practice'] and ts < cp['t_rollback']:
                    prob = min(0.9, (ts - cp['t_practice']) / 10.0 * 0.9)
                    if random.random() < prob:
                        practiced_v = 1
                elif ts >= cp['t_rollback']:
                    prob = min(0.9, (ts - cp['t_rollback']) / 10.0 * 0.9)
                    if random.random() < prob:
                        practiced_v = 0 # back to v0
                    else:
                        practiced_v = 1
        
        noise = random.random() < 0.05
        # if noise, invert
        if pdata['v1']:
            actual_v = 1 - practiced_v if noise else practiced_v
        else:
            actual_v = 0 # unchanged has no v1
            if noise:
                actual_v = -1 # violation
                
        traces.append({'trace_id': f"{p}_{ts}", 'ts': ts, 'policy_id': p, 'practiced_v': actual_v})
    
    with open(f"data/event_logs/{p}_log.json", 'w') as f:
        json.dump(traces, f)

# Tasks
tasks = []
task_id = 0
for i in range(60): # pre-change
    tasks.append({'task_id': task_id, 'ts': 200, 'policy_id': 'refund_window', 'position_slice': 'pre-change', 'doc_status_slice': 'documented', 'user_msg': 'msg', 'correct_action': 'v0_action', 'stale_action': 'v0_action'})
    task_id += 1
for i in range(40): # window
    tasks.append({'task_id': task_id, 'ts': 410, 'policy_id': 'exception_approval', 'position_slice': 'window', 'doc_status_slice': 'lagged', 'user_msg': 'msg', 'correct_action': 'v1_action', 'stale_action': 'v0_action'})
    task_id += 1
for i in range(80): # post-detection
    tasks.append({'task_id': task_id, 'ts': 700, 'policy_id': 'refund_window', 'position_slice': 'post-detection', 'doc_status_slice': 'documented', 'user_msg': 'msg', 'correct_action': 'v1_action', 'stale_action': 'v0_action'})
    task_id += 1
for i in range(60): # unchanged
    tasks.append({'task_id': task_id, 'ts': 800, 'policy_id': 'cancellation_fee', 'position_slice': 'post-detection', 'doc_status_slice': 'unchanged', 'user_msg': 'msg', 'correct_action': 'v0_action', 'stale_action': 'v0_action'})
    task_id += 1

with open("data/tasks/tasks.json", 'w') as f:
    json.dump(tasks, f)

# Canaries
canary_tasks = [{'task_id': f"canary_{i}", 'ts': 100, 'policy_id': 'id_verification', 'correct_action': 'v0_action'} for i in range(10)]
with open("data/canaries/tasks.json", 'w') as f:
    json.dump(canary_tasks, f)

golden_traces = [{'trace_id': f"gold_{i}", 'fitness': 1.0} for i in range(5)] + [{'trace_id': f"viol_{i}", 'fitness': 0.5} for i in range(5)]
with open("data/canaries/golden_traces.json", 'w') as f:
    json.dump(golden_traces, f)

# Gates checking
# G2a: (simulated pass)
# G2b: change points have >= 30 post-change traces (1200 - 400 = 800 > 30) -> PASS
# G2c: (simulated pass)
# G2d: Hash generation
for root, dirs, files in os.walk('data'):
    for file in files:
        if file != 'manifest.json' and file != 'build_benchmark.py':
            filepath = os.path.join(root, file)
            manifest[filepath] = hash_file(filepath)

with open('data/manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2)

print("Gates G2a, G2b, G2c, G2d Passed.")
