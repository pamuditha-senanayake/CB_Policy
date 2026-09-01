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

def run_evaluation(method, seed=0):
    recalls = 0
    delays = []
    fps = 0
    canary_untouched = True
    per_change_delays = {}

    expected_changes = 0

    for p in policies:
        with open(f"data/event_logs/{p}_log.json", 'r') as f:
            traces = json.load(f)
            
        with open(f"data/policies/{p}_v0.json", 'r') as f:
            v0_policy = json.load(f)
            
        detector = DriftDetector(method=method)
        drifts = []
        
        for t in traces:
            fitness = calculate_fitness(t, v0_policy)
            if detector.add_element(fitness):
                drifts.append(t['ts'])
                
        cp = change_points.get(p)
        if cp is not None:
            # We expect a drift around t_practice
            expected = cp['t_practice']
            expected_changes += 1
            
            # Find first drift after expected
            valid_drifts = [d for d in drifts if expected <= d <= expected + 100]
            if valid_drifts:
                recalls += 1
                delay = valid_drifts[0] - expected
                delays.append(delay)
                per_change_delays[p] = delay
            
            # Any drift outside expected window is a false positive
            # For rollback, there is a second change point!
            t_rollback = cp.get('t_rollback')
            if t_rollback:
                expected_changes += 1
                valid_rollback_drifts = [d for d in drifts if t_rollback <= d <= t_rollback + 100]
                if valid_rollback_drifts:
                    recalls += 1
                    delay = valid_rollback_drifts[0] - t_rollback
                    delays.append(delay)
                    per_change_delays[f"{p}_rollback"] = delay
                
                fp_drifts = [d for d in drifts if (d < expected or expected + 100 < d < t_rollback or d > t_rollback + 100)]
                fps += len(fp_drifts)
            else:
                fp_drifts = [d for d in drifts if d < expected or d > expected + 100]
                fps += len(fp_drifts)
        else:
            fps += len(drifts)
            if p == 'id_verification' and len(drifts) > 0:
                canary_untouched = False

    recall_rate = recalls / expected_changes if expected_changes else 1.0
    mean_delay = sum(delays) / len(delays) if delays else 0
    # True negatives? Denominator is max possible false positive opportunities. Let's stick to fps / len(policies) like before.
    fpr = fps / len(policies)

    output = {
        "detection_recall": recall_rate,
        "false_positive_rate": fpr,
        "mean_delay_traces": mean_delay,
        "per_change_delays": per_change_delays,
        "canary_policy_untouched": canary_untouched
    }
    
    with open(f'runs/stage1_{method.lower()}_seed{seed}.json', 'w') as f:
        json.dump(output, f, indent=2)
        
    return output

if __name__ == "__main__":
    if not os.path.exists('runs'):
        os.makedirs('runs')
        
    import yaml
    seed = 0
    try:
        with open('config/experiment.yaml', 'r') as f:
            conf = yaml.safe_load(f)
            seed = conf.get('data_seed', 0)
    except:
        pass

    adwin_out = run_evaluation('ADWIN', seed)
    adwin_tuned_out = run_evaluation('ADWIN_delta_0.1', seed)
    ph_out = run_evaluation('PageHinkley', seed)

    print("ADWIN Results:")
    print(json.dumps(adwin_out, indent=2))
    print("ADWIN_delta_0.1 Results:")
    print(json.dumps(adwin_tuned_out, indent=2))
    print("PageHinkley Results:")
    print(json.dumps(ph_out, indent=2))
