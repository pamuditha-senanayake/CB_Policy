# Multi-model replication results

Every value below is read directly from a run record in `runs/`. Cells are `mean [min-max]` across the seeds that produced a record. Missing seeds are named, never averaged over.

## Model validation (STEP 5)

20 real task prompts per model at `max_tokens=32`. A model passes only with 0% empty and <2% unparseable.

| provider | model | empty% | unparse% | mean_out_tok | accepts | verdict |
|---|---|---|---|---|---|---|
| anthropic | claude-sonnet-5 | 0.0 | 0.0 | 7.90 | `max_tokens, no-temp` | **PASS** |
| deepseek | deepseek-chat | 0.0 | 0.0 | 3.95 | `max_tokens` | **PASS** |
| deepseek | deepseek-v4-flash | 0.0 | 0.0 | 75.40 | `max_tokens` | **PASS** |
| openai | gpt-5.6-luna | 0.0 | 0.0 | 10.35 | `max_completion_tokens, no-temp` | **PASS** |

`deepseek-v4-flash` passes only because `providers.complete()` escalates the token budget on every call (mean 75.4 output tokens vs 3.95 for `deepseek-chat`, a 19x difference on the most expensive token type). `deepseek-chat` was selected as the DeepSeek model: it is far cheaper and matches the provenance of the existing verified table.

## Stage 1: detection (recovered artifacts)

`runs/stage1_*.json` was recovered from commit `32df3d5` and each file re-derived by rerunning `detect/eval_stage1.py` against a freshly rebuilt benchmark per seed. All 21 files reproduce byte-identically.

| detector | recall | FPR | mean delay | delay range | seeds |
|---|---|---|---|---|---|
| ADWIN delta=0.1 (selected) | 1.000 | 0.000 | 43.38 | [41.86-46.43] | 6 |
| ADWIN delta=0.002 (default) | 0.905 | 0.083 | 61.48 | [57.00-64.71] | 6 |
| Page-Hinkley | 0.071 | 0.812 | 47.00 | [0.00-100.00] | 6 |

The preregistered Stage 1 thresholds are recall >= 0.90, mean delay < 50 and FPR < 0.10. `delta=0.1` meets all three on every seed; the default `delta=0.002` misses recall on four of six seeds and the delay bound on all six; Page-Hinkley fails outright (recall 0.071 at FPR 0.812).

## Main tables (one per model, never mixed)

### deepseek / `deepseek-chat`

| condition | seeds | pass^1 | pass^4 | stale-action rate | changed pass^1 | unchanged pass^1 | tokens/task | unparseable n |
|---|---|---|---|---|---|---|---|---|
| floor_static_v0 | 11,13,17 | 59.9 [55.4-62.1] | 56.5 [53.8-62.1] | 68.6 [65.8-70.0] | 46.5 [40.6-49.4] | 100.0 [100.0-100.0] | 361.0 [361.0-361.0] | 0 |
| bitemporal_drift | 11,13,17 | 84.7 [84.6-85.0] | 82.6 [81.2-83.3] | 20.6 [19.0-22.5] | 79.6 [79.4-80.0] | 100.0 [100.0-100.0] | 368.5 [368.5-368.5] | 0 |
| oracle_expiry | 11,13,17 | 88.5 [87.9-89.6] | 87.9 [87.9-87.9] | 10.6 [7.1-14.2] | 84.6 [83.9-86.1] | 100.0 [100.0-100.0] | 361.0 [361.0-361.0] | 0 |
| latest_timestamp | 11,13,17 | 70.7 [68.8-71.7] | 68.6 [67.1-71.7] | 46.9 [46.5-47.7] | 60.9 [58.3-62.2] | 100.0 [100.0-100.0] | 361.0 [361.0-361.0] | 0 |
| plain_rag | 11,13,17 | 58.6 [55.0-61.3] | 54.3 [50.4-59.2] | 34.9 [34.8-35.0] | 62.6 [57.8-66.1] | 46.7 [46.7-46.7] | 354.7 [354.7-354.7] | 3 |
| full_history_brute | 11,13,17 | 80.1 [79.6-81.2] | 79.6 [79.6-79.6] | 36.7 [36.7-36.7] | 73.5 [72.8-75.0] | 100.0 [100.0-100.0] | 4912.7 [4912.7-4912.7] | 0 |

