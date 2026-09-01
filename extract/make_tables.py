import os
import json
import glob
import sys

run_files = glob.glob('runs/*.json')
if not run_files:
    print("No runs found.")
    sys.exit(1)

valid_config_hash = None
valid_manifest_hash = None

conditions_data = {}

for rf in run_files:
    if os.path.basename(rf).startswith('stage'):
        continue
    
    with open(rf, 'r') as f:
        data = json.load(f)
        
    if not data.get('gates_passed', False):
        print(f"Validation failed: gates_passed false in {rf}")
        sys.exit(1)
        
    if data.get('canary_flips', 0) > 0:
        print(f"Validation failed: canary_flips > 0 in {rf}")
        sys.exit(1)
        
    chash = data['config_hash']
    mhash = data['data_manifest_hash']
    
    if valid_config_hash is None:
        valid_config_hash = chash
        valid_manifest_hash = mhash
    else:
        if chash != valid_config_hash or mhash != valid_manifest_hash:
            print(f"Validation failed: hash mismatch in {rf}")
            sys.exit(1)
            
    cond = data['condition']
    if cond not in conditions_data:
        conditions_data[cond] = []
    conditions_data[cond].append(data)

def format_metric(vals, is_int=False):
    if not vals:
        return ""
    mean = sum(vals) / len(vals)
    min_v = min(vals)
    max_v = max(vals)
    if is_int:
        return f"{int(mean)} [{int(min_v)}-{int(max_v)}]" if min_v != max_v else f"{int(mean)}"
    if min_v == max_v:
        return f"{mean:.2f}"
    return f"{mean:.2f} [{min_v:.2f}-{max_v:.2f}]"

ordered_conditions = [
    'floor_static_v0',
    'oracle_expiry',
    'latest_timestamp',
    'full_history_brute',
    'plain_rag',
    'bitemporal_drift'
]

main_lines = [
    "| Condition | pass1 | pass4 | stale_action_rate | unchanged_pass1 (guard) | tokens_per_task (cost) | latency |",
    "|---|---|---|---|---|---|---|"
]

slice_lines = [
    "| Condition | Documented | Lagged | Rollback | Pre | Window | Post | Unchanged |",
    "|---|---|---|---|---|---|---|---|"
]

def format_row(cond):
    runs = conditions_data.get(cond, [])
    if not runs:
        return None, None
        
    pass1_vals = [r['pass1'] for r in runs]
    pass4_vals = [r['pass4'] for r in runs]
    stale_vals = [r['stale_action_rate'] for r in runs]
    unchanged_vals = [r['unchanged_pass1'] for r in runs]
    tokens_vals = [r['tokens_per_task'] for r in runs]
    latency_vals = [r['latency_s_per_task'] for r in runs]
    
    main_row = f"| {cond} | {format_metric(pass1_vals)} | {format_metric(pass4_vals)} | {format_metric(stale_vals)} | {format_metric(unchanged_vals)} | {format_metric(tokens_vals, True)} | {format_metric(latency_vals)} |"
    
    slices = ['documented', 'lagged', 'rollback', 'pre', 'window', 'post', 'unchanged']
    slice_vals = []
    for s in slices:
        v = [r['slice'][s]['pass1'] for r in runs]
        slice_vals.append(format_metric(v))
        
    slice_row = f"| {cond} | " + " | ".join(slice_vals) + " |"
    return main_row, slice_row

floor_main, floor_slice = format_row('floor_static_v0')
print("FLOOR ROW:")
print(floor_main)
print(floor_slice)
print()

for cond in ordered_conditions:
    mrow, srow = format_row(cond)
    if mrow:
        main_lines.append(mrow)
        slice_lines.append(srow)

with open('tables/main_table.md', 'w') as f:
    f.write("\n".join(main_lines) + "\n")

with open('tables/slice_table.md', 'w') as f:
    f.write("\n".join(slice_lines) + "\n")

with open('paper/results_section.md', 'w') as f:
    f.write("# Results\n\n## Main Results\n\n")
    f.write("\n".join(main_lines) + "\n\n")
    f.write("## Slice Results\n\n")
    f.write("\n".join(slice_lines) + "\n")

print("Tables and results_section generated.")
