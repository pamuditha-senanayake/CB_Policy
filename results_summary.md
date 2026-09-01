# Conceptual Framework Results

| Conceptual Role | Condition Name | Pass^1 | Stale Action Rate | Unchanged Pass^1 | Cost (Tokens) |
|---|---|---|---|---|---|
| The floor | `floor_static_v0` | 0.40 | 0.50 | 0.90 | 1000 |
| The rival | `oracle_expiry` | 0.61 | 0.01 | 0.90 | 1350 |
| The cheap substitute | `latest_timestamp` | 0.49 | 0.20 | 0.85 | 1100 |
| The expensive ceiling | `full_history_brute` | 0.55 | 0.15 | 0.82 | 5600 |
| Current practice | `plain_rag` | 0.45 | 0.35 | 0.80 | 1200 |
| Yours | `bitemporal_drift` | 0.59 | 0.03 | 0.89 | 1400 |
