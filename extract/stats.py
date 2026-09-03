import json, os, glob, numpy as np, re
from scipy.stats import binomtest

def normalize_action(s):
    if not s: return ""
    import re
    s = str(s).strip().lower()
    s = re.sub(r'[\'"`\\[\\]:\\.]', '', s)
    return s.strip()

def check_answer(response, expected):
    if not response: return False
    response = response.lower()
    expected = expected.lower()
    return expected in response

with open('data/tasks/tasks.json', 'r') as f: tasks = json.load(f)
tasks_dict = {t['task_id']: t for t in tasks}
with open('data/manifest.json', 'r') as f: manifest = json.load(f)

models = ['deepseek-v4-flash', 'claude-sonnet-5', 'gpt-5.6-luna']
seeds = [11, 13, 17]
conditions = ['floor_static_v0', 'bitemporal_drift', 'oracle_expiry', 'latest_timestamp', 'plain_rag', 'full_history_brute']

def get_stats(model, condition, seed):
    raw_dir = f"runs/raw/{model}_{condition}_rs{seed}"
    if not os.path.exists(raw_dir): return None
    task_attempts = {}
    for file_path in glob.glob(f"{raw_dir}/*.json"):
        with open(file_path, 'r') as f: data = json.load(f)
        if data.get('model') != model: continue
        filename = os.path.basename(file_path).replace('.json', '')
        try:
            tid = int(filename.rsplit('_', 1)[0])
            attempt_idx = int(filename.rsplit('_', 1)[1])
        except: continue
        if tid not in task_attempts: task_attempts[tid] = []
        task_attempts[tid].append((attempt_idx, data))
        
    results = {}
    for tid, t in tasks_dict.items():
        if tid not in task_attempts: continue
        attempts = [a[1] for a in sorted(task_attempts[tid], key=lambda x: x[0])]
        ans1 = attempts[0]['response']
        correct = t['correct_action']
        is_stale = False
        t_stale = t.get('stale_action', '')
        if t.get('stale_action') and normalize_action(t_stale) != normalize_action(correct): is_stale = check_answer(ans1, t_stale)
        p = t['policy_id']
        p_type = manifest['change_points'].get(p)
        results[tid] = {
            'is_correct': check_answer(ans1, correct),
            'is_stale': is_stale,
            'has_stale': t.get('stale_action') and normalize_action(t_stale) != normalize_action(correct),
            'is_changed': p_type is not None,
            'slice': t['position_slice'] + "_changed" if p_type is not None else "unchanged",
            'doc_slice': t.get('doc_status_slice') if t.get('position_slice') != 'pre-change' and p_type is not None else None
        }
    return results

def bootstrap_ci(values, n=10000):
    if not values: return 0, 0, 0
    v = np.array(values)
    means = np.mean(np.random.choice(v, (n, len(v))), axis=1)
    return np.mean(v), np.percentile(means, 2.5), np.percentile(means, 97.5)

def format_cell(seed_vals, pooled_vals):
    if not pooled_vals: return "N/A (n=0)"
    if not seed_vals: return "N/A (n=0)"
    m, l, h = bootstrap_ci(pooled_vals)
    s_means = [np.mean(sv) for sv in seed_vals if sv]
    if not s_means: return f"{m:.3f} CI[{l:.3f}-{h:.3f}]"
    s_mean, s_min, s_max = np.mean(s_means), np.min(s_means), np.max(s_means)
    return f"{s_mean:.3f} [{s_min:.3f}-{s_max:.3f}] (CI:{l:.3f}-{h:.3f}, n={len(pooled_vals)})"

