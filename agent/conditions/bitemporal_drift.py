import json
import os
import sys

# Hack to import data.template
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../data'))
from template import render_constraint

def build_context(task, stores):
    policy_id = task['policy_id']
    store = stores['bitemporal']
    ts = task['ts']
    doc = store.as_of(policy_id, ts, ts)
    if not doc:
        return ""
        
    if doc['doc_text'] == 'practice diverged, document pending':
        with open(f"data/policies/{policy_id}_v0.json", 'r') as f:
            v0 = json.load(f)
        action_t = v0['action_true']
        action_f = v0['action_false']
        prose = render_constraint(doc['constraint'], action_t, action_f)
        return prose + "\n\nSource: practice-mined, document pending"
    
    return doc['doc_text']
