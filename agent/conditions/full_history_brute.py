import json

def build_context(task, stores):
    policy_id = task['policy_id']
    ts = task['ts']
    store = stores['bitemporal']
    
    with store.lock:
        cursor = store.conn.cursor()
        cursor.execute('''
            SELECT version, constraint_text, doc_text, valid_from, valid_to, tx_from
            FROM policies 
            WHERE policy_id = ? AND tx_from <= ? 
            ORDER BY tx_from ASC
        ''', (policy_id, ts))
        rows = cursor.fetchall()
    
    context = "Document History:\n"
    for r in rows:
        context += f"Version {r[0]} (written at {r[5]}, valid {r[3]} to {r[4]}): {r[2]}\n"
        
    try:
        with open(f"data/event_logs/{policy_id}_log.json", 'r') as f:
            traces = json.load(f)
        recent = [t for t in traces if t['ts'] < ts][-50:]
        context += "\nRecent Event Log Summary:\n"
        for r in recent:
            context += f"ts {r['ts']}: attrs={r['events'][0]['attrs']}, decision={r['events'][0]['decision']}\n"
    except:
        pass
        
    return context
