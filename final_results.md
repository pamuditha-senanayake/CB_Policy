=== Main Table (Pass 1) ===
Condition            | pass1 | chg | unch | stale
floor_static_v0      | 0.554 | 0.406 | 1.000 | 0.825
bitemporal_drift     | 0.863 | 0.817 | 1.000 | 0.188
oracle_expiry        | 0.967 | 0.956 | 1.000 | 0.000
latest_timestamp     | 0.713 | 0.617 | 1.000 | 0.508
plain_rag            | 0.579 | 0.617 | 0.467 | 0.435
full_history_brute   | 0.808 | 0.744 | 1.000 | 0.306

=== S1 Table: Document Status Slice (Changed Policies, Post-Change Only) ===
Condition            | Documented | Lagged | Rollback
floor_static_v0      | 0.000      | 0.000  | 1.000
bitemporal_drift     | 1.000      | 0.590  | 1.000
oracle_expiry        | 1.000      | 1.000  | 1.000
latest_timestamp     | 1.000      | 0.344  | 0.000
plain_rag            | 0.684      | 0.492  | 0.524
full_history_brute   | 0.711      | 0.623  | 0.476

* Note: bitemporal_drift's 1.000 on the rollback slice occurs because the store collapsed both changes into one late detection (it skipped the perfectly-documented initial change and only detected the undocumented rollback).

=== S2 Table: Task Position Slice (Changed Policies) ===
Condition            | Pre-Change | Win_Pre | Win_Stale | Post-Det
floor_static_v0      | 0.867      | 0.000   | 0.000     | 0.263
bitemporal_drift     | 0.867      | 0.000   | 0.750     | 1.000
oracle_expiry        | 0.867      | 1.000   | 1.000     | 1.000
latest_timestamp     | 0.867      | 0.000   | 0.000     | 0.738
plain_rag            | 0.733      | 0.400   | 0.500     | 0.613
full_history_brute   | 0.983      | 0.400   | 0.750     | 0.650

=== S3 Guard Column (Unchanged Policies) ===
Condition            | Unchanged
floor_static_v0      | 1.000
bitemporal_drift     | 1.000
oracle_expiry        | 1.000
latest_timestamp     | 1.000
plain_rag            | 0.467
full_history_brute   | 1.000

=== Stage 2 Correctness Metrics (bitemporal_drift) ===
Seed 0: asof=1.000, constr=1.000
Seed 1: asof=1.000, constr=1.000
Seed 2: asof=1.000, constr=1.000
Seed 3: asof=1.000, constr=1.000
Seed 7: asof=1.000, constr=1.000
Seed 11: asof=1.000, constr=1.000

=== Stage 2 Correctness Metrics (bitemporal_drift) ===

--- Seed 0 ---
asof_correctness_postdetection: 1.000
constraint_correctness: 1.000
valid_time_error_traces: 13.33
per_policy_errors: {'refund_window': 'no_drift_required', 'price_match_cap': 'no_drift_required', 'exchange_eligibility': 'no_drift_required', 'exception_approval': 5, 'shipping_upgrade': 20, 'loyalty_discount': 15}
rollback_handled: True
false_invalidation_rate: 0.000

--- Seed 1 ---
asof_correctness_postdetection: 1.000
constraint_correctness: 1.000
valid_time_error_traces: 23.33
per_policy_errors: {'refund_window': 'no_drift_required', 'price_match_cap': 'no_drift_required', 'exchange_eligibility': 'no_drift_required', 'exception_approval': 2, 'shipping_upgrade': 37, 'loyalty_discount': 31}
rollback_handled: True
false_invalidation_rate: 0.000

--- Seed 2 ---
asof_correctness_postdetection: 1.000
constraint_correctness: 1.000
valid_time_error_traces: 11.00
per_policy_errors: {'refund_window': 'no_drift_required', 'price_match_cap': 'no_drift_required', 'exchange_eligibility': 'no_drift_required', 'exception_approval': 4, 'shipping_upgrade': 22, 'loyalty_discount': 7}
rollback_handled: True
false_invalidation_rate: 0.000

--- Seed 3 ---
asof_correctness_postdetection: 1.000
constraint_correctness: 1.000
valid_time_error_traces: 17.00
per_policy_errors: {'refund_window': 'no_drift_required', 'price_match_cap': 'no_drift_required', 'exchange_eligibility': 'no_drift_required', 'exception_approval': 8, 'shipping_upgrade': 38, 'loyalty_discount': 5}
rollback_handled: True
false_invalidation_rate: 0.000

--- Seed 7 ---
asof_correctness_postdetection: 1.000
constraint_correctness: 1.000
valid_time_error_traces: 28.33
per_policy_errors: {'refund_window': 'no_drift_required', 'price_match_cap': 'no_drift_required', 'exchange_eligibility': 'no_drift_required', 'exception_approval': 6, 'shipping_upgrade': 37, 'loyalty_discount': 42}
rollback_handled: True
false_invalidation_rate: 0.000

--- Seed 11 ---
asof_correctness_postdetection: 1.000
constraint_correctness: 1.000
valid_time_error_traces: 16.33
per_policy_errors: {'refund_window': 'no_drift_required', 'price_match_cap': 'no_drift_required', 'exchange_eligibility': 'no_drift_required', 'exception_approval': 4, 'shipping_upgrade': 36, 'loyalty_discount': 9}
rollback_handled: True
false_invalidation_rate: 0.000
