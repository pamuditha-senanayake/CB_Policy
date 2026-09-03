#!/usr/bin/env python3
"""Multi-model sweep driver.

Order and guards matter here:

* Every model must pass agent/validate_models.py before any condition runs.
  A model that cannot return parseable text is skipped, not swept.
* Conditions run cheapest-first, so a provider that hits its budget cap loses
  only `full_history_brute` (about 60% of a table's cost) and still yields the
  complete slice signature.
* A provider that goes unavailable or over budget is skipped; the sweep
  continues with the remaining providers.
"""

import os
import subprocess
import sys

import yaml

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from agent import spend  # noqa: E402
from agent.validate_models import is_validated  # noqa: E402

MODELS = [
    {"provider": "deepseek", "model": "deepseek-chat", "primary": True},
    {"provider": "openai", "model": "gpt-5.6-luna"},
    {"provider": "anthropic", "model": "claude-sonnet-5"},
]
SEEDS = [11, 13, 17]

# Cheapest first; full_history_brute last because it is the dominant cost.
CONDITIONS = ["floor_static_v0", "bitemporal_drift", "oracle_expiry",
              "latest_timestamp", "plain_rag", "full_history_brute"]

ABLATIONS = ["a2", "a3", "a4", "a5_absent", "a5_neutral"]

# Allow narrowing the sweep, e.g. CONDITIONS=floor_static_v0,bitemporal_drift
_env_conds = os.environ.get("CONDITIONS")
if _env_conds:
    CONDITIONS = [c for c in CONDITIONS if c in _env_conds.split(",")]
_env_seeds = os.environ.get("SEEDS")
if _env_seeds:
    SEEDS = [int(s) for s in _env_seeds.split(",")]
SKIP_ABLATIONS = os.environ.get("SKIP_ABLATIONS") == "1"

# Exit codes agent/harness.py uses to signal "stop spending on this provider".
SKIP_PROVIDER_CODES = {3: "budget cap", 4: "provider unavailable"}

with open("config/experiment.yaml") as f:
    ORIG = f.read()


def write_config(model, seed):
    conf = yaml.safe_load(ORIG)
    conf["models"] = [model]
    conf["run_seeds"] = [seed]
    conf["data_seed"] = 0
    with open("config/experiment.yaml", "w") as f:
        yaml.dump(conf, f)


# Re-validate well before the harness's 60-minute gate so a long sweep is
# never killed mid-flight by its own freshness check.
REVALIDATE_AFTER = 35 * 60


def ensure_validated(m):
    ok, _ = is_validated(m["provider"], m["model"], max_age=REVALIDATE_AFTER)
    if ok:
        return True
    print(f"    (re-validating {m['provider']}/{m['model']})")
    r = subprocess.run(["python3", "agent/validate_models.py", "--models",
                        f"{m['provider']}/{m['model']}", "--n", "20"],
                       stdout=subprocess.DEVNULL)
    ok, why = is_validated(m["provider"], m["model"])
    if not ok:
        print(f"    !! re-validation failed: {why}")
    return ok


def run_one(condition, seed, m):
    if not ensure_validated(m):
        return 2
    write_config(m, seed)
    subprocess.run(["python3", "data/build_benchmark.py"], stdout=subprocess.DEVNULL)
    r = subprocess.run(["python3", "agent/harness.py", condition, str(seed),
                        m["provider"], m["model"]])
    return r.returncode


def main():
    only = sys.argv[1:] or None
    models = [m for m in MODELS if not only or m["model"] in only or m["provider"] in only]

    usable = []
    for m in models:
        # Refresh a stale record rather than skipping: staleness means "not
        # checked recently", not "known bad".
        ok = ensure_validated(m)
        _, why = is_validated(m["provider"], m["model"])
        print(f"{'OK  ' if ok else 'SKIP'} {m['provider']}/{m['model']}: {why}")
        if ok:
            usable.append(m)
    if not usable:
        print("\nNo validated models. Run: python3 agent/validate_models.py")
        return 1

    try:
        for m in usable:
            prov = m["provider"]
            skipped = False
            for s in SEEDS:
                if skipped:
                    break
                for c in CONDITIONS:
                    print(f"\n--- {m['model']} seed {s} cond {c} ---")
                    code = run_one(c, s, m)
                    if code in SKIP_PROVIDER_CODES:
                        print(f"!! skipping remaining {prov} runs: "
                              f"{SKIP_PROVIDER_CODES[code]}")
                        skipped = True
                        break
                    if code != 0:
                        print(f"!! {c} seed {s} failed (exit {code}), continuing")
            print(f"\nSpend after {m['model']}:\n{spend.summary()}")

        primary = next((m for m in usable if m.get("primary")), None)
        if primary and not SKIP_ABLATIONS:
            for c in ABLATIONS:
                print(f"\n--- ABLATION {primary['model']} seed 11 cond {c} ---")
                run_one(c, 11, primary)
        else:
            print("\nPrimary model unavailable; ablations A2-A5 skipped.")
    finally:
        with open("config/experiment.yaml", "w") as f:
            f.write(ORIG)

    print(f"\nFinal spend:\n{spend.summary()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
