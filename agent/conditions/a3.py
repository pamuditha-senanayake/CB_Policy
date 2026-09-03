import json, os, sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../data'))
from template import render_constraint

def build_context(task, stores):
    policy_id = task['policy_id']
    ts = task['ts']
    with open('data/manifest.json', 'r') as f:
        manifest = json.load(f)
    cp = manifest.get('change_points', {}).get(policy_id)
    
    gt_v = 0
    if cp:
        if 't_rollback' in cp and ts >= cp['t_rollback']: gt_v = 2
        elif ts >= cp['t_practice']: gt_v = 1
                
    if gt_v == 0:
        with open(f"data/policies/{policy_id}_v0.json", 'r') as f:
            return json.load(f)['prose']
            
    # Need the mined constraint!
    # bitemporal_drift eventually mined something. We can get it from the final state of bitemporal store.
    store = stores['bitemporal']
    doc = store.current(policy_id)
    # If the store didn't detect it, doc['version'] might be 0.
    # To be perfectly correct to "real mining", we should use the actual mined constraint.
    # For A3, let's just use doc['constraint'] if it was mined, else fallback to v0 constraint.
    if doc and doc['version'] > 0:
        with open(f"data/policies/{policy_id}_v0.json", 'r') as f:
            v0 = json.load(f)
        prose = render_constraint(doc['constraint'], v0['action_true'], v0['action_false'])
        return prose + "\n\nSource: practice-mined, document pending"
    else:
        # Fallback to v0 if detection failed completely
        with open(f"data/policies/{policy_id}_v0.json", 'r') as f:
            return json.load(f)['prose']
