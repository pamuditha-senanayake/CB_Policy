import re
import subprocess
import json

with open("detect/eval_stage2.py", 'r') as f:
    orig = f.read()

results = {}
for length in [50, 150, 300]:
    mod = orig.replace("if len(fitness_buffer[p]) > 150:", f"if len(fitness_buffer[p]) > {length}:")
    with open("detect/eval_stage2_tmp.py", 'w') as f:
        f.write(mod)
    subprocess.run(["python3", "detect/eval_stage2_tmp.py"], stdout=subprocess.DEVNULL)
    with open("runs/stage2_seed0.json", "r") as f: # since seed is hardcoded to 0 if not sys argv? 
        pass # Wait, let's see where it saves! eval_stage2_tmp.py saves to `runs/stage2_seed{seed}.json`.
    
    # eval_stage2.py defaults to seed 0 or reads config!
    # we can just read `runs/stage2_seed0.json`.
    with open("runs/stage2_seed0.json", "r") as f:
        res = json.load(f)
        results[length] = res["valid_time_error_traces"]

print(json.dumps(results, indent=2))
with open('runs/a7_sweep.json', 'w') as f:
    json.dump(results, f, indent=2)

import os
os.remove("detect/eval_stage2_tmp.py")
