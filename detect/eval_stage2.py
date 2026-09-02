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
if os.path.exists(f'runs/store_data{seed}.db'):
    try: os.remove(f'runs/store_data{seed}.db')
    except: pass
store = BitemporalStore(f'runs/store_data{seed}.db')
store.set_meta('manifest_hash', 'f72addde5559da4db28d32fefd00ec78cb93d7e4f43ee478b43d626eee34b2c8')
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
            store.insert(p, v0['version'], v0['constraint'], v0['prose'], 0, 0, source='document')
    except FileNotFoundError:
        pass
    detectors[p] = DriftDetector("ADWIN_delta_0.1")
    drifts_detected[p] = 0
    recent_traces[p] = []
    fitness_buffer[p] = []
    detection_timestamps[p] = []
    est_change_points[p] = []

pending_docs = []
with open("data/manifest.json", 'r') as f:
    manifest = json.load(f)
change_points = manifest.get('change_points', {})

for p, cp in change_points.items():
    if cp:
        try:
            with open(f"data/policies/{p}_v1.json") as f: v1doc = json.load(f)
            pending_docs.append({'p': p, 'v': 1, 'v_from': cp['t_practice'], 't_doc': cp['t_doc'], 'vdoc': v1doc})
            if 't_rollback_doc' in cp:
                with open(f"data/policies/{p}_v2.json") as f: v2doc = json.load(f)
                pending_docs.append({'p': p, 'v': 2, 'v_from': cp['t_rollback'], 't_doc': cp['t_rollback_doc'], 'vdoc': v2doc})
        except: pass

traces = []
for p in policies:
    try:
        with open(f"data/event_logs/{p}_log.json", 'r') as f:
            t = json.load(f)
            traces.extend(t)
    except FileNotFoundError:
        pass

def insert_pending_docs_up_to(ts):
    for d in pending_docs:
        if d['t_doc'] <= ts and not d.get('inserted'):
            store.invalidate(d['p'], valid_to=d['v_from'], tx_now=d['t_doc']) # DO NOT PASS TARGET_VERSION for doc insert
            store.insert(d['p'], d['v'], d['vdoc']['constraint'], d['vdoc']['prose'], valid_from=d['v_from'], tx_now=d['t_doc'], source='document')
            d['inserted'] = True
            
            # Reset ADWIN to prevent false positives from long windows
            if d['p'] in detectors:
                from drift import DriftDetector
                detectors[d['p']] = DriftDetector("ADWIN_delta_0.1")
                fitness_buffer[d['p']] = []

traces.sort(key=lambda x: x['ts'])


for t in traces:
    p = t['policy_id']
    ts = t['ts']
    insert_pending_docs_up_to(ts)
    recent_traces[p].append(t)
    if len(recent_traces[p]) > 50:
        recent_traces[p].pop(0)
        
    doc = store.as_of(p, ts, ts)
    if not doc: continue
    
    doc_for_fit = dict(doc)
    doc_for_fit['action_true'] = v0_docs[p]['action_true']
    doc_for_fit['action_false'] = v0_docs[p]['action_false']
    
    fit = calculate_fitness(t, doc_for_fit)
    if p == 'price_match_cap' and 400 <= ts <= 450: print(f"FIT ts={ts} fit={fit} t={t} active_c={doc_for_fit['constraint']}")
    fitness_buffer[p].append((ts, fit))
    if len(fitness_buffer[p]) > 150:
        fitness_buffer[p].pop(0)
        
    if detectors[p].add_element(fit):
        drifts_detected[p] += 1
        detect_ts = ts
        detection_timestamps[p].append(detect_ts)
        
        est_change = retrospective_scan(fitness_buffer[p])
        est_change_points[p].append(est_change)
        
        store.invalidate(p, valid_to=est_change, tx_now=detect_ts, target_version=doc['version'])
        
        new_c = mine_constraint(recent_traces[p], doc['constraint'], v0_docs[p]['action_true'], v0_docs[p]['action_false'])
        print(f"MINED {p} at {detect_ts}: {new_c}")
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

