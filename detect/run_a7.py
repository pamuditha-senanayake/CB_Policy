import re
import subprocess
import json
import yaml
import os

with open("detect/eval_stage2.py", 'r') as f:
    orig = f.read()

results = {}
seeds = [0, 1, 2, 3, 7, 11]

# Save original config
with open('config/experiment.yaml', 'r') as f:
    orig_config = f.read()

for length in [50, 150, 300]:
    mod = orig.replace("if len(fitness_buffer[p]) > 150:", f"if len(fitness_buffer[p]) > {length}:")
    with open("detect/eval_stage2_tmp.py", 'w') as f:
        f.write(mod)
        
    error_traces = []
    for seed in seeds:
        conf = yaml.safe_load(orig_config)
        conf['data_seed'] = seed
        with open('config/experiment.yaml', 'w') as f:
            yaml.dump(conf, f)
            
        subprocess.run(["python3", "data/build_benchmark.py"], stdout=subprocess.DEVNULL)
        subprocess.run(["python3", "detect/eval_stage2_tmp.py"], stdout=subprocess.DEVNULL)
        
        with open(f"runs/stage2_seed{seed}.json", "r") as f:
            res = json.load(f)
            error_traces.append(res["valid_time_error_traces"])
            
    results[length] = sum(error_traces) / len(error_traces)

with open('config/experiment.yaml', 'w') as f:
    f.write(orig_config)
subprocess.run(["python3", "data/build_benchmark.py"], stdout=subprocess.DEVNULL)
os.remove("detect/eval_stage2_tmp.py")

print(json.dumps(results, indent=2))
with open('runs/a7_sweep.json', 'w') as f:
    json.dump(results, f, indent=2)
