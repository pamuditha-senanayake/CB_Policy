#!/usr/bin/env python3
"""Report the four store invariants across every runs/store_data*.db."""
import glob
import json
import os
import sqlite3
import sys

END = 999999999


def check(db, manifest_changes):
    con = sqlite3.connect(db)
    cur = con.cursor()
    cur.execute("SELECT id,policy_id,version,valid_from,valid_to,tx_from,tx_to "
                "FROM policies ORDER BY policy_id, tx_from, id")
    rows = cur.fetchall()
    con.close()
    from collections import defaultdict
    by = defaultdict(list)
    for r in rows:
        by[r[1]].append(r)
    inverted, vf_gt_tx, overlaps, multiver = [], [], [], []
    for p, vs in by.items():
        if not manifest_changes.get(p):
            d = {v[2] for v in vs}
            if len(d) != 1:
                multiver.append((p, sorted(d)))
        for v in vs:
            if v[4] < v[3]:
                inverted.append((p, v[2], v[3], v[4]))
            if v[3] > v[5]:
                vf_gt_tx.append((p, v[2], v[3], v[5]))
        for i in range(len(vs)):
            for j in range(i + 1, len(vs)):
                a, b = vs[i], vs[j]
                if a[2] == b[2] and a[3] == b[3]:
                    continue
                if a[3] < b[4] and b[3] < a[4] and a[5] < (b[6] or END) and b[5] < (a[6] or END):
                    overlaps.append((p, a[2], (a[3], a[4]), b[2], (b[3], b[4])))
    return {"inverted_valid_interval": inverted, "valid_from_gt_tx_from": vf_gt_tx,
            "bitemporal_overlap": overlaps, "unchanged_multi_version": multiver}


def main():
    changes = json.load(open("data/manifest.json")).get("change_points", {})
    total = 0
    out = {}
    for db in sorted(glob.glob("runs/store_data*.db")):
        if not db.endswith(".db"):
            continue
        r = check(db, changes)
        n = sum(len(v) for v in r.values())
        total += n
        out[db] = r
        flag = "OK" if n == 0 else f"{n} VIOLATIONS"
        print(f"{db:26} {flag}")
        for k, v in r.items():
            if v:
                print(f"    {k}: {v}")
    print(f"\ntotal violations: {total}")
    if len(sys.argv) > 1:
        json.dump(out, open(sys.argv[1], "w"), indent=2)
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