### openai / `gpt-5.6-luna`

| condition | seeds | pass^1 | pass^4 | stale-action rate | changed pass^1 | unchanged pass^1 | tokens/task | unparseable n |
|---|---|---|---|---|---|---|---|---|
| floor_static_v0 | 11,13,17 | 58.8 [58.8-58.8] | 58.8 [58.8-58.8] | 82.5 [82.5-82.5] | 45.0 [45.0-45.0] | 100.0 [100.0-100.0] | 454.7 [415.7-480.4] | 0 |
| bitemporal_drift | 11,13,17 | 88.6 [87.5-90.8] | 87.5 [87.5-87.5] | 22.2 [20.0-25.0] | 84.8 [83.3-87.8] | 100.0 [100.0-100.0] | 453.0 [432.8-468.9] | 0 |
| oracle_expiry | 11,13,17 | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] | 0.0 [0.0-0.0] | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] | 433.9 [410.1-447.8] | 0 |
| latest_timestamp | 11,13,17 | 74.6 [74.6-74.6] | 74.6 [74.6-74.6] | 50.8 [50.8-50.8] | 66.1 [66.1-66.1] | 100.0 [100.0-100.0] | 449.8 [433.4-470.9] | 0 |
| plain_rag | 11,13,17 | 59.7 [58.3-60.8] | 57.9 [57.9-57.9] | 47.2 [45.4-48.5] | 60.2 [58.9-61.7] | 58.3 [56.7-60.0] | 928.6 [916.6-938.3] | 0 |
| full_history_brute | 11,13,17 | 93.1 [92.9-93.3] | 84.2 [79.6-89.2] | 17.0 [14.2-19.4] | 90.7 [90.6-91.1] | 100.0 [100.0-100.0] | 7062.1 [6824.7-7335.7] | 10 |

### anthropic / `claude-sonnet-5`

| condition | seeds | pass^1 | pass^4 | stale-action rate | changed pass^1 | unchanged pass^1 | tokens/task | unparseable n |
|---|---|---|---|---|---|---|---|---|
| floor_static_v0 | 11,13,17 | 58.8 [58.8-58.8] | 58.8 [58.8-58.8] | 82.5 [82.5-82.5] | 45.0 [45.0-45.0] | 100.0 [100.0-100.0] | 594.5 [577.1-605.9] | 0 |
| bitemporal_drift | 11,13,17 | 87.5 [87.5-87.5] | 87.5 [87.5-87.5] | 25.0 [25.0-25.0] | 83.3 [83.3-83.3] | 100.0 [100.0-100.0] | 615.3 [611.9-619.4] | 0 |
| oracle_expiry | 11,13,17 | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] | 0.0 [0.0-0.0] | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] | 555.9 [554.9-556.5] | 0 |
| latest_timestamp | 11,13,17 | 74.6 [74.6-74.6] | 74.6 [74.6-74.6] | 50.8 [50.8-50.8] | 66.1 [66.1-66.1] | 100.0 [100.0-100.0] | 581.1 [569.5-588.8] | 0 |
| plain_rag | 11,13,17 | 56.5 [55.8-57.1] | 55.1 [55.0-55.4] | 48.7 [48.5-48.8] | 59.6 [58.9-60.6] | 47.2 [46.7-48.3] | 725.4 [694.6-784.5] | 33 |
| full_history_brute | 11,13 | 91.2 [90.8-91.7] | 87.9 [87.1-88.8] | 13.3 [12.9-13.8] | 88.3 [87.8-88.9] | 100.0 [100.0-100.0] | 12613.4 [12378.0-12848.8] | 31 |

**Missing runs:** full_history_brute seed 17.

## Slice tables

### deepseek / `deepseek-chat` -- S2 task position / S3 policy status