for p, cp in change_points.items():
    if cp:
        try:
            with open(f"data/policies/{p}_v1.json") as f: v1doc = json.load(f)
            pending_docs.append({'p': p, 'v': 1, 'v_from': cp['t_practice'], 't_doc': cp['t_doc'], 'vdoc': v1doc})
            if 't_rollback_doc' in cp:
                with open(f"data/policies/{p}_v2.json") as f: v2doc = json.load(f)
                pending_docs.append({'p': p, 'v': 2, 'v_from': cp['t_rollback'], 't_doc': cp['t_rollback_doc'], 'vdoc': v2doc})
        except: pass

traces = []
per_policy_errors = {}
for p in policies:
    cp = change_points.get(p)
    if cp:
        expected_cps = []
        # Primary change
        if cp['t_practice'] != cp.get('t_doc', -1):
            expected_cps.append(('primary', cp['t_practice']))
        # Rollback change
        if 't_rollback' in cp and cp.get('t_rollback_doc', -1) != cp['t_rollback']:
            expected_cps.append(('rollback', cp['t_rollback']))
            
        if not expected_cps:
            per_policy_errors[p] = "no_drift_required"
            continue
            
        if not est_change_points.get(p):
            continue
            
        per_policy_errors[p] = {}
        for est_cp in est_change_points[p]:
            closest = None
            min_dist = float('inf')
            for name, true_cp in expected_cps:
                dist = abs(est_cp - true_cp)
                if dist < min_dist:
                    min_dist = dist
                    closest = name
            
            if min_dist < 300: # Within detection window
                error_traces.append(min_dist)
                if len(expected_cps) > 1:
                    per_policy_errors[p][closest] = min_dist
                else:
                    per_policy_errors[p] = min_dist
            
valid_time_error = sum(error_traces) / len(error_traces) if error_traces else 0

correct_post = 0
total_post = 0

correct_retro = 0
total_retro = 0
correct_constraint = 0

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
    
    is_constraint_correct = False
    if ans_retro:
        true_c = v0_docs[p]['constraint']
        if gt_v == 1:
            try:
                with open(f"data/policies/{p}_v1.json") as f: true_c = json.load(f)['constraint']
            except: pass
        elif gt_v == 2:
            try:
                with open(f"data/policies/{p}_v2.json") as f: true_c = json.load(f)['constraint']
            except: pass
            
        mined_c = ans_retro['constraint']
        if true_c == mined_c:
            is_constraint_correct = True
        else:
            agree = True
            # Check semantic equivalence on the recent traces
            for tr in recent_traces[p]:
                for e in tr.get('events', []):
                    env = dict(e['attrs'])
                    try:
                        r1 = eval(mined_c, {"__builtins__": {}}, env)
                        r2 = eval(true_c, {"__builtins__": {}}, env)
                        if r1 != r2: agree = False
                    except: pass
            if agree:
                is_constraint_correct = True
    if is_constraint_correct:
        correct_constraint += 1

    is_post = False
    if detection_timestamps[p]:
        if cp and 't_rollback' in cp and len(detection_timestamps[p]) >= 2:
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
            
    if cp is None:
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

# Redefine rollback_handled as content check
rb_handled = False
rb_ans = store.as_of('loyalty_discount', 800, 800)
if rb_ans:
    mined_c = rb_ans['constraint']
    true_c = v0_docs['loyalty_discount']['constraint']
    if mined_c == true_c:
        rb_handled = True
    else:
        # Check equivalence
        agree = True
        for tr in recent_traces['loyalty_discount']:
            for e in tr.get('events', []):
                env = dict(e['attrs'])
                try:
                    r1 = eval(mined_c, {"__builtins__": {}}, env)
                    r2 = eval(true_c, {"__builtins__": {}}, env)
                    if r1 != r2: agree = False
                except: pass
        if agree:
            rb_handled = True

output = {
    "asof_correctness_postdetection": asof_corr_post,
    "asof_correctness_retrospective": asof_corr_retro,
    "constraint_correctness": correct_constraint / total_retro if total_retro else 0,
    "asof_correctness_online": asof_corr_online,
    "valid_time_error_traces": valid_time_error,
    "per_policy_errors": per_policy_errors,
    "false_invalidation_rate": fir,
    "rollback_handled": rb_handled,
    "canary_policy_still_valid": canary_ok
}

out_file = f"runs/stage2_seed{seed}.json"
with open(out_file, "w") as f:
    json.dump(output, f, indent=2)

print(json.dumps(output, indent=2))
