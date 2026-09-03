#!/usr/bin/env python3
"""STEP 8 verification: every run record must reproduce from its own raw logs.

Also reports empty_n / unparseable_n per run and fails any run above 2%
unparseable, and checks the bitemporal store invariants.
"""
import glob
import json
import os
import subprocess
import sqlite3
import sys
import tempfile

FAIL_UNPARSE = 0.02


def reproduce(record_path):
    d = json.load(open(record_path))
    cond, seed = d["condition"], d["run_seed"]
    model, provider = d.get("model"), d.get("provider")
    raw = f"runs/raw/{model}_{cond}_rs{seed}"
    if not os.path.isdir(raw):
        return None, f"raw dir missing: {raw}"
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        tmp = tf.name
    os.remove(tmp)  # rescore.py json.loads the path if it exists; an empty file breaks it
    try:
        r = subprocess.run([sys.executable, "extract/rescore.py", raw, cond, str(seed),
                            "0", tmp, provider, model, d.get("config_hash", "")],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return None, f"rescore failed: {r.stderr.strip().splitlines()[-1][:90]}"
        new = json.load(open(tmp))
    finally:
        os.path.exists(tmp) and os.remove(tmp)
    diffs = [k for k, v in d.items()
             if isinstance(v, (int, float)) and isinstance(new.get(k), (int, float))
             and abs(v - new[k]) > 1e-9]
    return (new, diffs)


def raw_stats(model, cond, seed):
    fs = glob.glob(f"runs/raw/{model}_{cond}_rs{seed}/*.json")
    empty = unp = 0
    for f in fs:
        r = json.load(open(f))
        if not r.get("response", "").strip():
            empty += 1
        if r.get("unparseable"):
            unp += 1
    return len(fs), empty, unp


def store_invariants(db):
    """Bi-temporal invariants.

    Valid-time intervals for one policy MAY overlap across different
    transaction times -- that is the point of a bi-temporal store. A real
    conflict needs an overlap in BOTH valid time and transaction time.
    """
    END = 999999999
    con = sqlite3.connect(db)
    cur = con.cursor()
    problems = []
    cur.execute("SELECT COUNT(*) FROM policies WHERE valid_to < valid_from")
    n = cur.fetchone()[0]
    if n:
        problems.append(f"{n} rows with valid_to < valid_from")
    cur.execute(f"SELECT COUNT(*) FROM policies WHERE valid_from > tx_from AND tx_from < {END}")
    n = cur.fetchone()[0]
    if n:
        problems.append(f"{n} rows with valid_from > tx_from")
    cur.execute(f"""SELECT COUNT(*) FROM policies a JOIN policies b
        ON a.policy_id=b.policy_id AND a.source=b.source AND a.id<b.id
        WHERE a.valid_from < b.valid_to AND b.valid_from < a.valid_to
          AND a.tx_from < IFNULL(b.tx_to,{END}) AND b.tx_from < IFNULL(a.tx_to,{END})""")
    n = cur.fetchone()[0]
    if n:
        problems.append(f"{n} bi-temporal overlaps (valid AND tx)")
    con.close()
    return problems


def main():
    records = sorted(glob.glob("runs/*_rs*.json"))
    records = [r for r in records if "SMOKE" not in r]
    ok = bad = 0
    print(f"{'run':52} {'repro':7} {'empty':>6} {'unpars':>7} {'rate':>7} verdict")
    print("-" * 96)
    failed = []
    for rp in records:
        d = json.load(open(rp))
        model = d.get("model"); cond = d["condition"]; seed = d["run_seed"]
        new, diffs = reproduce(rp)
        n, empty, unp = raw_stats(model, cond, seed)
        rate = d.get("unparseable_rate", 0)
        if new is None:
            status, verdict = "ERR", diffs
            failed.append((rp, diffs)); bad += 1
        elif diffs:
            status, verdict = "NO", f"MISMATCH {diffs[:3]}"
            failed.append((rp, verdict)); bad += 1
        elif rate > FAIL_UNPARSE:
            status, verdict = "yes", f"FAILED unparseable {rate:.3f} > {FAIL_UNPARSE}"
            failed.append((rp, verdict)); bad += 1
        else:
            status, verdict = "yes", "PASS"; ok += 1
        name = os.path.basename(rp).replace(".json", "")
        print(f"{name:52} {status:7} {empty:6} {unp:7} {rate:7.4f} {verdict}")

    print(f"\n{ok} records verified, {bad} failed")
    for rp, why in failed:
        print(f"  FAILED {os.path.basename(rp)}: {why}")

    print("\nStore invariants:")
    for db in sorted(glob.glob("runs/store_data*.db")):
        if db.endswith(".bak"):
            continue
        probs = store_invariants(db)
        print(f"  {db}: {'OK' if not probs else '; '.join(probs)}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
