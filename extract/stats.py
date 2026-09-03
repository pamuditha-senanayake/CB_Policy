import json
import os
import glob
import numpy as np
from scipy.stats import binomtest
import matplotlib.pyplot as plt

def normalize_action(s):
    if not s: return ""
    import re
    s = str(s).strip()
    s = re.sub(r'[\'"`\[\]:\.]', '', s)
    return s.strip().lower()

with open('data/tasks/tasks.json', 'r') as f:
    tasks = json.load(f)

# Build tasks dict
tasks_dict = {t['task_id']: t for t in tasks}

with open('data/manifest.json', 'r') as f:
    manifest = json.load(f)

conditions = ['floor_static_v0', 'bitemporal_drift', 'oracle_expiry', 'latest_timestamp', 'plain_rag', 'full_history_brute']

def get_stats(condition):
    raw_dir = f"runs/raw/{condition}_rs11"
    if not os.path.exists(raw_dir):
        return None
        
    task_attempts = {}
    for file_path in glob.glob(f"{raw_dir}/*.json"):
        filename = os.path.basename(file_path).replace('.json', '')
        parts = filename.rsplit('_', 1)
        tid = parts[0]
        attempt_idx = parts[1]
        try: tid = int(tid)
        except: pass
        if tid not in task_attempts:
            task_attempts[tid] = []
        with open(file_path, 'r') as f:
            data = json.load(f)
        task_attempts[tid].append((int(attempt_idx), data))
        
    # We want pass1 correctly
    results = {}
    for tid, t in tasks_dict.items():
        if tid not in task_attempts:
            continue
        attempts = [a[1] for a in sorted(task_attempts[tid], key=lambda x: x[0])]
        ans1 = normalize_action(attempts[0]['response'])
        correct = normalize_action(t['correct_action'])
        is_correct = (ans1 == correct)
        
        is_stale = False
        t_stale = normalize_action(t.get('stale_action', ''))
        if t.get('stale_action') and t_stale != correct:
            is_stale = (ans1 == t_stale)
            
        p = t['policy_id']
        p_type = manifest['change_points'].get(p)
        
        results[tid] = {
            'is_correct': is_correct,
            'is_stale': is_stale,
            'has_stale': t.get('stale_action') and t_stale != correct,
            'is_changed': p_type is not None,
            'slice': t['position_slice'] + "_changed" if p_type is not None else "unchanged",
            'doc_slice': t.get('doc_status_slice') if t.get('position_slice') != 'pre-change' and p_type is not None else None
        }
    return results

data_all = {}
for cond in conditions:
    res = get_stats(cond)
    if res:
        data_all[cond] = res

# Calculate tables
def bootstrap_ci(values, n_resamples=10000):
    if len(values) == 0: return 0, 0, 0
    values = np.array(values)
    means = np.mean(np.random.choice(values, (n_resamples, len(values))), axis=1)
    return np.mean(values), np.percentile(means, 2.5), np.percentile(means, 97.5)

def format_cell(values):
    mean, p25, p975 = bootstrap_ci(values)
    return f"{mean:.3f} [{p25:.2f}, {p975:.2f}]"

print("MAIN TABLE")
print("Condition | Pass1 | Changed Pass1 | Unchanged Pass1 | Stale Action")
for cond in conditions:
    if cond not in data_all: continue
    d = data_all[cond]
    pass1 = [v['is_correct'] for v in d.values()]
    chg = [v['is_correct'] for v in d.values() if v['is_changed']]
    unch = [v['is_correct'] for v in d.values() if not v['is_changed']]
    stale = [v['is_stale'] for v in d.values() if v['has_stale']]
    print(f"{cond} | {format_cell(pass1)} | {format_cell(chg)} | {format_cell(unch)} | {format_cell(stale)}")

print("\nS1 TABLE")
print("Condition | Documented | Lagged | Rollback")
for cond in conditions:
    if cond not in data_all: continue
    d = data_all[cond]
    doc = [v['is_correct'] for v in d.values() if v['doc_slice'] == 'documented']
    lag = [v['is_correct'] for v in d.values() if v['doc_slice'] == 'lagged']
    roll = [v['is_correct'] for v in d.values() if v['doc_slice'] == 'rollback']
    print(f"{cond} | {format_cell(doc)} | {format_cell(lag)} | {format_cell(roll)}")
    
# McNemar
def mcnemar_exact(b, c):
    if b + c == 0: return 1.0
    return binomtest(min(b, c), b + c, 0.5).pvalue

print("\nMcNemar Test: bitemporal_drift vs latest_timestamp")
bd = data_all['bitemporal_drift']
lt = data_all['latest_timestamp']

# changed_policy_pass1
b_chg = 0
c_chg = 0
for tid in bd:
    if bd[tid]['is_changed']:
        if bd[tid]['is_correct'] and not lt[tid]['is_correct']: b_chg += 1
        if not bd[tid]['is_correct'] and lt[tid]['is_correct']: c_chg += 1
print(f"Changed Policy Pass1: b={b_chg}, c={c_chg}, p={mcnemar_exact(b_chg, c_chg)}")

# lagged cell
b_lag = 0
c_lag = 0
for tid in bd:
    if bd[tid]['doc_slice'] == 'lagged':
        if bd[tid]['is_correct'] and not lt[tid]['is_correct']: b_lag += 1
        if not bd[tid]['is_correct'] and lt[tid]['is_correct']: c_lag += 1
print(f"Lagged Cell: b={b_lag}, c={c_lag}, p={mcnemar_exact(b_lag, c_lag)}")

