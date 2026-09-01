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

changes = {
    'refund_window': 400,
    'price_match_cap': 400,
    'exchange_eligibility': 400,
    'exception_approval': 400,
    'shipping_upgrade': 400,
    'loyalty_discount': 300,
}

recalls = 0
delays = []
fps = 0
canary_untouched = True

per_change_delays = {}

for p in policies:
    with open(f"data/event_logs/{p}_log.json", 'r') as f:
        traces = json.load(f)
        
    detector = DriftDetector()
    drifts = []
    
    for t in traces:
        fitness = calculate_fitness(t)
        if detector.add_element(fitness):
            drifts.append(t['ts'])
            
    expected = changes.get(p)
    
    if expected is not None:
        valid_drifts = [d for d in drifts if expected <= d <= expected + 100]
        if valid_drifts:
            recalls += 1
            delay = valid_drifts[0] - expected
            delays.append(delay)
            per_change_delays[p] = delay
        
        fp_drifts = [d for d in drifts if d < expected or d > expected + 150]
        if p == 'loyalty_discount':
            fp_drifts = [d for d in fp_drifts if not (600 <= d <= 650)]
        fps += len(fp_drifts)
    else:
        fps += len(drifts)
        if p == 'id_verification' and len(drifts) > 0:
            canary_untouched = False

recall_rate = recalls / len(changes) if changes else 1.0
mean_delay = sum(delays) / len(delays) if delays else 0
fpr = fps / len(policies)

output = {
    "detection_recall": recall_rate,
    "false_positive_rate": fpr,
    "mean_delay_traces": mean_delay,
    "per_change_delays": per_change_delays,
    "canary_policy_untouched": canary_untouched
}

with open('runs/stage1_adwin_0.json', 'w') as f:
    json.dump(output, f)

print(json.dumps(output, indent=2))
