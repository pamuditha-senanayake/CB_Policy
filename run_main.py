import yaml
import subprocess
import os

with open('config/experiment.yaml', 'r') as f:
    config = yaml.safe_load(f)

models = config['models']
run_seeds = config['run_seeds']
conditions = ['floor_static_v0', 'bitemporal_drift', 'oracle_expiry', 'latest_timestamp', 'plain_rag', 'full_history_brute']

failures = []

for m in models:
    provider = m['provider']
    model = m['model']
    for seed in run_seeds:
        for cond in conditions:
            print(f"Running {provider}/{model} seed {seed} condition {cond}...")
            try:
                subprocess.run(['python3', 'agent/harness.py', cond, str(seed), provider, model], check=True)
            except subprocess.CalledProcessError as e:
                print(f"Failed {provider}/{model} on {cond}: {e}")
                failures.append(f"{provider}/{model} on {cond} seed {seed}")
                
with open('failures.txt', 'w') as f:
    f.write("\n".join(failures))
