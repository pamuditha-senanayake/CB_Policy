"""
Uses TF-IDF locally for retrieval over all versions mixed, with no invalidation.
No embedding API spend.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def build_context(task, stores):
    ts = task['ts']
    store = stores['bitemporal']
    
    # Get all documents for all policies written before or at ts
    store.cursor.execute('''
        SELECT doc_text FROM policies WHERE tx_from <= ?
    ''', (ts,))
    docs = [row[0] for row in store.cursor.fetchall()]
    
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
        # e.g., empty vocabulary
        return docs[0]