| condition | pre-change_changed | window_pre_detection_changed | window_detected_doc_stale_changed | post-detection_changed | unchanged |
|---|---|---|---|---|---|
| floor_static_v0 | 82.2 [80.0-86.7] | 20.0 [0.0-30.0] | 16.7 [0.0-25.0] | 33.8 [26.2-37.5] | 100.0 [100.0-100.0] |
| bitemporal_drift | 82.2 [80.0-86.7] | 25.0 [15.0-30.0] | 75.0 [75.0-75.0] | 92.5 [92.5-92.5] | 100.0 [100.0-100.0] |
| oracle_expiry | 82.2 [80.0-86.7] | 70.0 [70.0-70.0] | 75.0 [75.0-75.0] | 92.5 [92.5-92.5] | 100.0 [100.0-100.0] |
| latest_timestamp | 82.2 [80.0-86.7] | 20.0 [0.0-30.0] | 16.7 [0.0-25.0] | 66.2 [66.2-66.2] | 100.0 [100.0-100.0] |
| plain_rag | 65.6 [61.7-73.3] | 60.0 [40.0-70.0] | 66.7 [50.0-75.0] | 60.0 [52.5-66.2] | 46.7 [46.7-46.7] |
| full_history_brute | 93.9 [91.7-98.3] | 40.0 [40.0-40.0] | 75.0 [75.0-75.0] | 66.2 [66.2-66.2] | 100.0 [100.0-100.0] |

| condition | lagged | rollback | documented |
|---|---|---|---|
| floor_static_v0 | 21.9 [0.0-32.8] | 100.0 [100.0-100.0] | 0.0 [0.0-0.0] |
| bitemporal_drift | 57.4 [54.1-59.0] | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] |
| oracle_expiry | 72.1 [72.1-72.1] | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] |
| latest_timestamp | 36.6 [24.6-42.6] | 0.0 [0.0-0.0] | 100.0 [100.0-100.0] |
| plain_rag | 61.2 [39.3-72.1] | 52.4 [52.4-52.4] | 65.8 [60.5-71.1] |
| full_history_brute | 62.3 [62.3-62.3] | 100.0 [100.0-100.0] | 44.7 [44.7-44.7] |

### openai / `gpt-5.6-luna` -- S2 task position / S3 policy status

| condition | pre-change_changed | window_pre_detection_changed | window_detected_doc_stale_changed | post-detection_changed | unchanged |
|---|---|---|---|---|---|
| floor_static_v0 | 100.0 [100.0-100.0] | 0.0 [0.0-0.0] | 0.0 [0.0-0.0] | 26.2 [26.2-26.2] | 100.0 [100.0-100.0] |
| bitemporal_drift | 100.0 [100.0-100.0] | 5.0 [0.0-15.0] | 58.3 [50.0-75.0] | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] |
| oracle_expiry | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] |
| latest_timestamp | 100.0 [100.0-100.0] | 0.0 [0.0-0.0] | 0.0 [0.0-0.0] | 73.8 [73.8-73.8] | 100.0 [100.0-100.0] |
| plain_rag | 73.3 [73.3-73.3] | 40.0 [40.0-40.0] | 50.0 [50.0-50.0] | 57.9 [55.0-61.3] | 58.3 [56.7-60.0] |
| full_history_brute | 100.0 [100.0-100.0] | 35.0 [30.0-40.0] | 81.7 [75.0-85.0] | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] |

| condition | lagged | rollback | documented |
|---|---|---|---|
| floor_static_v0 | 0.0 [0.0-0.0] | 100.0 [100.0-100.0] | 0.0 [0.0-0.0] |
| bitemporal_drift | 55.2 [50.8-63.9] | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] |
| oracle_expiry | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] |
| latest_timestamp | 34.4 [34.4-34.4] | 0.0 [0.0-0.0] | 100.0 [100.0-100.0] |
| plain_rag | 49.2 [49.2-49.2] | 52.4 [52.4-52.4] | 61.4 [55.3-68.4] |
| full_history_brute | 72.7 [72.1-73.8] | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] |

### anthropic / `claude-sonnet-5` -- S2 task position / S3 policy status

