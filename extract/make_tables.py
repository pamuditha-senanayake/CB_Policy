import json
import glob

conditions = ['floor_static_v0', 'bitemporal_drift', 'oracle_expiry', 'latest_timestamp', 'plain_rag', 'full_history_brute']

output_lines = []
output_lines.append("=== Main Table (Pass 1) ===")
output_lines.append(f"{'Condition':<20} | pass1 | chg | unch | stale")
for cond in conditions:
    try:
        with open(f"runs/{cond}_s11.json", 'r') as f:
            data = json.load(f)
            pass1 = data.get('pass1', 0)
            chg = data.get('changed_policy_pass1', 0)
            unch = data.get('unchanged_pass1', 0)
            stale = data.get('stale_action_rate', 0)
            output_lines.append(f"{cond:<20} | {pass1:.3f} | {chg:.3f} | {unch:.3f} | {stale:.3f}")
    except Exception as e:
        print(f"Error reading stage2: {e}")
        raise
        print(f"Error reading {cond}: {e}")
        raise
        pass

output_lines.append("\n=== S1 Table: Document Status Slice (Changed Policies, Post-Change Only) ===")
output_lines.append(f"{'Condition':<20} | Documented | Lagged | Rollback")
for cond in conditions:
    try:
        with open(f"runs/{cond}_s11.json", 'r') as f:
            data = json.load(f)
            doc_docs = data.get('doc_slice_documented', 0)
            doc_lag = data.get('doc_slice_lagged', 0)
            doc_roll = data.get('doc_slice_rollback', 0)
            output_lines.append(f"{cond:<20} | {doc_docs:.3f}      | {doc_lag:.3f}  | {doc_roll:.3f}")
    except Exception as e:
        print(f"Error reading stage2: {e}")
        raise
        print(f"Error reading {cond}: {e}")
        raise
        pass
output_lines.append("\n* Note: bitemporal_drift's 1.000 on the rollback slice occurs because the store collapsed both changes into one late detection (it skipped the perfectly-documented initial change and only detected the undocumented rollback).")

output_lines.append("\n=== S2 Table: Task Position Slice (Changed Policies) ===")
output_lines.append(f"{'Condition':<20} | Pre-Change | Win_Pre | Win_Stale | Post-Det")
for cond in conditions:
    try:
        with open(f"runs/{cond}_s11.json", 'r') as f:
            data = json.load(f)
            s_pre = data.get('slice_pre-change_changed', 0)
            s_win_pre = data.get('slice_window_pre_detection_changed', 0)
            s_win_stale = data.get('slice_window_detected_doc_stale_changed', 0)
            s_post = data.get('slice_post-detection_changed', 0)
            output_lines.append(f"{cond:<20} | {s_pre:.3f}      | {s_win_pre:.3f}   | {s_win_stale:.3f}     | {s_post:.3f}")
    except Exception as e:
        print(f"Error reading stage2: {e}")
        raise
        print(f"Error reading {cond}: {e}")
        raise
        pass

output_lines.append("\n=== S3 Guard Column (Unchanged Policies) ===")
output_lines.append(f"{'Condition':<20} | Unchanged")
for cond in conditions:
    try:
        with open(f"runs/{cond}_s11.json", 'r') as f:
            data = json.load(f)
            s_unch = data.get('slice_unchanged', 0)
            output_lines.append(f"{cond:<20} | {s_unch:.3f}")
    except Exception as e:
        print(f"Error reading stage2: {e}")
        raise
        print(f"Error reading {cond}: {e}")
        raise
        pass

output_lines.append("\n=== Stage 2 Correctness Metrics (bitemporal_drift) ===")
# Seeds are 0, 1, 2, 3, 7, 11
for i in [0, 1, 2, 3, 7, 11]:
    try:
        with open(f"runs/stage2_seed{i}.json", 'r') as f:
            data = json.load(f)
            asof = data.get('asof_correctness_postdetection', 0)
            constr = data.get('constraint_correctness', 0)
            output_lines.append(f"Seed {i}: asof={asof:.3f}, constr={constr:.3f}")
    except Exception as e:
        print(f"Error reading stage2: {e}")
        raise
        print(f"Error reading {cond}: {e}")
        raise
        pass

final_text = "\n".join(output_lines)
print(final_text)
with open('final_results.md', 'w') as f:
    f.write(final_text)

print("\n=== Stage 2 Correctness Metrics (bitemporal_drift) ===")
for seed in [0, 1, 2, 3, 7, 11]:
    try:
        with open(f"runs/stage2_seed{seed}.json", "r") as f:
            import json
            s2 = json.load(f)
            print(f"\n--- Seed {seed} ---")
            print(f"asof_correctness_postdetection: {s2.get('asof_correctness_postdetection', 0):.3f}")
            print(f"constraint_correctness: {s2.get('constraint_correctness', 0):.3f}")
            print(f"valid_time_error_traces: {s2.get('valid_time_error_traces', 0):.2f}")
            print(f"per_policy_errors: {s2.get('per_policy_errors', {})}")
            print(f"rollback_handled: {s2.get('rollback_handled', False)}")
            print(f"false_invalidation_rate: {s2.get('false_invalidation_rate', 0):.3f}")
    except Exception as e:
        print(f"Error reading stage2: {e}")
        raise
        pass