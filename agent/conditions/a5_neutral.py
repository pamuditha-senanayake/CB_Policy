import json, os, sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../data'))
from template import render_constraint

def build_context(task, stores):
    policy_id = task['policy_id']
    store = stores['bitemporal']
    ts = task['ts']
    doc = store.as_of(policy_id, ts, ts)
    if not doc: return ""
    if doc['doc_text'] == 'practice diverged, document pending':
        with open(f"data/policies/{policy_id}_v0.json", 'r') as f:
            v0 = json.load(f)
        prose = render_constraint(doc['constraint'], v0['action_true'], v0['action_false'])
        return prose + "\n\nSource: internal policy record"
    return doc['doc_text']
