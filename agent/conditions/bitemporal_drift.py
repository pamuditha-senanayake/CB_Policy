def build_context(task, stores):
    policy_id = task['policy_id']
    store = stores['bitemporal']
    
    # "bitemporal_drift uses store.current(policy_id) from the corrected Step 5B store."
    doc = store.current(policy_id)
    return doc['doc_text'] if doc else ""