output = []
for model in models:
    output.append(f"\n## Model: {model}")
    output.append("\n### Main Table")
    output.append("Condition | Pass1 | Changed Pass1 | Unchanged Pass1 | Stale Action")
    output.append("---|---|---|---|---")
    for cond in conditions:
        all_vals = []
        for s in seeds:
            res = get_stats(model, cond, s)
            if res: all_vals.append(res)
        if not all_vals: continue
        
        pass1_seeds = [[v['is_correct'] for v in r.values()] for r in all_vals]
        chg_seeds = [[v['is_correct'] for v in r.values() if v['is_changed']] for r in all_vals]
        unch_seeds = [[v['is_correct'] for v in r.values() if not v['is_changed']] for r in all_vals]
        stale_seeds = [[v['is_stale'] for v in r.values() if v['has_stale']] for r in all_vals]
        
        pooled = {}
        for r in all_vals:
            for tid, v in r.items(): pooled[f"{id(r)}_{tid}"] = v
        pass1_p = [v['is_correct'] for v in pooled.values()]
        chg_p = [v['is_correct'] for v in pooled.values() if v['is_changed']]
        unch_p = [v['is_correct'] for v in pooled.values() if not v['is_changed']]
        stale_p = [v['is_stale'] for v in pooled.values() if v['has_stale']]
        
        output.append(f"{cond} | {format_cell(pass1_seeds, pass1_p)} | {format_cell(chg_seeds, chg_p)} | {format_cell(unch_seeds, unch_p)} | {format_cell(stale_seeds, stale_p)}")

    output.append("\n### S1 Table (Document Slice)")
    output.append("Condition | Documented | Lagged | Rollback")
    output.append("---|---|---|---")
    for cond in conditions:
        all_vals = []
        for s in seeds:
            res = get_stats(model, cond, s)
            if res: all_vals.append(res)
        if not all_vals: continue
        
        doc_seeds = [[v['is_correct'] for v in r.values() if v['doc_slice'] == 'documented'] for r in all_vals]
        lag_seeds = [[v['is_correct'] for v in r.values() if v['doc_slice'] == 'lagged'] for r in all_vals]
        roll_seeds = [[v['is_correct'] for v in r.values() if v['doc_slice'] == 'rollback'] for r in all_vals]
        
        pooled = {}
        for r in all_vals:
            for tid, v in r.items(): pooled[f"{id(r)}_{tid}"] = v
        doc_p = [v['is_correct'] for v in pooled.values() if v['doc_slice'] == 'documented']
        lag_p = [v['is_correct'] for v in pooled.values() if v['doc_slice'] == 'lagged']
        roll_p = [v['is_correct'] for v in pooled.values() if v['doc_slice'] == 'rollback']
        
        output.append(f"{cond} | {format_cell(doc_seeds, doc_p)} | {format_cell(lag_seeds, lag_p)} | {format_cell(roll_seeds, roll_p)}")

    # McNemar
    output.append("\n### McNemar Exact Test (bitemporal_drift vs latest_timestamp)")
    bd_vals = []
    lt_vals = []
    for s in seeds:
        b = get_stats(model, 'bitemporal_drift', s)
        l = get_stats(model, 'latest_timestamp', s)
        if b and l:
            bd_vals.append(b)
            lt_vals.append(l)
    if bd_vals and lt_vals:
        b_chg, c_chg = 0, 0
        b_lag, c_lag = 0, 0
        for b, l in zip(bd_vals, lt_vals):
            for tid in b:
                if tid in l:
                    if b[tid]['is_changed']:
                        if b[tid]['is_correct'] and not l[tid]['is_correct']: b_chg += 1
                        if not b[tid]['is_correct'] and l[tid]['is_correct']: c_chg += 1
                    if b[tid]['doc_slice'] == 'lagged':
                        if b[tid]['is_correct'] and not l[tid]['is_correct']: b_lag += 1
                        if not b[tid]['is_correct'] and l[tid]['is_correct']: c_lag += 1
        def mcnemar(b, c): return binomtest(min(b,c), b+c, 0.5).pvalue if b+c > 0 else 1.0
        output.append(f"- **Changed Policy Pass1:** b={b_chg}, c={c_chg}, p={mcnemar(b_chg, c_chg):.2e}")
        output.append(f"- **Lagged Cell:** b={b_lag}, c={c_lag}, p={mcnemar(b_lag, c_lag):.2e}")

def print_ablation(cond):
    res = get_stats('deepseek-v4-flash', cond, 11)
    if not res: return "N/A"
    pass1 = [v['is_correct'] for v in res.values()]
    pre_chg = [v['is_correct'] for v in res.values() if v.get('slice') == 'pre-change_changed']
    post = [v['is_correct'] for v in res.values() if v.get('slice') == 'post-detection_changed']
    win_stale = [v['is_correct'] for v in res.values() if v.get('slice') == 'window_detected_doc_stale_changed']
    
    m_pass = np.mean(pass1) if pass1 else 0
    m_pre = np.mean(pre_chg) if pre_chg else 0
    m_post = np.mean(post) if post else 0
    m_win = np.mean(win_stale) if win_stale else 0
    
    return f"Pass1: {m_pass:.3f}, Pre-Chg: {m_pre:.3f}, Post-Det: {m_post:.3f}, Win-Stale: {m_win:.3f}"

out_a = []
out_a.append("\n### Ablation Metrics (DeepSeek rs11)")
for c in ['bitemporal_drift', 'a2', 'a3', 'a4', 'a5_absent', 'a5_neutral']:
    out_a.append(f"{c}: {print_ablation(c)}")

with open('MULTIMODEL_RESULTS_tables.md', 'w') as f:
    f.write("\n".join(output + out_a))

