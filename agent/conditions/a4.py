import json, os, sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../data'))
from template import render_constraint

def build_context(task, stores):
    policy_id = task['policy_id']
    store = stores['bitemporal']
    # ALWAYS use the CURRENT (latest) state of the store, ignoring temporal indexing (tx_now, valid_from)
    doc = store.current(policy_id)
    if not doc: return ""
    
    if doc['doc_text'] == 'practice diverged, document pending':
        with open(f"data/policies/{policy_id}_v0.json", 'r') as f:
            v0 = json.load(f)
        prose = render_constraint(doc['constraint'], v0['action_true'], v0['action_false'])
        return prose + "\n\nSource: practice-mined, document pending"
    
    return doc['doc_text']
