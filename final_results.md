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
