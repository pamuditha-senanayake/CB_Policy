import sqlite3

class BitemporalStore:
    def __init__(self, db_path=':memory:'):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id TEXT,
                valid_from INTEGER,
                valid_to INTEGER,
                tx_from INTEGER,
                tx_to INTEGER,
                version INTEGER,
                constraint_text TEXT,
                doc_text TEXT,
                permission TEXT
            )
        ''')
        self.conn.commit()
    
    def insert(self, policy_id, version, constraint, doc_text, valid_from, tx_now, permission=""):
        self.cursor.execute('''
            INSERT INTO policies 
            (policy_id, valid_from, valid_to, tx_from, tx_to, version, constraint_text, doc_text, permission)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (policy_id, valid_from, 999999999, tx_now, 999999999, version, constraint, doc_text, permission))
        self.conn.commit()
        
    def invalidate(self, policy_id, valid_to, tx_now):
        self.cursor.execute('''
            SELECT id, valid_from, version, constraint_text, doc_text, permission 
            FROM policies 
            WHERE policy_id = ? AND valid_to = 999999999 AND tx_to = 999999999
        ''', (policy_id,))
        row = self.cursor.fetchone()
        if row:
            old_id, v_from, ver, constr, doc, perm = row
            self.cursor.execute('''
                UPDATE policies SET tx_to = ? WHERE id = ?
            ''', (tx_now, old_id))
            self.cursor.execute('''
                INSERT INTO policies 
                (policy_id, valid_from, valid_to, tx_from, tx_to, version, constraint_text, doc_text, permission)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (policy_id, v_from, valid_to, tx_now, 999999999, ver, constr, doc, perm))
            self.conn.commit()

    def as_of(self, policy_id, valid_time, tx_time):
        self.cursor.execute('''
            SELECT version, constraint_text, doc_text, permission
            FROM policies
            WHERE policy_id = ? 
              AND valid_from <= ? AND valid_to > ?
              AND tx_from <= ? AND tx_to > ?
            ORDER BY tx_from DESC
            LIMIT 1
        ''', (policy_id, valid_time, valid_time, tx_time, tx_time))
        row = self.cursor.fetchone()
        if row:
            return {'version': row[0], 'constraint': row[1], 'doc_text': row[2], 'permission': row[3]}
        return None

    def current(self, policy_id):
        return self.as_of(policy_id, 999999998, 999999998)
