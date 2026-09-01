# Predictions: Expected Orderings

- On **documented** changes: `latest_timestamp ≈ oracle ≈ yours > plain_rag > floor`
- On **lagged / rollback** changes: `oracle > yours ≫ latest_timestamp ≈ plain_rag ≈ floor` (win-for-the-claimed-reason signature)
- On **unchanged** policies: all rows within 2 points of floor
- On **pre-change** tasks: all rows ≈ floor
- On **window_pre_detection** tasks: `oracle > yours ≈ latest_timestamp ≈ plain_rag ≈ floor` (only oracle knows)
- On **window_detected_doc_stale** tasks: `oracle ≈ yours ≫ latest_timestamp ≈ plain_rag ≈ floor` (bitemporal_drift should win decisively here)
