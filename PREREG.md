# Phase 1 Preregistration

## Claim v1
A bi-temporal policy graph, invalidated by a conformance-fitness drift signal, raises current-policy pass^1 by **at least 15 absolute points** over a static-policy agent on tasks affected by mid-stream policy changes, and cuts stale-policy action rate to **under 5 percent** (gain), at a per-task token cost of **no more than 1.6× the static agent and no more than 40 percent of the full-history brute-force ceiling** (cost), while pass^1 on unchanged policies degrades by **no more than 2 points** and false invalidations stay **under 10 percent** (guards).

## Outcomes
| Outcome | Definition |
|---|---|
| **WIN** | All four stages pass: detection (recall ≥ 0.90, mean delay < 50 traces, FPR < 0.10); invalidation (as-of-now correctness ≥ 0.95); agent gain (Δpass^1 ≥ +15 on changed-policy tasks AND stale-action rate < 5%); guard (unchanged-policy Δpass^1 ≥ −2, false-invalidation < 10%) |
| **PARTIAL** | Stages 1–2 pass; agent gain lands in **+5 to +15**, OR gain ≥ +15 only within a preregistered slice |
| **FAIL** | Stage 1 or 2 misses threshold after instrument check, OR gain < +5, OR any guard breaks |

## Slice Axes
- **S1 change-documentation status:** documented / lagged-documentation / rollback
- **S2 task position:** pre-change / inside detection window / post-detection
- **S3 policy status:** changed / unchanged

## Delete Pass
- pass^8 everywhere → deleted; pass^4 kept only where the reliability-cliff claim is used (floor, yours).
- Multi-seed on deterministic-retrieval rows → reduced to 2 seeds (LLM sampling still varies); floor and yours keep 3.
- Airline domain → NOT in v1. It is the confirmation dataset for the WIN branch only.

## Budget Mode
240 tasks primary mode selected.


## Appendix: Amendments
### 2026-09-01
- Added an alternative ADWIN configuration with `delta=0.05` (increased sensitivity, default is 0.002) to evaluate its effect on the mean delay threshold. The < 50 threshold itself remains untouched. Both default and `delta=0.05` ADWIN configurations will be reported.
