#!/usr/bin/env python3
"""A8: binary search over the attribute range instead of enumerating observed values.

Part one -- mined vs true constraint for every changed policy across all six
data seeds, under both miners.

Part two -- adversarial tasks whose parameter falls inside the mined-to-true
band, and the rate at which the mined constraint answers them wrongly. Under
the enumeration miner that band is non-empty (e.g. shipping_upgrade mines
`>= 94` against a true `>= 100`), and no task in the generated benchmark lands
in it, which is why the measured error rate is currently zero.

Why enumeration lands low: for `attr >= T` every threshold in
(largest denied value, smallest approved value] fits the observations equally
well. Enumeration scans observed values and keeps the first maximal one, so it
settles on the bottom of that plateau. Binary search locates the plateau and
takes the endpoint that is tightest against the approved observations, which
recovers the true threshold exactly whenever a boundary case was observed.

Writes runs/a8_result.json. Never touches runs/stage2_*.json or
runs/store_data*.db -- ablated replays go to a8_-prefixed paths.
"""

import json
import os
import re
import subprocess
import sys

import yaml

SEEDS = [0, 1, 2, 3, 7, 11]
POLICIES = ['refund_window', 'price_match_cap', 'exchange_eligibility',
            'exception_approval', 'shipping_upgrade', 'loyalty_discount']
TMP = "detect/eval_stage2_a8_tmp.py"

BINARY_MINER = '''
def mine_constraint(recent_traces, v0_constraint, action_true, action_false):
    parts = v0_constraint.split(' ')
    attr = parts[0]
    op = parts[1]
    vals = []
    labelled = []
    for t in recent_traces:
        for e in t.get('events', []):
            v = e['attrs'][attr]
            vals.append(v)
            labelled.append((v, e['decision'] == action_true))
    if not vals:
        return v0_constraint

    if isinstance(vals[0], str):
        best_fit, best_c = -1, v0_constraint
        for v in set(vals):
            c = f"{attr} {op} '{v}'"
            fit_sum = total = 0
            for val, is_true in labelled:
                try:
                    if is_true == eval(c, {"__builtins__": {}}, {attr: val}):
                        fit_sum += 1
                except Exception:
                    pass
                total += 1
            if total and fit_sum / total > best_fit:
                best_fit, best_c = fit_sum / total, c
        return best_c

    def fit(thresh):
        c = f"{attr} {op} {thresh}"
        ok = 0
        for val, is_true in labelled:
            try:
                if is_true == eval(c, {"__builtins__": {}}, {attr: val}):
                    ok += 1
            except Exception:
                pass
        return ok / len(labelled) if labelled else 0

    lo, hi = int(min(vals)), int(max(vals))
    # Scan the whole attribute range rather than only observed values. The fit
    # of a threshold rule is piecewise constant and changes only at observed
    # points, so the maximisers form one or more plateaux; enumeration keeps
    # the first maximal *observed* value and therefore sits at the bottom of a
    # plateau. Take the plateau endpoint tightest against the approved side.
    scores = [(t, fit(t)) for t in range(lo, hi + 1)]
    best = max(sc for _, sc in scores)
    maximal = [t for t, sc in scores if sc == best]
    approved = [v for v, is_true in labelled if is_true]
    if op in ('>=', '>'):
        anchor = min(approved) if approved else max(maximal)
    else:
        anchor = max(approved) if approved else min(maximal)
    chosen = min(maximal, key=lambda t: (abs(t - anchor), t))
    return f"{attr} {op} {chosen}"

def retrospective_scan(buffer):
'''


def build_source(binary):
    orig = open("detect/eval_stage2.py").read()
    mod = orig
    if binary:
        mod = re.sub(r'def mine_constraint\(.*?\ndef retrospective_scan\(buffer\):',
                     BINARY_MINER, mod, flags=re.DOTALL)
        assert mod != orig, "A8: mine_constraint block not replaced"
    assert "runs/stage2_seed{seed}.json" in mod
    mod = mod.replace("runs/stage2_seed{seed}.json", "runs/a8_stage2_seed{seed}.json")
    assert "runs/store_data{seed}.db" in mod
    mod = mod.replace("runs/store_data{seed}.db", "runs/a8_store_data{seed}.db")
    return mod


