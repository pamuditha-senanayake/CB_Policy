# Fake Paper: Results Section (Kill Test)

We evaluated the bi-temporal policy graph on the retail domain benchmark. Our detection layer achieved a recall of 94% on mid-stream policy changes, with a mean delay of 30 traces. Invalidation correctness was perfect. The bi-temporal agent raised current-policy pass^1 by 19 absolute points over the static baseline on changed-policy tasks. Concurrently, the stale-policy action rate dropped to 3%.

Guards remained intact: pass^1 on unchanged policies degraded by only 1 point, and false invalidations remained well under 10%. Cost metrics were within limits, using 1.4× the tokens of the static agent and only 25% of the full-history brute-force ceiling.

This confirms the capability of bi-temporal graph structures to resolve operational policy staleness using fitness drift.
