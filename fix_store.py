import re

with open('graph/bitemporal_store.py', 'r') as f:
    content = f.read()

invariant_method = """
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
"""

if "def verify_invariants" not in content:
    content += "\n" + invariant_method

with open('graph/bitemporal_store.py', 'w') as f:
    f.write(content)

