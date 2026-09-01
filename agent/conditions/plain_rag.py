from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def build_context(task, stores):
    ts = task['ts']
    store = stores['bitemporal']
    
    with store.lock:
        cursor = store.conn.cursor()
        cursor.execute('''
            SELECT doc_text FROM policies WHERE tx_from <= ?
        ''', (ts,))
        docs = [row[0] for row in cursor.fetchall()]
    
    if not docs:
        return ""
        
    vectorizer = TfidfVectorizer()
    try:
        tfidf_matrix = vectorizer.fit_transform(docs)
        query_vec = vectorizer.transform([task['user_msg']])
        sims = cosine_similarity(query_vec, tfidf_matrix).flatten()
        best_idx = sims.argmax()
        return docs[best_idx]
    except ValueError:
        return docs[0]