| condition | pre-change_changed | window_pre_detection_changed | window_detected_doc_stale_changed | post-detection_changed | unchanged |
|---|---|---|---|---|---|
| floor_static_v0 | 100.0 [100.0-100.0] | 0.0 [0.0-0.0] | 0.0 [0.0-0.0] | 26.2 [26.2-26.2] | 100.0 [100.0-100.0] |
| bitemporal_drift | 100.0 [100.0-100.0] | 0.0 [0.0-0.0] | 50.0 [50.0-50.0] | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] |
| oracle_expiry | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] |
| latest_timestamp | 100.0 [100.0-100.0] | 0.0 [0.0-0.0] | 0.0 [0.0-0.0] | 73.8 [73.8-73.8] | 100.0 [100.0-100.0] |
| plain_rag | 76.1 [73.3-78.3] | 40.0 [40.0-40.0] | 50.0 [50.0-50.0] | 54.6 [53.8-55.0] | 47.2 [46.7-48.3] |
| full_history_brute | 100.0 [100.0-100.0] | 20.0 [20.0-20.0] | 75.0 [70.0-80.0] | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] |

| condition | lagged | rollback | documented |
|---|---|---|---|
| floor_static_v0 | 0.0 [0.0-0.0] | 100.0 [100.0-100.0] | 0.0 [0.0-0.0] |
| bitemporal_drift | 50.8 [50.8-50.8] | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] |
| oracle_expiry | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] |
| latest_timestamp | 34.4 [34.4-34.4] | 0.0 [0.0-0.0] | 100.0 [100.0-100.0] |
| plain_rag | 49.2 [49.2-49.2] | 52.4 [52.4-52.4] | 54.4 [52.6-55.3] |
| full_history_brute | 65.6 [63.9-67.2] | 100.0 [100.0-100.0] | 100.0 [100.0-100.0] |

## Significance

McNemar (exact, two-sided) on first-attempt correctness over changed-policy tasks, `bitemporal_drift` vs `floor_static_v0`, seed 11.

| model | n01 (floor wrong, bitemporal right) | n10 | p | n tasks |
|---|---|---|---|---|
| deepseek-chat | 54 | 0 | 1.11e-16 | 180 |
| gpt-5.6-luna | 69 | 0 | 3.39e-21 | 180 |
| claude-sonnet-5 | 69 | 0 | 3.39e-21 | 180 |

Bootstrap 95% CI on changed-policy pass^1 (2000 resamples, seed 11).

| model | condition | changed-policy pass^1 | 95% CI |
|---|---|---|---|
| deepseek-chat | floor_static_v0 | 49.4 | [42.2, 56.7] |
| deepseek-chat | bitemporal_drift | 79.4 | [73.3, 85.6] |
| gpt-5.6-luna | floor_static_v0 | 45.0 | [37.8, 52.2] |
| gpt-5.6-luna | bitemporal_drift | 83.3 | [77.8, 88.9] |
| claude-sonnet-5 | floor_static_v0 | 45.0 | [37.8, 52.2] |
| claude-sonnet-5 | bitemporal_drift | 83.3 | [77.8, 88.9] |

## Ablations A1-A8 (definitions read from PREREG.md)

A2-A5 run on the primary model `deepseek-chat` at seed 11, per STEP 7.

| ablation | PREREG definition | result |
|---|---|---|
| A1 | Remove retrospective scan (`valid_from = detect_ts`) | 6 seeds; valid_time_error_traces 46.56 vs baseline 18.22 -- see the side-by-side below |
| A2 | Remove constraint mining | pass^1=80.4, changed pass^1=73.9, window_detected_doc_stale=75.0, unparseable=0 |
| A3 | Oracle timing, real mining | pass^1=95.0, changed pass^1=93.3, window_detected_doc_stale=100.0, unparseable=0 |
| A4 | Remove temporal indexing (serve most recently mined rule) | pass^1=82.5, changed pass^1=76.7, window_detected_doc_stale=75.0, unparseable=0 |
| A5_ABSENT | Provenance tag: absent | pass^1=84.6, changed pass^1=79.4, window_detected_doc_stale=75.0, unparseable=0 |
| A5_NEUTRAL | Provenance tag: neutral | pass^1=84.6, changed pass^1=79.4, window_detected_doc_stale=75.0, unparseable=0 |
| A6 | Detector sweep (ADWIN delta grid, Page-Hinkley, KSWIN, 6 data seeds) | see `runs/a6_sweep.json` |
| A7 | Changepoint buffer length 50/150/300 | see `runs/a7_sweep.json` |
| A8 | Mining strategy on numeric attributes | see `runs/a8_result.json` |

