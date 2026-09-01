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

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 0

store = BitemporalStore()
detectors = {}
drifts_detected = {}
recent_traces = {}

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
    
    # Inject action_true and action_false for calculate_fitness
    doc_for_fit = dict(doc)
    doc_for_fit['action_true'] = v0_docs[p]['action_true']
    doc_for_fit['action_false'] = v0_docs[p]['action_false']
    
    fit = calculate_fitness(t, doc_for_fit)
    if detectors[p].add_element(fit):
        drifts_detected[p] += 1
        store.invalidate(p, ts, ts)
        
        # Mine constraint
        new_c = mine_constraint(recent_traces[p], doc['constraint'], v0_docs[p]['action_true'], v0_docs[p]['action_false'])
        new_v = doc['version'] + 1
        store.insert(p, new_v, new_c, 'practice diverged, document pending', ts, ts)

with open("data/manifest.json", 'r') as f:
    manifest = json.load(f)
change_points = manifest.get('change_points', {})

with open("data/tasks/tasks.json", 'r') as f:
    tasks = json.load(f)

correct = 0
false_inv = 0
unchanged_count = 0

for t in tasks:
    p = t['policy_id']
    ts = t['ts']
    ans = store.as_of(p, ts, ts)
    ans_v = ans['version'] if ans else -1
    
    cp = change_points.get(p)
    gt_v = 0
    if cp:
        # Ground truth version at ts
        if 't_rollback' in cp:
            if ts >= cp['t_rollback']:
                gt_v = 2
            elif ts >= cp['t_practice']:
                gt_v = 1
        else:
            if ts >= cp['t_practice']:
                gt_v = 1
                
    if ans_v == gt_v:
        correct += 1
    else:
        print(f"Error: task_id={t['task_id']} p={p} ts={ts} slice={t['position_slice']} ans={ans_v} gt={gt_v}")
        
    if p in ['cancellation_fee', 'gift_card_expiry']:
        unchanged_count += 1
        if ans_v != 0:
            false_inv += 1

asof_corr = correct / len(tasks) if len(tasks) > 0 else 0
fir = false_inv / unchanged_count if unchanged_count > 0 else 0.0

with open("data/canaries/tasks.json", 'r') as f:
    ctasks = json.load(f)

canary_ok = True
for t in ctasks:
    ans = store.as_of(t['policy_id'], t['ts'], t['ts'])
    if not ans or ans['version'] != 0:
        canary_ok = False

output = {
    "asof_correctness": asof_corr,
    "false_invalidation_rate": fir,
    "rollback_handled": (drifts_detected.get('loyalty_discount', 0) >= 2),
    "canary_policy_still_valid": canary_ok
}

out_file = f"runs/stage2_seed{seed}.json"
with open(out_file, "w") as f:
    json.dump(output, f, indent=2)

print(f"Seed {seed}: asof={asof_corr:.4f}, fir={fir:.4f}")
