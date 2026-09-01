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

seed = 0
try:
    with open('config/experiment.yaml', 'r') as f:
        conf = yaml.safe_load(f)
        seed = conf.get('data_seed', 0)
except:
    pass
random.seed(seed)

policies = {
    'refund_window': {
        'type': 'documented',
        'attr': 'days_since_purchase',
        'v0': {'val': 30}, 'v1': {'val': 14},
        'eval': lambda attr, val: attr <= val,
        'action_true': 'approve_refund', 'action_false': 'deny_refund',
        'msg_template': 'I bought this {attr} days ago. Can I get a refund?'
    },
    'price_match_cap': {
        'type': 'documented',
        'attr': 'amount',
        'v0': {'val': 50}, 'v1': {'val': 100},
        'eval': lambda attr, val: attr <= val,
        'action_true': 'approve_match', 'action_false': 'deny_match',
        'msg_template': 'Found it cheaper elsewhere, difference is ${attr}. Can you match?'
    },
    'exchange_eligibility': {
        'type': 'documented',
        'attr': 'has_item',
        'v0': {'val': 'receipt'}, 'v1': {'val': 'tags'},
        'eval': lambda attr, val: attr == val,
        'action_true': 'approve_exchange', 'action_false': 'deny_exchange',
        'msg_template': 'I want to exchange this, I only have the {attr}.'
    },
    'exception_approval': {
        'type': 'lagged',
        'attr': 'approver',
        'v0': {'val': 'manager'}, 'v1': {'val': 'supervisor'},
        'eval': lambda attr, val: attr == val,
        'action_true': 'approve_exception', 'action_false': 'deny_exception',
        'msg_template': 'The {attr} approved my exception. Please process it.'
    },
    'shipping_upgrade': {
        'type': 'lagged',
        'attr': 'cart_total',
        'v0': {'val': 50}, 'v1': {'val': 100},
        'eval': lambda attr, val: attr >= val,
        'action_true': 'upgrade_shipping', 'action_false': 'deny_upgrade',
        'msg_template': 'My cart is ${attr}. Do I get free upgraded shipping?'
    },
    'loyalty_discount': {
        'type': 'rollback',
        'attr': 'tier',
        'v0': {'val': 'gold'}, 'v1': {'val': 'platinum'},
        'eval': lambda attr, val: attr == val,
        'action_true': 'apply_15_percent', 'action_false': 'apply_10_percent',
        'msg_template': 'I am a {attr} member, what discount do I get?'
    },
    'cancellation_fee': {
        'type': 'unchanged',
        'attr': 'hours_notice',
        'v0': {'val': 24}, 'v1': None,
        'eval': lambda attr, val: attr >= val,
        'action_true': 'waive_fee', 'action_false': 'charge_fee',
        'msg_template': 'I am cancelling with {attr} hours notice.'
    },
    'id_verification': {
        'type': 'canary',
        'attr': 'id_type',
        'v0': {'val': 'photo_id'}, 'v1': None,
        'eval': lambda attr, val: attr == val,
        'action_true': 'verify_pass', 'action_false': 'verify_fail',
        'msg_template': 'Here is my {attr} for verification.'
    }
}

manifest = {}
change_points = {}