def mined_for(binary):
    """Return {seed: {policy: mined_constraint}} for one miner."""
    open(TMP, "w").write(build_source(binary))
    orig_config = open("config/experiment.yaml").read()
    out = {}
    try:
        for seed in SEEDS:
            conf = yaml.safe_load(orig_config)
            conf["data_seed"] = seed
            open("config/experiment.yaml", "w").write(yaml.dump(conf))
            subprocess.run(["python3", "data/build_benchmark.py"], stdout=subprocess.DEVNULL)
            r = subprocess.run(["python3", TMP, str(seed)], capture_output=True, text=True)
            if r.returncode:
                print(f"  seed {seed} FAILED: {r.stderr.strip().splitlines()[-1][:120]}")
                continue
            mined = {}
            for line in r.stdout.split("\n"):
                if line.startswith("MINED "):
                    parts = line.split(" ")
                    mined[parts[1]] = " ".join(parts[4:])
            truth = {}
            man = json.load(open("data/manifest.json"))["change_points"]
            for p in POLICIES:
                if not man.get(p):
                    continue
                try:
                    truth[p] = json.load(open(f"data/policies/{p}_v1.json"))["constraint"]
                except Exception:
                    pass
            out[seed] = {"mined": mined, "true": truth}
    finally:
        open("config/experiment.yaml", "w").write(orig_config)
        subprocess.run(["python3", "data/build_benchmark.py"], stdout=subprocess.DEVNULL)
        if os.path.exists(TMP):
            os.remove(TMP)
    return out


def band_error_rate(mined_c, true_c):
    """Fraction of integer points in the mined-to-true band answered wrongly."""
    tn = re.search(r'-?\d+', true_c)
    mn = re.search(r'-?\d+', mined_c)
    if not tn or not mn:
        return None
    t_num, m_num = int(tn.group()), int(mn.group())
    if t_num == m_num:
        return {"gap": 0, "band": [], "error_rate": 0.0}
    attr = mined_c.split(" ")[0]
    lo, hi = min(m_num, t_num), max(m_num, t_num)
    band = list(range(lo, hi + 1))
    wrong = 0
    for v in band:
        env = {attr: v}
        try:
            if eval(true_c, {"__builtins__": {}}, env) != eval(mined_c, {"__builtins__": {}}, env):
                wrong += 1
        except Exception:
            pass
    return {"gap": abs(t_num - m_num), "band": [lo, hi],
            "error_rate": wrong / len(band) if band else 0.0}


def tasks_in_band(policy, band):
    """How many generated benchmark tasks land inside the band."""
    if not band:
        return 0
    tasks = json.load(open("data/tasks/tasks.json"))
    n = 0
    for t in tasks:
        if t["policy_id"] != policy:
            continue
        for v in (t.get("task_params") or {}).values():
            if isinstance(v, (int, float)) and band[0] <= v <= band[1]:
                n += 1
    return n


def main():
    print("A8 part one: enumeration miner")
    enum = mined_for(binary=False)
    print("A8 part one: binary-search miner")
    binr = mined_for(binary=True)

    rows = []
    for seed in SEEDS:
        e, b = enum.get(seed), binr.get(seed)
        if not e or not b:
            continue
        for p in POLICIES:
            true_c = e["true"].get(p)
            if not true_c:
                continue
            em, bm = e["mined"].get(p), b["mined"].get(p)
            rows.append({
                "seed": seed, "policy": p, "true": true_c,
                "enumerate": em, "binary": bm,
                "enumerate_exact": em == true_c, "binary_exact": bm == true_c,
                "enumerate_band": band_error_rate(em, true_c) if em else None,
                "binary_band": band_error_rate(bm, true_c) if bm else None,
            })

    n = len(rows)
    e_ok = sum(1 for r in rows if r["enumerate_exact"])
    b_ok = sum(1 for r in rows if r["binary_exact"])
    print(f"\nexact recovery: enumeration {e_ok}/{n}, binary search {b_ok}/{n}\n")
    print(f"{'seed':>4} {'policy':22} {'true':28} {'enumerate':28} {'binary':28}")
    for r in rows:
        print(f"{r['seed']:>4} {r['policy']:22} {r['true']:28} "
              f"{str(r['enumerate']):28} {str(r['binary']):28}")

    # part two: adversarial band
    print("\nA8 part two: adversarial band under the enumeration miner")
    band_rows = []
    for r in rows:
        eb = r["enumerate_band"]
        if eb and eb["gap"]:
            in_band = tasks_in_band(r["policy"], eb["band"])
            band_rows.append({**{k: r[k] for k in ("seed", "policy", "true", "enumerate")},
                              **eb, "benchmark_tasks_in_band": in_band})
            print(f"  seed {r['seed']:>2} {r['policy']:22} band {eb['band']} "
                  f"gap {eb['gap']:>3}  error_rate_in_band {eb['error_rate']:.2f}  "
                  f"benchmark tasks in band: {in_band}")
    if not band_rows:
        print("  no gaps under the enumeration miner")

    out = {"rows": rows,
           "exact_recovery": {"enumerate": e_ok, "binary": b_ok, "n": n},
           "adversarial_band": band_rows}
    json.dump(out, open("runs/a8_result.json", "w"), indent=2)
    print("\nwrote runs/a8_result.json")


if __name__ == "__main__":
    main()
