import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../graph'))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'detect'))

from bitemporal_store import BitemporalStore
from conformance import calculate_fitness
from drift import DriftDetector

def mine_constraint(recent_traces, v0_constraint, action_true, action_false):
    parts = v0_constraint.split(' ')
    attr = parts[0]
    op = parts[1]
    
    vals = []
    for t in recent_traces:
        for e in t.get('events', []):
            vals.append(e['attrs'][attr])
    vals = list(set(vals))
    
    best_fit = -1
    best_c = v0_constraint
    
    for v in vals:
        if isinstance(v, str):
            c = f"{attr} {op} '{v}'"
        else:
            c = f"{attr} {op} {v}"
            
        fit_sum = 0
        total = 0
        for t in recent_traces:
            evs = t.get('events', [])
            for e in evs:
                env = dict(e['attrs'])
                try:
                    res = eval(c, {"__builtins__": {}}, env)
                    if (e['decision'] == action_true) == res:
                        fit_sum += 1
                except:
                    pass
                total += 1
        if total > 0:
            score = fit_sum / total
            if score > best_fit:
                best_fit = score
                best_c = c
    return best_c

def retrospective_scan(buffer):
    # buffer is list of (ts, fitness)
    # split maximizing |mean(left) - mean(right)| with min segment 10
    if len(buffer) < 20:
        return buffer[len(buffer)//2][0]
    
    best_diff = -1
    best_ts = buffer[0][0]
    
    # We want min segment of 10
    for i in range(10, len(buffer) - 9):
        left = buffer[:i]
        right = buffer[i:]
        mean_left = sum(f for t, f in left) / len(left)
        mean_right = sum(f for t, f in right) / len(right)
        diff = abs(mean_left - mean_right)
        if diff > best_diff:
            best_diff = diff
            best_ts = right[0][0] # The split point is the start of the right segment
    return best_ts

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 0

import os
if os.path.exists(f'runs/store_seed{seed}.db'):
    try: os.remove(f'runs/store_seed{seed}.db')
    except: pass
store = BitemporalStore(f'runs/store_seed{seed}.db')
detectors = {}
drifts_detected = {}
recent_traces = {}
fitness_buffer = {} # buffer of (ts, fitness), up to 150
detection_timestamps = {} # p -> list of detect_ts
est_change_points = {} # p -> list of est_change

policies = [
    'refund_window', 'price_match_cap', 'exchange_eligibility',
    'exception_approval', 'shipping_upgrade', 'loyalty_discount',
    'cancellation_fee', 'id_verification', 'gift_card_expiry'
]

v0_docs = {}
for p in policies:
    try:
        with open(f"data/policies/{p}_v0.json", 'r') as f:
            v0 = json.load(f)
            v0_docs[p] = v0
            store.insert(p, v0['version'], v0['constraint'], v0['prose'], 0, 0)
    except FileNotFoundError:
        pass
    detectors[p] = DriftDetector("ADWIN_delta_0.1")
    drifts_detected[p] = 0
    recent_traces[p] = []
    fitness_buffer[p] = []
    detection_timestamps[p] = []
    est_change_points[p] = []

traces = []
for p in policies:
    try:
        with open(f"data/event_logs/{p}_log.json", 'r') as f:
            t = json.load(f)
            traces.extend(t)
    except FileNotFoundError:
        pass

traces.sort(key=lambda x: x['ts'])

for t in traces:
    p = t['policy_id']
    ts = t['ts']
    recent_traces[p].append(t)
    if len(recent_traces[p]) > 50:
        recent_traces[p].pop(0)
        
    doc = store.as_of(p, ts, ts)
    if not doc: continue
    
    doc_for_fit = dict(doc)
    doc_for_fit['action_true'] = v0_docs[p]['action_true']
    doc_for_fit['action_false'] = v0_docs[p]['action_false']
    
    fit = calculate_fitness(t, doc_for_fit)
    fitness_buffer[p].append((ts, fit))
    if len(fitness_buffer[p]) > 150:
        fitness_buffer[p].pop(0)
        
    if detectors[p].add_element(fit):
        drifts_detected[p] += 1
        detect_ts = ts
        detection_timestamps[p].append(detect_ts)
        
        est_change = retrospective_scan(fitness_buffer[p])
        est_change_points[p].append(est_change)
        
        store.invalidate(p, valid_to=est_change, tx_now=detect_ts)
        
        new_c = mine_constraint(recent_traces[p], doc['constraint'], v0_docs[p]['action_true'], v0_docs[p]['action_false'])
        new_v = doc['version'] + 1
        
        assert est_change != detect_ts, "valid_from must differ from tx_now"
        
        store.insert(p, new_v, new_c, 'practice diverged, document pending', valid_from=est_change, tx_now=detect_ts)

with open("data/manifest.json", 'r') as f:
    manifest = json.load(f)
change_points = manifest.get('change_points', {})

with open("data/tasks/tasks.json", 'r') as f:
    tasks = json.load(f)

# Evaluate valid_time_error_traces
error_traces = []
for p in policies:
    cp = change_points.get(p)
    if cp and est_change_points[p]:
        if p == 'loyalty_discount' and len(est_change_points[p]) >= 2:
            err1 = abs(est_change_points[p][0] - cp['t_practice'])
            err2 = abs(est_change_points[p][1] - cp['t_rollback'])
            error_traces.extend([err1, err2])
        else:
            err = abs(est_change_points[p][0] - cp['t_practice'])
            error_traces.append(err)
            
valid_time_error = sum(error_traces) / len(error_traces) if error_traces else 0
per_policy_errors = {}
for p in policies:
    cp = change_points.get(p)
    if cp and est_change_points[p]:
        if p == 'loyalty_discount' and len(est_change_points[p]) >= 2:
            per_policy_errors[p] = [abs(est_change_points[p][0] - cp['t_practice']), abs(est_change_points[p][1] - cp['t_rollback'])]
        else:
            per_policy_errors[p] = abs(est_change_points[p][0] - cp['t_practice'])

correct_post = 0
total_post = 0

correct_retro = 0
total_retro = 0

correct_online = 0
total_online = 0

false_inv = 0
unchanged_count = 0

for t in tasks:
    p = t['policy_id']
    ts = t['ts']
    cp = change_points.get(p)
    
    gt_v = 0
    if cp:
        if 't_rollback' in cp:
            if ts >= cp['t_rollback']:
                gt_v = 2
            elif ts >= cp['t_practice']:
                gt_v = 1
        else:
            if ts >= cp['t_practice']:
                gt_v = 1

    ans_online = store.as_of(p, ts, ts)
    ans_v_online = ans_online['version'] if ans_online else -1
    if ans_v_online == gt_v:
        correct_online += 1
    total_online += 1
    
    ans_retro = store.as_of(p, ts, 999999998)
    ans_v_retro = ans_retro['version'] if ans_retro else -1
    if ans_v_retro == gt_v:
        correct_retro += 1
    total_retro += 1

    is_post = False
    if detection_timestamps[p]:
        if p == 'loyalty_discount' and len(detection_timestamps[p]) >= 2:
            if ts >= detection_timestamps[p][0] and ts < cp['t_rollback']:
                is_post = True
            elif ts >= detection_timestamps[p][1]:
                is_post = True
        else:
            if ts >= detection_timestamps[p][0]:
                is_post = True
                
    if is_post:
        total_post += 1
        if ans_v_retro == gt_v:
            correct_post += 1
            
    if p in ['cancellation_fee', 'gift_card_expiry']:
        unchanged_count += 1
        if ans_v_online != 0:
            false_inv += 1

asof_corr_post = correct_post / total_post if total_post > 0 else 0
asof_corr_retro = correct_retro / total_retro if total_retro > 0 else 0
asof_corr_online = correct_online / total_online if total_online > 0 else 0
fir = false_inv / unchanged_count if unchanged_count > 0 else 0.0

with open("data/canaries/tasks.json", 'r') as f:
    ctasks = json.load(f)

canary_ok = True
for t in ctasks:
    ans = store.as_of(t['policy_id'], t['ts'], t['ts'])
    if not ans or ans['version'] != 0:
        canary_ok = False

output = {
    "asof_correctness_postdetection": asof_corr_post,
    "asof_correctness_retrospective": asof_corr_retro,
    "asof_correctness_online": asof_corr_online,
    "valid_time_error_traces": valid_time_error,
    "per_policy_errors": per_policy_errors,
    "false_invalidation_rate": fir,
    "rollback_handled": (drifts_detected.get('loyalty_discount', 0) >= 2),
    "canary_policy_still_valid": canary_ok
}

out_file = f"runs/stage2_seed{seed}.json"
with open(out_file, "w") as f:
    json.dump(output, f, indent=2)

print(json.dumps(output, indent=2))
