#!/usr/bin/env python3
"""A1: remove the retrospective scan (`valid_from = detect_ts`).

Two things this deliberately does NOT do any more:

* It no longer writes over `runs/stage2_seed*.json` or `runs/store_data*.db`.
  The previous version ran an ablated pipeline straight into the real Stage 2
  artifacts and then read them back, which is how those artifacts were
  destroyed. Ablated output goes to `runs/a1_stage2_seed{seed}.json` and
  `runs/a1_store_data{seed}.db`.
* It no longer trusts a silent string replace. Each substitution is asserted,
  so a drift in `eval_stage2.py` fails loudly instead of quietly running the
  unablated pipeline and reporting it as the ablation.

Also dumps the mined rows per seed to check the collapse actually reaches the
store: under A1 every mined version must have `valid_from == tx_from`.
"""

import json
import os
import sqlite3
import subprocess
import sys

import yaml

SEEDS = [0, 1, 2, 3, 7, 11]
TMP = "detect/eval_stage2_a1_tmp.py"


def build_ablated_source():
    orig = open("detect/eval_stage2.py").read()
    mod = orig

    # 1. the ablation itself: collapse the retrospective estimate onto detect_ts
    target = ("est_change = retrospective_scan(fitness_buffer[p])\n"
              "        # Enforce valid_from <= valid_to (est_change must be >= doc['valid_from'])\n"
              "        est_change = max(est_change, doc['valid_from'])\n"
              "        # Enforce valid_from <= tx_from (est_change must be <= detect_ts)\n"
              "        est_change = min(est_change, detect_ts)")
    assert target in mod, "A1: retrospective_scan block not found in eval_stage2.py"
    mod = mod.replace(target, "est_change = detect_ts")

    # 2. that guard asserts valid_from != tx_now, which A1 deliberately violates
    guard = 'assert est_change != detect_ts, "valid_from must differ from tx_now"'
    assert guard in mod, "A1: est_change guard not found"
    mod = mod.replace(guard, "pass  # A1 collapses valid_from onto tx_now by design")

    # 3. redirect both artifacts so the real ones are never touched
    assert "runs/store_data{seed}.db" in mod, "A1: store path not found"
    mod = mod.replace("runs/store_data{seed}.db", "runs/a1_store_data{seed}.db")
    # Redirect every reference, not just the out_file assignment: the write
    # guard also names this path up front, before any destructive work.
    assert "runs/stage2_seed{seed}.json" in mod, "A1: stage2 out path not found"
    mod = mod.replace("runs/stage2_seed{seed}.json", "runs/a1_stage2_seed{seed}.json")
    assert mod != orig
    return mod


def store_collapse_check(seed):
    """Under A1 every mined row must have valid_from == tx_from."""
    db = f"runs/a1_store_data{seed}.db"
    if not os.path.exists(db):
        return None
    con = sqlite3.connect(db)
    cur = con.cursor()
    cur.execute("SELECT policy_id, version, valid_from, valid_to, tx_from "
                "FROM policies WHERE source != 'document'")
    rows = cur.fetchall()
    con.close()
    total = len(rows)
    collapsed = sum(1 for r in rows if r[2] == r[4])
    return {"mined_rows": total, "valid_from_eq_tx_from": collapsed,
            "all_collapsed": total > 0 and collapsed == total}


def predoc_correctness(db, manifest_changes, tasks):
    """As-of correctness measured BEFORE the document lands.

    `asof_correctness_retrospective` queries at tx=999999998, by which time
    every document row exists with its authoritative valid_from, so mined rows
    are fully superseded and the metric cannot respond to A1 at all (measured:
    0 of 24 probes differ at tx=END, 15 of 24 differ at tx=t_doc-1). This
    variant queries at `t_doc - 1`, where the retrospective estimate is the only
    thing answering, so it actually measures what A1 ablates.
    """
    import sys as _s
    _s.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../graph"))
    from bitemporal_store import BitemporalStore
    if not os.path.exists(db):
        return None
    store = BitemporalStore(db)
    correct = total = 0
    for t in tasks:
        p, ts = t["policy_id"], t["ts"]
        cp = manifest_changes.get(p)
        if not cp:
            continue
        t_doc = cp.get("t_doc")
        if t_doc is None or not (cp["t_practice"] <= ts < t_doc):
            continue
        gt_v = 0
        if "t_rollback" in cp and ts >= cp["t_rollback"]:
            gt_v = 2
        elif ts >= cp["t_practice"]:
            gt_v = 1
        ans = store.as_of(p, ts, t_doc - 1)
        total += 1
        if (ans or {}).get("version", -1) == gt_v:
            correct += 1
    return {"correct": correct, "total": total,
            "rate": correct / total if total else None}


def main():
    open(TMP, "w").write(build_ablated_source())
    orig_config = open("config/experiment.yaml").read()
    per_seed, collapse, predoc = {}, {}, {}
    try:
        for seed in SEEDS:
            conf = yaml.safe_load(orig_config)
            conf["data_seed"] = seed
            open("config/experiment.yaml", "w").write(yaml.dump(conf))
            subprocess.run(["python3", "data/build_benchmark.py"], stdout=subprocess.DEVNULL)
            r = subprocess.run(["python3", TMP, str(seed)], capture_output=True, text=True)
            if r.returncode:
                print(f"seed {seed} FAILED: {r.stderr.strip().splitlines()[-1][:160]}")
                continue
            per_seed[seed] = json.load(open(f"runs/a1_stage2_seed{seed}.json"))
            collapse[seed] = store_collapse_check(seed)
            man = json.load(open("data/manifest.json")).get("change_points", {})
            tasks = json.load(open("data/tasks/tasks.json"))
            predoc[seed] = {
                "baseline": predoc_correctness(f"runs/store_data{seed}.db", man, tasks),
                "a1": predoc_correctness(f"runs/a1_store_data{seed}.db", man, tasks),
            }
            print(f"seed {seed}: ok  collapse={collapse[seed]['all_collapsed']}  "
                  f"predoc base={predoc[seed]['baseline']} a1={predoc[seed]['a1']}")
    finally:
        open("config/experiment.yaml", "w").write(orig_config)
        subprocess.run(["python3", "data/build_benchmark.py"], stdout=subprocess.DEVNULL)
        if os.path.exists(TMP):
            os.remove(TMP)

    keys = ["valid_time_error_traces", "asof_correctness_retrospective",
            "constraint_correctness", "asof_correctness_online"]
    def _mean(sel):
        vals = [v[sel]["rate"] for v in predoc.values()
                if v.get(sel) and v[sel]["rate"] is not None]
        return sum(vals) / len(vals) if vals else None

    out = {"per_seed": {str(s): {k: v.get(k) for k in keys} for s, v in per_seed.items()},
           "store_collapse_check": {str(s): c for s, c in collapse.items()},
           "asof_correctness_predoc": {"per_seed": {str(s): v for s, v in predoc.items()},
                                       "baseline_mean": _mean("baseline"),
                                       "a1_mean": _mean("a1")},
           "mean": {k: sum(v.get(k, 0) for v in per_seed.values()) / len(per_seed)
                    for k in keys} if per_seed else {}}
    json.dump(out, open("runs/a1_sweep.json", "w"), indent=2)
    print(json.dumps(out["mean"], indent=2))


if __name__ == "__main__":
    main()
