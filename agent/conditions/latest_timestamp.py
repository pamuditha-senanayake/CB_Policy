def build_context(task, stores):
    policy_id = task['policy_id']
    ts = task['ts']
    store = stores['bitemporal']
    store.cursor.execute('''
        SELECT doc_text FROM policies 
        WHERE policy_id = ? AND tx_from <= ? 
        ORDER BY tx_from DESC LIMIT 1
    ''', (policy_id, ts))
    row = store.cursor.fetchone()
    return row[0] if row else ""
