import json
import os
import sys

sys.path.append(os.path.dirname(__file__))

from conformance import calculate_fitness
from drift import DriftDetector

policies = [
    'refund_window', 'price_match_cap', 'exchange_eligibility',
    'exception_approval', 'shipping_upgrade', 'loyalty_discount',
    'cancellation_fee', 'id_verification'
]

with open('data/manifest.json', 'r') as f:
    manifest = json.load(f)
change_points = manifest.get('change_points', {})

def run_evaluation(method, seed=0, **kwargs):
    recalls = 0
    delays = []
    fps = 0
    expected_changes = 0

    for p in policies:
        with open(f"data/event_logs/{p}_log.json", 'r') as f:
            traces = json.load(f)
            
        with open(f"data/policies/{p}_v0.json", 'r') as f:
            v0_policy = json.load(f)
            
        detector = DriftDetector(method=method, **kwargs)
        drifts = []
        
        for t in traces:
            fitness = calculate_fitness(t, v0_policy)
            if detector.add_element(fitness):
                drifts.append(t['ts'])
                
        cp = change_points.get(p)
        if cp is not None:
            expected = cp['t_practice']
            expected_changes += 1
            valid_drifts = [d for d in drifts if expected <= d <= expected + 100]
            if valid_drifts:
                recalls += 1
                delay = valid_drifts[0] - expected
                delays.append(delay)
            
            t_rollback = cp.get('t_rollback')
            if t_rollback:
                expected_changes += 1
                valid_rollback_drifts = [d for d in drifts if t_rollback <= d <= t_rollback + 100]
                if valid_rollback_drifts:
                    recalls += 1
                    delay = valid_rollback_drifts[0] - t_rollback
                    delays.append(delay)
                fp_drifts = [d for d in drifts if (d < expected or expected + 100 < d < t_rollback or d > t_rollback + 100)]
                fps += len(fp_drifts)
            else:
                fp_drifts = [d for d in drifts if d < expected or d > expected + 100]
                fps += len(fp_drifts)
        else:
            fps += len(drifts)

    recall_rate = recalls / expected_changes if expected_changes else 1.0
    mean_delay = sum(delays) / len(delays) if delays else 0
    fpr = fps / len(policies)

    return {"recall": recall_rate, "fpr": fpr, "mean_delay": mean_delay}

results = []
for seed in [0, 1, 2, 3, 7, 11]:
    # Write config to dummy or set it inside
    for delta in [0.002, 0.01, 0.05, 0.1, 0.15, 0.2, 0.3]:
        res = run_evaluation('ADWIN', seed, delta=delta)
        results.append({"method": f"ADWIN_delta_{delta}", "seed": seed, **res})
    
    res_ph = run_evaluation('PageHinkley', seed)
    results.append({"method": "PageHinkley", "seed": seed, **res_ph})
    
    # KSWIN if supported by river?
    try:
        res_ks = run_evaluation('KSWIN', seed)
        results.append({"method": "KSWIN", "seed": seed, **res_ks})
    except Exception as e:
        pass

# Average across seeds
agg = {}
for r in results:
    m = r['method']
    if m not in agg: agg[m] = {'fpr': [], 'mean_delay': []}
    agg[m]['fpr'].append(r['fpr'])
    agg[m]['mean_delay'].append(r['mean_delay'])

final = {}
for m, v in agg.items():
    final[m] = {
        'fpr': sum(v['fpr']) / len(v['fpr']),
        'mean_delay': sum(v['mean_delay']) / len(v['mean_delay'])
    }
print(json.dumps(final, indent=2))
with open('runs/a6_sweep.json', 'w') as f:
    json.dump(final, f, indent=2)