### A6 detector sweep (recall now reported alongside FPR)

| method | recall | FPR | mean delay | seeds |
|---|---|---|---|---|
| ADWIN_delta_0.002 | 0.905 | 0.083 | 61.5 | 6 |
| ADWIN_delta_0.01 | 0.976 | 0.021 | 56.4 | 6 |
| ADWIN_delta_0.05 | 0.976 | 0.021 | 47.9 | 6 |
| ADWIN_delta_0.1 | 1.000 | 0.000 | 43.4 | 6 |
| ADWIN_delta_0.15 | 1.000 | 0.000 | 41.9 | 6 |
| ADWIN_delta_0.2 | 1.000 | 0.021 | 41.9 | 6 |
| ADWIN_delta_0.3 | 1.000 | 0.042 | 37.3 | 6 |
| PageHinkley | 0.071 | 0.812 | 47.0 | 6 |
| KSWIN | 0.595 | 0.021 | 29.4 | 6 |

### A7 changepoint buffer

| buffer (traces) | mean detection delay |
|---|---|
| 50 | 20.56 |
| 150 | 18.22 |
| 300 | 20.39 |

## Actual spend

| provider | USD | calls | prompt tokens | completion tokens |
|---|---|---|---|---|
| anthropic | $12.9512 | 5432 | 4758496 | 343419 |
| deepseek | $0.9376 | 7667 | 3305723 | 28634 |
| openai | $8.3249 | 6307 | 3790493 | 358679 |
| **total** | **$22.2137** | | | |

## Provider outcomes

| provider | model | runs completed | notes |
|---|---|---|---|
| deepseek | `deepseek-chat` | 18/18 | complete (18/18) + A2-A5 ablations |
| openai | `gpt-5.6-luna` | 18/18 | complete (18/18) |
| anthropic | `claude-sonnet-5` | 17/18 | 17/18 -- `full_history_brute` seed 17 not run: the remaining Anthropic balance (~$3.03) was below the ~$5.70 that seed cost. Cheapest-first ordering means the only lost row is the cost ceiling, which is still measured on the other two models. |

## Verification (STEP 8)

`verify_runs.py` re-derives every run record from its own raw logs with `extract/rescore.py` and compares field by field.

- **58 of 58 records reproduce exactly.** No record is reported that its raw logs do not support.
- Every run is under the 2% unparseable bar. The highest are `claude-sonnet-5 full_history_brute` seed 11 (1.90%) and `plain_rag` seeds 11/17 (1.30%). Runs that exceeded 2% during the sweep were failed by `rescore.py` and re-run, not averaged in.
- The six seed-11 reference records in `runs/{condition}_s11.json` were left untouched and still reproduce from their raw logs; see `REFERENCE_RECORD_VERIFICATION.md`.

### A1 side by side (6 data seeds)

| metric | baseline | A1 collapsed |
|---|---|---|
| valid_time_error_traces | 18.22 | 46.56 |
| asof_correctness_retrospective | 1.000 | 1.000 |
| asof_correctness_predoc (corrected) | 0.817 | 0.500 |
| constraint_correctness | 1.000 | 1.000 |

**The preregistered `asof_correctness_retrospective` cannot respond to A1.** It queries `store.as_of(p, ts, 999999998)`, a transaction time after every document has landed, so the document rows supersede the mined rows and the retrospective estimate is never consulted. Measured directly: baseline and A1 differ on 0 of 24 probes at `tx=END`, and on 15 of 24 at `tx=t_doc-1`. The collapse itself is confirmed to reach the store -- every mined row satisfies `valid_from == tx_from` under A1 on all six seeds (`store_collapse_check` in `runs/a1_sweep.json`).

