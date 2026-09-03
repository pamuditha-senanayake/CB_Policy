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
        
    def invalidate(self, policy_id, valid_to, tx_now, target_version=None,
                   incoming_version=None):
        """Close every currently-visible row for `policy_id` at `valid_to`.

        Conflict rule -- **the incoming valid_from wins on valid-time
        placement.** A document states when a policy actually changed; a mined
        version only estimates it. When the two disagree the document is
        authoritative, so:

        * a row that starts before `valid_to` is truncated to end at `valid_to`;
        * a row that starts at or after `valid_to` never had a valid interval
          under the corrected timeline, so it is retracted (its transaction
          interval is closed and no successor row is written) rather than being
          given `valid_to < valid_from`;
        * a row of the SAME version as `incoming_version` is retracted outright,
          because the document restates that version's true start and the mined
          estimate of it carries no independent information.

        Selection is by transaction visibility (`tx_to = END`) rather than
        `valid_to = END`. Selecting only valid_to = END missed rows whose
        valid_to had already been truncated to an *estimated* change time, so a
        later document never corrected them and the predecessor version kept
        claiming validity past the documented change -- the source of both the
        inverted intervals and the v0/v1 valid-time overlap.
        """
        self.cursor.execute('''
            SELECT id, valid_from, version, constraint_text, doc_text, permission, source
            FROM policies 
            WHERE policy_id = ? AND tx_to = 999999999
        ''', (policy_id,))
        rows = self.cursor.fetchall()
        for row in rows:
            old_id, v_from, ver, constr, d, perm, src = row
            if target_version is not None and ver != target_version:
                continue
            self.cursor.execute('''
                UPDATE policies SET tx_to = ? WHERE id = ?
            ''', (tx_now, old_id))
            if valid_to <= v_from:
                # Fully superseded by the incoming version: retract, do not
                # emit an inverted interval.
                continue
            if incoming_version is not None and ver == incoming_version:
                # The incoming row restates the SAME version at an authoritative
                # valid_from. A document supersedes a mined estimate of its own
                # version outright, so retract rather than leaving a truncated
                # remnant that would overlap the corrected predecessor.
                continue
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
                SELECT version, constraint_text, doc_text, permission, valid_from
                FROM policies
                WHERE policy_id = ? AND source = ?
                  AND valid_from <= ? AND valid_to > ?
                  AND tx_from <= ? AND tx_to > ?
                ORDER BY tx_from DESC
                LIMIT 1
                ''', (policy_id, source, valid_time, valid_time, tx_time, tx_time))
            else:
                cursor.execute('''
                SELECT version, constraint_text, doc_text, permission, valid_from
                FROM policies
                WHERE policy_id = ? 
                  AND valid_from <= ? AND valid_to > ?
                  AND tx_from <= ? AND tx_to > ?
                ORDER BY tx_from DESC
                LIMIT 1
                ''', (policy_id, valid_time, valid_time, tx_time, tx_time))
            row = cursor.fetchone()
            if row:
                return {'version': row[0], 'constraint': row[1], 'doc_text': row[2], 'permission': row[3], 'valid_from': row[4]}
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
        """Assert the four store invariants. Raises AssertionError, loudly.

        The overlap check is bi-temporal: two valid intervals for one policy may
        overlap freely as long as they were not visible at the same transaction
        time. Only a simultaneous overlap in valid time AND transaction time is
        a violation.
        """
        END = 999999999
        self.cursor.execute(
            'SELECT id, policy_id, version, valid_from, valid_to, tx_from, tx_to '
            'FROM policies ORDER BY policy_id, tx_from, id')
        rows = self.cursor.fetchall()
        from collections import defaultdict
        policies = defaultdict(list)
        for r in rows:
            policies[r[1]].append(r)

        for p_id, vs in policies.items():
            # 1. a policy with no change has exactly one version
            has_change = bool(manifest_changes.get(p_id))
            if not has_change:
                distinct = {v[2] for v in vs}
                assert len(distinct) == 1, (
                    f"Policy {p_id} has no change but versions {sorted(distinct)}")

            for v in vs:
                _id, _p, ver, valid_from, valid_to, tx_from, tx_to = v
                # 2. valid_to >= valid_from
                assert valid_to >= valid_from, (
                    f"valid_to < valid_from for {p_id} v{ver}: "
                    f"[{valid_from}, {valid_to})")
                # 3. valid_from <= tx_from (nothing is known before it happens)
                assert valid_from <= tx_from, (
                    f"valid_from > tx_from for {p_id} v{ver}: "
                    f"valid_from={valid_from} tx_from={tx_from}")

            # 4. no two rows of one policy overlap in valid AND transaction time
            for i in range(len(vs)):
                for j in range(i + 1, len(vs)):
                    a, b = vs[i], vs[j]
                    if a[2] == b[2] and a[3] == b[3]:
                        continue  # same version, same valid_from: a restatement
                    v_overlap = a[3] < b[4] and b[3] < a[4]
                    t_overlap = a[5] < (b[6] or END) and b[5] < (a[6] or END)
                    assert not (v_overlap and t_overlap), (
                        f"Bi-temporal overlap in {p_id}: "
                        f"v{a[2]} valid[{a[3]},{a[4]}) tx[{a[5]},{a[6]}) and "
                        f"v{b[2]} valid[{b[3]},{b[4]}) tx[{b[5]},{b[6]})")
        return True
