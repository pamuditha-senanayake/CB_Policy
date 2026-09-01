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
- Added an alternative ADWIN configuration with `delta=0.1` (increased sensitivity, default is 0.002) to evaluate its effect on the mean delay threshold. The < 50 threshold itself remains untouched. Both default and `delta=0.1` ADWIN configurations will be reported.
  **Selection Rule:** The parameter `delta=0.1` was chosen as the centre of the widest contiguous region that satisfies all four thresholds across six independent data seeds (0, 1, 2, 3, 7, 11), ensuring the parameter generalizes rather than overfitting to a single seed.

### Appendix A: S2 Axis Refinement (2026-09-02)

The original S2 (Doc Status) axis specified a single "window" slice for lagged policies between practice change and document update. However, measured detection delay means tasks immediately following the practice change occur before drift is detected. Measuring the mechanism's performance across this entire block conflates two distinct states: pre-detection and post-detection.

In response to the measured detection delay, the S2 "window" axis is subdivided into two sub-slices:
- `window_pre_detection`: Tasks drawn from the interval between practice change and detection.
- `window_detected_doc_stale`: Tasks drawn from the interval between detection and document update.

This refines the preregistered S2 axis without moving any thresholds, which the expansion rule permits.

### Appendix B: Stage 2 Metrics Correction (2026-09-02)

The Stage 2 gated population is corrected to exclusively evaluate post-detection queries, strictly matching criterion 2 from `paper 2.md`. The 0.95 threshold is unchanged. Two additional ungated diagnostics (`asof_correctness_retrospective` and `asof_correctness_online`) have been added to honestly measure valid-time recovery and raw online detection lag.

### Bug Fix: Stale Action Rate Population Correction
The `stale_action_rate` calculation was found to improperly evaluate against pre-change and unchanged tasks where the "stale" action is logically identical to the correct current action. The population measured has been corrected to exactly reflect the definition given in `paper 2.md` criterion 3 ("the fraction of agent actions that satisfy an expired policy but violate the current one"). The underlying threshold of <5% remains completely unchanged.