`asof_correctness_predoc` is the corrected diagnostic: it queries at `t_doc - 1`, where the retrospective estimate is the only thing answering. It falls from 0.817 to exactly 0.500 on every seed, because collapsing `valid_from` onto `detect_ts` makes every query between the practice change and detection return the superseded version. This is the ablation that justifies the word bi-temporal.

`runs/a1_sweep.json` is now written from a replay that redirects to `runs/a1_stage2_seed*.json` and `runs/a1_store_data*.db`. The previous version ran the ablated pipeline straight into the real Stage 2 artifacts and read them back, which is how those were destroyed.

### A8 mining strategy (6 seeds)

Exact recovery: enumeration 4/36, range search 5/36.

| seed | policy | true | enumerate | range search |
|---|---|---|---|---|
| 0 | exception_approval | `approver == 'supervisor'` | `approver == 'supervisor'` | `approver == 'supervisor'` |
| 0 | shipping_upgrade | `cart_total >= 100` | `cart_total >= 94` | `cart_total >= 93` |
| 0 | loyalty_discount | `tier == 'platinum'` | `tier == 'gold'` | `tier == 'gold'` |
| 1 | exception_approval | `approver == 'supervisor'` | `approver == 'manager'` | `approver == 'manager'` |
| 1 | shipping_upgrade | `cart_total >= 100` | `cart_total >= 103` | `cart_total >= 98` |
| 1 | loyalty_discount | `tier == 'platinum'` | `tier == 'gold'` | `tier == 'gold'` |
| 2 | exception_approval | `approver == 'supervisor'` | `approver == 'supervisor'` | `approver == 'supervisor'` |
| 2 | shipping_upgrade | `cart_total >= 100` | `cart_total >= 99` | `cart_total >= 96` |
| 2 | loyalty_discount | `tier == 'platinum'` | `tier == 'gold'` | `tier == 'gold'` |
| 3 | exception_approval | `approver == 'supervisor'` | `approver == 'supervisor'` | `approver == 'supervisor'` |
| 3 | shipping_upgrade | `cart_total >= 100` | `cart_total >= 103` | `cart_total >= 100` |
| 3 | loyalty_discount | `tier == 'platinum'` | `tier == 'gold'` | `tier == 'gold'` |
| 7 | exception_approval | `approver == 'supervisor'` | `approver == 'supervisor'` | `approver == 'supervisor'` |
| 7 | shipping_upgrade | `cart_total >= 100` | `cart_total >= 104` | `cart_total >= 87` |
| 7 | loyalty_discount | `tier == 'platinum'` | `tier == 'gold'` | `tier == 'gold'` |
| 11 | exception_approval | `approver == 'supervisor'` | `approver == 'manager'` | `approver == 'manager'` |
| 11 | shipping_upgrade | `cart_total >= 100` | `cart_total >= 101` | `cart_total >= 101` |
| 11 | loyalty_discount | `tier == 'platinum'` | `tier == 'gold'` | `tier == 'gold'` |

Only three of the six changed policies are ever mined: the other three are documented at the same tick they change (`t_doc == t_practice`), so no mining is triggered and there is no mined-vs-true gap to report. In particular `price_match_cap` is never mined here.

**PREREG's predicted exact recovery does not hold.** On `shipping_upgrade` (true `>= 100`) the absolute gap is 6/3/1/3/4/1 under enumeration (mean 3.0) and 7/2/4/0/13/1 under range search (mean 4.5). Searching the full attribute range instead of observed values recovers the threshold exactly on one more seed but is worse on average. The gap is not an artifact of enumerating observed values: the mining window spans both policy regimes, so the boundary is genuinely ambiguous in the data. `loyalty_discount` mines `gold` against a true `platinum` on all six seeds under both miners.

Adversarial band under the enumeration miner:

