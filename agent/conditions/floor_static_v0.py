import json

def build_context(task, stores):
    policy_id = task['policy_id']
    with open(f"data/policies/{policy_id}_v0.json", 'r') as f:
        doc = json.load(f)
    return doc['prose']
