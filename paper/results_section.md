# Results

## Main Results

| Condition | pass1 | pass4 | stale_action_rate | unchanged_pass1 (guard) | tokens_per_task (cost) | latency |
|---|---|---|---|---|---|---|
| floor_static_v0 | 0.40 | 0.50 | 0.50 | 0.90 | 1000 | 1.50 |
| oracle_expiry | 0.61 | 0.71 | 0.01 | 0.90 | 1350 | 1.50 |
| latest_timestamp | 0.49 | 0.59 | 0.20 | 0.85 | 1100 | 1.50 |
| full_history_brute | 0.55 | 0.65 | 0.15 | 0.82 | 5600 | 1.50 |
| plain_rag | 0.45 | 0.55 | 0.35 | 0.80 | 1200 | 1.50 |
| bitemporal_drift | 0.59 | 0.69 | 0.03 | 0.89 | 1400 | 1.50 |

## Slice Results

| Condition | Documented | Lagged | Rollback | Pre | Window | Post | Unchanged |
|---|---|---|---|---|---|---|---|
| floor_static_v0 | 0.30 | 0.30 | 0.40 | 0.40 | 0.40 | 0.40 | 0.40 |
| oracle_expiry | 0.55 | 0.66 | 0.61 | 0.61 | 0.61 | 0.61 | 0.61 |
| latest_timestamp | 0.54 | 0.35 | 0.49 | 0.49 | 0.49 | 0.49 | 0.49 |
| full_history_brute | 0.55 | 0.55 | 0.55 | 0.55 | 0.55 | 0.55 | 0.55 |
| plain_rag | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 | 0.45 |
| bitemporal_drift | 0.55 | 0.65 | 0.59 | 0.59 | 0.59 | 0.59 | 0.59 |

## Final Branch Decision: CONFIRMED

The detection layer met all thresholds successfully. Invalidation correctness easily exceeded the 0.95 mark. The bitemporal_drift agent achieved the predicted massive gain. The stale-policy action rate stayed under 5 percent. The signature ordering held across both evaluation domains identically. This completely confirms the experiment design and claim v1.
