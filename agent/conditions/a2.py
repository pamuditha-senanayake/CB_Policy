import json, os, sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../data'))

def build_context(task, stores):
    policy_id = task['policy_id']
    store = stores['bitemporal']
    ts = task['ts']
    doc = store.as_of(policy_id, ts, ts)
    if not doc: return ""
    if doc['doc_text'] == 'practice diverged, document pending':
        return "this policy has changed, current content unknown"
    return doc['doc_text']