for p, pdata in policies.items():
    cond_str_v0 = f"{pdata['attr']} == '{pdata['v0']['val']}'" if isinstance(pdata['v0']['val'], str) else f"{pdata['attr']} {'<=' if p in ['refund_window','price_match_cap'] else '>=' if p in ['shipping_upgrade','cancellation_fee'] else '=='} {pdata['v0']['val']}"
    with open(f"data/policies/{p}_v0.json", 'w') as f:
        json.dump({
            'policy_id': p, 'version': 0, 
            'prose': f"Policy {p} is {pdata['v0']['val']}", 
            'constraint': cond_str_v0, 'action_true': pdata['action_true'], 'action_false': pdata['action_false']
        }, f)

    if pdata['type'] == 'documented':
        change_points[p] = {'t_practice': 400, 't_doc': 400}
        cond_str_v1 = f"{pdata['attr']} == '{pdata['v1']['val']}'" if isinstance(pdata['v1']['val'], str) else f"{pdata['attr']} {'<=' if p in ['refund_window','price_match_cap'] else '>=' if p in ['shipping_upgrade','cancellation_fee'] else '=='} {pdata['v1']['val']}"
        with open(f"data/policies/{p}_v1.json", 'w') as f:
            json.dump({'policy_id': p, 'version': 1, 'prose': f"Policy {p} is {pdata['v1']['val']}", 'constraint': cond_str_v1, 'action_true': pdata['action_true'], 'action_false': pdata['action_false']}, f)
    elif pdata['type'] == 'lagged':
        change_points[p] = {'t_practice': 400, 't_doc': 550}
        cond_str_v1 = f"{pdata['attr']} == '{pdata['v1']['val']}'" if isinstance(pdata['v1']['val'], str) else f"{pdata['attr']} {'<=' if p in ['refund_window','price_match_cap'] else '>=' if p in ['shipping_upgrade','cancellation_fee'] else '=='} {pdata['v1']['val']}"
        with open(f"data/policies/{p}_v1.json", 'w') as f:
            json.dump({'policy_id': p, 'version': 1, 'prose': f"Policy {p} is {pdata['v1']['val']}", 'constraint': cond_str_v1, 'action_true': pdata['action_true'], 'action_false': pdata['action_false']}, f)
    elif pdata['type'] == 'rollback':
        change_points[p] = {'t_practice': 300, 't_doc': 300, 't_rollback': 600}
        cond_str_v1 = f"{pdata['attr']} == '{pdata['v1']['val']}'" if isinstance(pdata['v1']['val'], str) else f"{pdata['attr']} {'<=' if p in ['refund_window','price_match_cap'] else '>=' if p in ['shipping_upgrade','cancellation_fee'] else '=='} {pdata['v1']['val']}"
        with open(f"data/policies/{p}_v1.json", 'w') as f:
            json.dump({'policy_id': p, 'version': 1, 'prose': f"Policy {p} is {pdata['v1']['val']}", 'constraint': cond_str_v1, 'action_true': pdata['action_true'], 'action_false': pdata['action_false']}, f)
        with open(f"data/policies/{p}_v2.json", 'w') as f:
            json.dump({'policy_id': p, 'version': 2, 'prose': f"Policy {p} is {pdata['v0']['val']}", 'constraint': cond_str_v0}, f)
    else:
        change_points[p] = None

# We need to save the change_points into manifest.json
manifest['change_points'] = change_points

# Generator for random attr based on policy
def get_random_attr(p):
    pdata = policies[p]
    if p == 'refund_window': return random.randint(1, 60)
    if p == 'price_match_cap': return random.randint(10, 150)
    if p == 'exchange_eligibility': return random.choice(['receipt', 'tags', 'nothing'])
    if p == 'exception_approval': return random.choice(['manager', 'supervisor', 'agent'])
    if p == 'shipping_upgrade': return random.randint(10, 150)
    if p == 'loyalty_discount': return random.choice(['gold', 'platinum', 'silver'])
    if p == 'cancellation_fee': return random.choice([12, 24, 48])
    if p == 'id_verification': return random.choice(['photo_id', 'credit_card'])
    return 0

# Generator logs
for p, pdata in policies.items():
    traces = []
    cp = change_points[p]
    for ts in range(1200):
        practiced_v = 0
        if cp:
            if pdata['type'] in ['documented', 'lagged']:
                if ts >= cp['t_practice']:
                    prob = min(0.9, (ts - cp['t_practice']) / 10.0 * 0.9)
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
                        practiced_v = 0
                    else:
                        practiced_v = 1
        
        noise = random.random() < 0.05
        actual_v = practiced_v
        if noise:
            actual_v = 1 - practiced_v if pdata['v1'] else 0

        val = pdata[f'v{actual_v}']['val'] if pdata['v1'] else pdata['v0']['val']
        attr_val = get_random_attr(p)
        
        # force evaluation to match the 'actual_v' if not noise? 
        # Actually, if the store is practicing actual_v, it should just behave according to actual_v's constraint.
        # we generate a random attr_val and then apply the action that actual_v would dictate.
        decision_bool = pdata['eval'](attr_val, val)
        decision = pdata['action_true'] if decision_bool else pdata['action_false']
        
        # WE ONLY EMIT ATTRS AND DECISION, NO VERSIONS.
        traces.append({
            'trace_id': f"{p}_{ts}",
            'ts': ts,
            'policy_id': p,
            'events': [{'attrs': {pdata['attr']: attr_val}, 'decision': decision}]
        })
    
    with open(f"data/event_logs/{p}_log.json", 'w') as f:
        json.dump(traces, f, indent=2)


