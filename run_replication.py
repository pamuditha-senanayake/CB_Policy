import subprocess
import yaml
import sys
import os

models = [
    {"provider": "deepseek", "model": "deepseek-v4-flash", "primary": True},
    {"provider": "anthropic", "model": "claude-sonnet-5"},
    {"provider": "openai", "model": "gpt-5.6-luna"}
]
seeds = [11, 13, 17]
conditions = ['floor_static_v0', 'bitemporal_drift', 'oracle_expiry', 'latest_timestamp', 'plain_rag', 'full_history_brute']

with open('config/experiment.yaml', 'r') as f:
    orig = f.read()

for m in models:
    for s in seeds:
        for c in conditions:
            print(f"\n>>> Running Model={m['model']}, Seed={s}, Cond={c}")
            conf = yaml.safe_load(orig)
            conf['models'] = [m]
            conf['run_seeds'] = [s]
            # Write temp config
            with open('config/experiment.yaml', 'w') as f:
                yaml.dump(conf, f)
            
            # Since pipeline requires data, generate data for seed 0 (data_seed is 0 for all)
            # Actually data_seed is 0 and already generated. We don't need to rebuild benchmark unless we need to.
            # Just run the python agent/harness.py
            subprocess.run(["python3", "agent/harness.py", "--condition", c], stdout=subprocess.DEVNULL)
            
            # Also rescore!
            subprocess.run(["python3", "extract/rescore.py", "--condition", c, "--seed", str(s)], stdout=subprocess.DEVNULL)

with open('config/experiment.yaml', 'w') as f:
    f.write(orig)