| seed | policy | band | gap | error rate in band | benchmark tasks in band |
|---|---|---|---|---|---|
| 0 | shipping_upgrade | [94, 100] | 6 | 0.86 | 4 |
| 1 | shipping_upgrade | [100, 103] | 3 | 0.75 | 0 |
| 2 | shipping_upgrade | [99, 100] | 1 | 0.50 | 0 |
| 3 | shipping_upgrade | [100, 103] | 3 | 0.75 | 0 |
| 7 | shipping_upgrade | [100, 104] | 4 | 0.80 | 0 |
| 11 | shipping_upgrade | [100, 101] | 1 | 0.50 | 0 |

A8 part two, agent side (deepseek/`deepseek-chat`, seed 11, shipping_upgrade). Mined `cart_total >= 101` against true `cart_total >= 100`, band [100, 101], with out-of-band controls either side.

| population | calls | wrong vs true policy | rate |
|---|---|---|---|
| in band | 8 | 4 | 0.50 |
| out of band | 32 | 0 | 0.00 |

The agent follows the mined rule on 40/40 calls, so a mis-mined threshold converts directly into wrong actions -- but only for inputs inside the band. The generated benchmark places 0 tasks in the seed-11 band, which is the entire reason the measured cost of this gap was previously zero. Quantifying it is the contribution.

### Resolved: bi-temporal store invariants

Previously 22 violations across the six seed stores (inverted valid intervals and v0/v1 valid-time overlaps). **Now 0.**

Cause and rule. `invalidate()` selected rows by `valid_to = END`, so a row whose `valid_to` had already been truncated to an *estimated* change time was invisible to the later document correction. The predecessor kept claiming validity past the documented change (the v0/v1 overlap), while the mined row was closed at the document's earlier `valid_from` and inverted. The rule now implemented and documented in `graph/bitemporal_store.py`: **a document is authoritative for valid-time placement over a mined estimate.** Selection is by transaction visibility (`tx_to = END`); a row starting before the incoming `valid_from` is truncated to it; a row starting at or after it, or a row of the same version as the incoming document, is retracted rather than left as a truncated remnant.

`store.verify_invariants()` existed but was never called anywhere. It now runs after every replay in `detect/eval_stage2.py` and fails loudly. Its overlap check is bi-temporal: valid intervals may overlap across different transaction times, and only a simultaneous overlap in valid AND transaction time is a violation. The four assertions are `valid_to >= valid_from`, `valid_from <= tx_from`, no bi-temporal overlap, and exactly one version for a policy with no change.

The fix changes `as_of` results, so Stage 2 was regenerated: `valid_time_error_traces` improved on seed 0 (27.00 -> 13.33) and `asof_correctness_online` moved slightly on seeds 0/1/11. The gated criterion `asof_correctness_postdetection` remains 1.0 with `false_invalidation_rate` 0.0 on every seed.

The agent run records are unaffected: `extract/rescore.py` derives them from raw logs, not from the store, and all 58 still reproduce. One caveat for any future re-run of a store-backed condition: the store the sweep read had `shipping_upgrade` mined at `valid_from=423` where the corrected store has 420, and exactly one benchmark task (`shipping_upgrade` at ts=420) sits in that window.

### Resolved: scorer parseability now matches correctness

`extract/rescore.py` scored correctness by substring but counted unparseable by exact match, so a verbose correct answer counted as both. Parseability now uses the same substring rule: a response is parseable when exactly one distinct valid action appears in it (zero is unreadable, two is ambiguous). All 58 records were regenerated; exactly one changed (`claude-sonnet-5 plain_rag` seed 13, unparseable 8 -> 7, pass^1 unchanged), confirming that every other unparseable response really was an empty string.

### Protected artifacts

`runs/stage1_*.json`, `runs/stage2_*.json` and `runs/store_data*.db` are now guarded by `protected_artifacts.py`. Overwriting an existing one requires `ALLOW_OVERWRITE_STAGE=1`. The check runs before any destructive work, not at the write site -- `eval_stage2.py` deletes and rebuilds the store early, so a guard at the write site still lost the store.