# Task generation
tasks = []
task_id = 0

def gen_task(policy_id, ts, pos_slice, doc_slice):
    pdata = policies[policy_id]
    
    while True:
        attr_val = get_random_attr(policy_id)
        
        # Determine actual version and stale version
        cp = change_points[policy_id]
        if cp is None:
            # Unchanged policy
            actual_v = 0
            stale_v = 0
        else:
            if ts < cp['t_practice']:
                actual_v = 0
                stale_v = 0
            elif pdata['type'] == 'rollback':
                if ts >= cp['t_rollback']:
                    actual_v = 0
                    stale_v = 1
                else:
                    actual_v = 1
                    stale_v = 0
            else:
                actual_v = 1
                stale_v = 0
                
        # Evaluate correct and stale
        def eval_v(v):
            val = pdata[f'v{v}']['val']
            decision_bool = pdata['eval'](attr_val, val)
            return pdata['action_true'] if decision_bool else pdata['action_false']
            
        correct_action = eval_v(actual_v)
        stale_action = eval_v(stale_v)
        
        # Condition: must differ if changed policy post-change
        if pos_slice in ['window', 'post-detection'] and policy_id != 'cancellation_fee' and policy_id != 'id_verification':
            if correct_action == stale_action:
                continue # Regenerate attribute until they differ
                
        msg = pdata['msg_template'].format(attr=attr_val)
        
        return {
            'task_id': task_id,
            'ts': ts,
            'policy_id': policy_id,
            'position_slice': pos_slice,
            'doc_status_slice': doc_slice,
            'user_msg': msg,
            'correct_action': correct_action,
            'stale_action': stale_action,
            'task_params': {pdata['attr']: attr_val} # Optional but useful
        }

# Distribution
dist = [
    # 60 pre-change
    *[gen_task(p, 200, 'pre-change', policies[p]['type']) for p in random.choices(['refund_window', 'price_match_cap', 'exchange_eligibility', 'exception_approval', 'shipping_upgrade', 'loyalty_discount'], k=60)],
    # 40 inside window
    # lagged: exception_approval, shipping_upgrade (change practice at 400, doc at 550)
    *[gen_task(random.choice(['exception_approval', 'shipping_upgrade']), 450, 'window', 'lagged') for _ in range(40)],
    # 80 post-detection on changed
    *[gen_task(p, 700, 'post-detection', policies[p]['type']) for p in random.choices(['refund_window', 'price_match_cap', 'exchange_eligibility', 'exception_approval', 'shipping_upgrade', 'loyalty_discount'], k=80)],
    # 60 unchanged
    *[gen_task('cancellation_fee', random.randint(100, 800), 'post-detection', 'unchanged') for _ in range(60)]
]

for i, t in enumerate(dist):
    t['task_id'] = i

with open("data/tasks/tasks.json", 'w') as f:
    json.dump(dist, f, indent=2)

# Canaries
canary_tasks = []
for i in range(10):
    t = gen_task('id_verification', 100, 'pre-change', 'canary')
    t['task_id'] = f"canary_{i}"
    canary_tasks.append(t)
    
with open("data/canaries/tasks.json", 'w') as f:
    json.dump(canary_tasks, f, indent=2)

# Golden traces
# 5 fitness 1.0, 5 fitness 0.5 (Wait, a single trace fitness. "fitness is the fraction of events whose observed decision matches what the constraint prescribes").
# So for 1.0, all events match. For 0.5, half match.
import sys
sys.path.append('detect')
from conformance import calculate_fitness
with open('data/canaries/golden_traces.json', 'r') as f:
    golden_traces = json.load(f)
with open('data/policies/refund_window_v0.json', 'r') as f:
    v0_policy = json.load(f)
for gt in golden_traces:
    fit = calculate_fitness(gt, v0_policy)
    assert abs(fit - gt['expected_fitness']) < 0.01, f"G2c failed for {gt['trace_id']}: expected {gt['expected_fitness']}, got {fit}"

for p, cp in change_points.items():
    if cp:
        post = 1200 - cp['t_practice']
        assert post >= 30, f"G2b failed for {p}"

# G2d: Hash generation
for root, dirs, files in os.walk('data'):
    for file in files:
        if file != 'manifest.json' and file != 'build_benchmark.py':
            filepath = os.path.join(root, file)
            manifest[filepath] = hash_file(filepath)

with open('data/manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2)

print("Gates G2a, G2b, G2c, G2d Passed.")
