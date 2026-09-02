import json
import glob

conditions = ['floor_static_v0', 'bitemporal_drift', 'oracle_expiry', 'latest_timestamp', 'plain_rag', 'full_history_brute']

print("=== Main Table (Pass 1) ===")
for cond in conditions:
    try:
        with open(f"runs/{cond}_s11.json", 'r') as f:
            data = json.load(f)
            print(f"{cond:<20} {data['pass1']:.3f}")
    except:
        pass

print("\n=== S1 Table: Document Status Slice (Changed Policies) ===")
for cond in conditions:
    try:
        with open(f"runs/{cond}_s11.json", 'r') as f:
            data = json.load(f)
            doc_docs = data.get('doc_slice_documented', 0)
            doc_lag = data.get('doc_slice_lagged', 0)
            doc_roll = data.get('doc_slice_rollback', 0)
            print(f"{cond:<20} | Documented: {doc_docs:.3f} | Lagged: {doc_lag:.3f} | Rollback: {doc_roll:.3f}")
    except:
        pass

print("\n=== S2 Table: Task Position Slice (Changed Policies) ===")
for cond in conditions:
    try:
        with open(f"runs/{cond}_s11.json", 'r') as f:
            data = json.load(f)
            s_pre = data.get('slice_pre-change_changed', 0)
            s_post = data.get('slice_post-change_changed', 0)
            s_det = data.get('slice_post-detection_changed', 0)
            print(f"{cond:<20} | Pre-Change: {s_pre:.3f} | Post-Change: {s_post:.3f} | Post-Detection: {s_det:.3f}")
    except:
        pass

print("\n=== S3 Guard Column (Unchanged Policies) ===")
for cond in conditions:
    try:
        with open(f"runs/{cond}_s11.json", 'r') as f:
            data = json.load(f)
            s_unch = data.get('slice_unchanged', 0)
            print(f"{cond:<20} | Unchanged: {s_unch:.3f}")
    except:
        pass

print("\n=== Stage 2 Correctness Metrics (bitemporal_drift) ===")
for i in range(6):
    try:
        with open(f"runs/stage2_seed{i}.json", 'r') as f:
            data = json.load(f)
            asof = data.get('asof_correctness_postdetection', 0)
            constr = data.get('constraint_correctness', 0)
            print(f"Seed {i}: asof={asof:.3f}, constr={constr:.3f}")
    except:
        pass
