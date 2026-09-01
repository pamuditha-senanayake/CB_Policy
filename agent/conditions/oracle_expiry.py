import json

def build_context(task, stores):
    policy_id = task['policy_id']
    ts = task['ts']
    with open('data/manifest.json', 'r') as f:
        manifest = json.load(f)
    cp = manifest.get('change_points', {}).get(policy_id)
    
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
                
    with open(f"data/policies/{policy_id}_v{gt_v}.json", 'r') as f:
        doc = json.load(f)
    return doc['prose']
