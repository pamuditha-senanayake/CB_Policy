import json
import os
import sys
import subprocess
import shutil
import yaml

sys.path.append(os.path.dirname(__file__))

from conformance import calculate_fitness
from drift import DriftDetector

policies = [
    'refund_window', 'price_match_cap', 'exchange_eligibility',
    'exception_approval', 'shipping_upgrade', 'loyalty_discount',
    'cancellation_fee', 'id_verification'
]

def run_evaluation(method, scratch_dir, **kwargs):
    recalls = 0
    delays = []
    fps = 0
    expected_changes = 0
    
    with open(f"{scratch_dir}/manifest.json", 'r') as f:
        manifest = json.load(f)
    change_points = manifest.get('change_points', {})

    for p in policies:
        with open(f"{scratch_dir}/event_logs/{p}_log.json", 'r') as f:
            traces = json.load(f)
            
        with open(f"{scratch_dir}/policies/{p}_v0.json", 'r') as f:
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
manifest_hashes = set()

# save config
with open('config/experiment.yaml', 'r') as f:
    orig_config = f.read()

SEEDS = [0, 1, 2, 3, 7, 11]
for seed in SEEDS:
    # Update config
    conf = yaml.safe_load(orig_config)
    conf['data_seed'] = seed
    with open('config/experiment.yaml', 'w') as f:
        yaml.dump(conf, f)
        
    # Generate data
    subprocess.run(["python3", "data/build_benchmark.py"], stdout=subprocess.DEVNULL)
    
    # Copy to scratch
    scratch_dir = f"scratch/data_seed_{seed}"
    if os.path.exists(scratch_dir):
        shutil.rmtree(scratch_dir)
    shutil.copytree("data", scratch_dir)
    
    # Record manifest hash
    import hashlib
    with open(f"{scratch_dir}/manifest.json", 'rb') as f:
        mhash = hashlib.sha256(f.read()).hexdigest()
    manifest_hashes.add(mhash)

    for delta in [0.002, 0.01, 0.05, 0.1, 0.15, 0.2, 0.3]:
        res = run_evaluation('ADWIN', scratch_dir, delta=delta)
        results.append({"method": f"ADWIN_delta_{delta}", "seed": seed, **res})
    
    res_ph = run_evaluation('PageHinkley', scratch_dir)
    results.append({"method": "PageHinkley", "seed": seed, **res_ph})
    
    try:
        res_ks = run_evaluation('KSWIN', scratch_dir)
        results.append({"method": "KSWIN", "seed": seed, **res_ks})
    except Exception:
        pass

# Assert manifest hash differs between seeds
assert len(manifest_hashes) == len(SEEDS), \
    f"Expected {len(SEEDS)} distinct manifest hashes, got {len(manifest_hashes)}"

# Restore original config and rebuild data (seed 0)
with open('config/experiment.yaml', 'w') as f:
    f.write(orig_config)
subprocess.run(["python3", "data/build_benchmark.py"], stdout=subprocess.DEVNULL)

# Average across seeds
agg = {}
for r in results:
    m = r['method']
    if m not in agg: agg[m] = {'recall': [], 'fpr': [], 'mean_delay': []}
    agg[m]['recall'].append(r['recall'])
    agg[m]['fpr'].append(r['fpr'])
    agg[m]['mean_delay'].append(r['mean_delay'])

def _mmm(xs):
    return {'mean': sum(xs) / len(xs), 'min': min(xs), 'max': max(xs)}

final = {}
for m, v in agg.items():
    # Recall must be reported alongside FPR: a detector that never fires
    # scores a perfect FPR, so FPR/delay alone cannot rank detectors.
    final[m] = {
        'recall': sum(v['recall']) / len(v['recall']),
        'fpr': sum(v['fpr']) / len(v['fpr']),
        'mean_delay': sum(v['mean_delay']) / len(v['mean_delay']),
        'n_seeds': len(v['fpr']),
        'recall_spread': _mmm(v['recall']),
        'fpr_spread': _mmm(v['fpr']),
        'mean_delay_spread': _mmm(v['mean_delay']),
    }
print(json.dumps(final, indent=2))
with open('runs/a6_sweep.json', 'w') as f:
    json.dump(final, f, indent=2)
