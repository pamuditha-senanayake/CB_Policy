import sqlite3
import threading

class BitemporalStore:
    def __init__(self, db_path=':memory:'):
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id TEXT,
                valid_from INTEGER,
                valid_to INTEGER,
                tx_from INTEGER,
                tx_to INTEGER,
                version INTEGER,
                constraint_text TEXT,
                doc_text TEXT,
                permission TEXT,
                source TEXT
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        self.conn.commit()
    
    def insert(self, policy_id, version, constraint, doc_text, valid_from, tx_now, permission="", source="mined"):
        self.cursor.execute('''
            INSERT INTO policies 
            (policy_id, valid_from, valid_to, tx_from, tx_to, version, constraint_text, doc_text, permission, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (policy_id, valid_from, 999999999, tx_now, 999999999, version, constraint, doc_text, permission, source))
        self.conn.commit()
        
    def invalidate(self, policy_id, valid_to, tx_now, target_version=None):
        self.cursor.execute('''
            SELECT id, valid_from, version, constraint_text, doc_text, permission, source
            FROM policies 
            WHERE policy_id = ? AND valid_to = 999999999 AND tx_to = 999999999
        ''', (policy_id,))
        rows = self.cursor.fetchall()
        for row in rows:
            old_id, v_from, ver, constr, d, perm, src = row
            if target_version is not None and ver != target_version:
                continue
            self.cursor.execute('''
                UPDATE policies SET tx_to = ? WHERE id = ?
            ''', (tx_now, old_id))
            self.cursor.execute('''
                INSERT INTO policies 
                (policy_id, valid_from, valid_to, tx_from, tx_to, version, constraint_text, doc_text, permission, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (policy_id, v_from, valid_to, tx_now, 999999999, ver, constr, d, perm, src))
        self.conn.commit()

    def as_of(self, policy_id, valid_time, tx_time, source=None):
        with self.lock:
            cursor = self.conn.cursor()
            if source:
                cursor.execute('''
                SELECT version, constraint_text, doc_text, permission
                FROM policies
                WHERE policy_id = ? AND source = ?
                  AND valid_from <= ? AND valid_to > ?
                  AND tx_from <= ? AND tx_to > ?
                ORDER BY tx_from DESC
                LIMIT 1
                ''', (policy_id, source, valid_time, valid_time, tx_time, tx_time))
            else:
                cursor.execute('''
                SELECT version, constraint_text, doc_text, permission
                FROM policies
                WHERE policy_id = ? 
                  AND valid_from <= ? AND valid_to > ?
                  AND tx_from <= ? AND tx_to > ?
                ORDER BY tx_from DESC
                LIMIT 1
                ''', (policy_id, valid_time, valid_time, tx_time, tx_time))
            row = cursor.fetchone()
            if row:
                return {'version': row[0], 'constraint': row[1], 'doc_text': row[2], 'permission': row[3]}
            return None

    def current(self, policy_id):
        return self.as_of(policy_id, 999999998, 999999998)

    def set_meta(self, key, value):
        self.cursor.execute('INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)', (key, value))
        self.conn.commit()
        
    def get_meta(self, key):
        self.cursor.execute('SELECT value FROM metadata WHERE key = ?', (key,))
        row = self.cursor.fetchone()
        return row[0] if row else None


    def verify_invariants(self, manifest_changes):
        self.cursor.execute('SELECT policy_id, version, valid_from, valid_to, tx_from FROM policies ORDER BY policy_id, version')
        rows = self.cursor.fetchall()
        from collections import defaultdict
        policies = defaultdict(list)
        for r in rows:
            policies[r[0]].append(r)
            
        for p_id, versions in policies.items():
            # A policy with no change has exactly one version
            has_change = p_id in manifest_changes and manifest_changes[p_id] is not None
            if not has_change:
                assert len(versions) == 1, f"Policy {p_id} has no change but {len(versions)} versions"
            
            for i, v in enumerate(versions):
                valid_from = v[2]
                valid_to = v[3]
                tx_from = v[4]
                assert valid_to >= valid_from, f"valid_to < valid_from for {p_id} v{v[1]}"
                assert valid_from <= tx_from, f"valid_from > tx_from for {p_id} v{v[1]}"
                
                if i > 0:
                    prev = versions[i-1]
                    # No overlap
                    assert prev[3] <= valid_from, f"Overlap in {p_id}: v{prev[1]} ends {prev[3]} but v{v[1]} starts {valid_from}"
