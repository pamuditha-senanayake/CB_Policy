def build_context(task, stores):
    policy_id = task['policy_id']
    store = stores['bitemporal']
    ts = task['ts']
    doc = store.as_of(policy_id, ts, ts)
    return doc['doc_text'] if doc else ""
