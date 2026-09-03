# Reference record verification (seed 11)

**Status: all six records verified. Records are correct; the tarballs were stale.**

## What happened

An initial check rescored the six seed-11 records against the `runs/raw_*.tar.gz`
tarballs and found three mismatches: `latest_timestamp`, `plain_rag`, and
`full_history_brute`. That check was measuring the wrong artifact.

The tarballs were last written at commit `7c229e5`. The run records were
regenerated one commit later at `b96c545` ("Fix latest_timestamp tie-break and
S1/S2 reporting tables, re-run missing evaluations"). The three conditions that
disagreed are exactly the three re-run in `b96c545`. The tarballs were a commit
behind the records, so they still carried pre-tie-break-fix logs.

## Resolution

Raw logs recovered from `b96c545`:

```
git checkout b96c545 -- runs/raw/latest_timestamp_rs11 runs/raw/plain_rag_rs11 \
  runs/raw/full_history_brute_rs11 runs/raw/floor_static_v0_rs11 \
  runs/raw/bitemporal_drift_rs11 runs/raw/oracle_expiry_rs11
```

Rescored with `extract/rescore.py`, all six now reproduce their committed
records exactly:

| condition | reproduces |
|---|---|
| floor_static_v0 | yes |
| bitemporal_drift | yes |
| oracle_expiry | yes |
| latest_timestamp | yes (pass1 0.7125, doc_slice_documented 1.0) |
| plain_rag | yes |
| full_history_brute | yes |

All six tarballs have been rewritten from the `b96c545` logs so the archives
now match the records. Each contains 1000 raw JSON files.

## Note on identical `tokens_per_task`

`floor_static_v0`, `oracle_expiry` and `latest_timestamp` all report
`tokens_per_task = 360.96666666666664`. This is expected, not a copied value:
each of these three conditions serves exactly one short policy document per
task, so the prompt token counts coincide. `bitemporal_drift`, which builds a
different context, reports `367.1166666666667`.

## Standing invariant

These six records are the reference result. A replication run must never
overwrite them: model-scoped paths (`runs/{model}_{condition}_rs{seed}.json`)
are used for all replication output. When raw logs are regenerated, the
tarballs must be rewritten in the same commit, or this staleness recurs.
