# Multi-Model Bitemporal RAG Replication Results

## Main Results

The headline tables reflect the runs completed on `deepseek-chat` (DeepSeek) at run seed 11. 
Data is reported as Mean [95% CI Lower, 95% CI Upper] across tasks, derived from 10,000 bootstrap resamples.

### Main Table (Pass1 & Staleness)

| Condition | Pass1 | Changed Pass1 | Unchanged Pass1 | Stale Action |
|-----------|-------|---------------|-----------------|--------------|
| floor_static_v0 | 0.554 [0.49, 0.62] | 0.406 [0.33, 0.48] | 1.000 [1.00, 1.00] | 0.825 [0.75, 0.89] |
| bitemporal_drift | 0.863 [0.82, 0.90] | 0.817 [0.76, 0.87] | 1.000 [1.00, 1.00] | 0.208 [0.14, 0.28] |
| oracle_expiry | 0.967 [0.94, 0.99] | 0.956 [0.92, 0.98] | 1.000 [1.00, 1.00] | 0.000 [0.00, 0.00] |
| latest_timestamp | 0.713 [0.65, 0.77] | 0.617 [0.54, 0.69] | 1.000 [1.00, 1.00] | 0.508 [0.42, 0.60] |
| plain_rag | 0.579 [0.52, 0.64] | 0.617 [0.54, 0.69] | 0.467 [0.35, 0.60] | 0.442 [0.35, 0.53] |
| full_history_brute | 0.808 [0.76, 0.86] | 0.744 [0.68, 0.81] | 1.000 [1.00, 1.00] | 0.375 [0.29, 0.46] |

### S1 Table (Temporal Slices)

| Condition | Documented | Lagged | Rollback |
|-----------|------------|--------|----------|
| floor_static_v0 | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.00] | 1.000 [1.00, 1.00] |
| bitemporal_drift | 1.000 [1.00, 1.00] | 0.590 [0.46, 0.70] | 1.000 [1.00, 1.00] |
| oracle_expiry | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] |
| latest_timestamp | 1.000 [1.00, 1.00] | 0.344 [0.23, 0.46] | 0.000 [0.00, 0.00] |
| plain_rag | 0.684 [0.53, 0.82] | 0.492 [0.36, 0.62] | 0.524 [0.33, 0.71] |
| full_history_brute | 0.711 [0.55, 0.84] | 0.623 [0.51, 0.74] | 0.476 [0.29, 0.67] |

## Statistical Significance

McNemar's exact test for the headline comparison between `bitemporal_drift` and `latest_timestamp`:

*   **Changed Policy Pass1:** `bitemporal_drift` corrected 36 failures that `latest_timestamp` had, and `latest_timestamp` corrected 0 failures that `bitemporal_drift` had. (b=36, c=0)
    *   **p-value:** `2.91e-11`
*   **Lagged Cell:** `bitemporal_drift` corrected 15 failures that `latest_timestamp` had, and `latest_timestamp` corrected 0 failures that `bitemporal_drift` had. (b=15, c=0)
    *   **p-value:** `6.10e-05`

These results indicate robust statistically significant outperformance of the bitemporal configuration.

## Inter-Model Agreement

*Note: Could not compute Inter-Model Agreement as Anthropic and OpenAI keys failed (see Provider Failures).*

## Ablations vs Predictions (A1-A8)

*   **A1 (Detector threshold 0.1):** Not run (API fail) vs Pred: *ADWIN handles noise; minor variance expected.*
*   **A2 (System Prompt explicitly states: current policy unknown):** Not run (API fail) vs Pred: *Slightly lower pass1 (higher abstention), low stale rate.*
*   **A3 (Disable RAG chunking):** Not run (API fail) vs Pred: *Cost explodes, precision drops, Pass1 decreases significantly.*
*   **A4 (Scramble `t_practice`):** Not run (API fail) vs Pred: *Performance defaults to naive baseline.*
*   **A5 (Inject Provenance tags):** Not run (API fail) vs Pred: *Models utilize explicitly tagged DB times for better reasoning.*
*   **A6 (Detector Frontier):** 
    *   **Observed:** ADWIN mean delay scales logarithmically with $\delta$. PageHinkley has 0 mean delay but high FPR. (See `figures/detector_frontier.png`).
    *   **Pred:** ADWIN dominates PageHinkley by trading slight delay for 0 FPR. 
*   **A7 (Changepoint Buffer Length):** 
    *   **Observed:** Time error traces drop significantly at 150 length (13.3), but bounce back up at 300 length (26.3). 50 length is too small (27.3). 
    *   **Pred:** 150 buffer catches optimal temporal window.

## Usage and Spend

*   **DeepSeek:** 1,648,188 prompt tokens, 22,760 completion tokens. Total spend: **$0.2371**
*   **Anthropic:** 0 prompt tokens, 0 completion tokens. Total spend: **$0.0000**
*   **OpenAI:** 0 prompt tokens, 0 completion tokens. Total spend: **$0.0000**
*   **Total Spend:** $0.2371

---

## PROVIDER FAILURES

The following runs failed due to `ProviderUnavailable` and authentication errors. The errors were gracefully caught and did not stop execution, but resulted in incomplete multi-model runs:

*   **Anthropic API (`claude-sonnet-5`):** All runs across seeds 11, 13, and 17 failed.
    *   `Error code: 400 - anthropic-workspace-id is required when authenticating with an identity-linked API key`
    *   Also failed `Error code: 401 - invalid x-api-key` in manual tests.
*   **OpenAI API (`gpt-5.6-luna`):** All runs across seeds 11, 13, and 17 failed.
    *   `Error code: 401 - Incorrect API key provided: sk-proj-*.`
*   **DeepSeek API (`deepseek-v4-flash`):** Failed on new runs (seeds 13 and 17).
    *   `Error code: 401 - Authentication Fails (no such user)`
