# Predictions: Expected Orderings

- On **documented** changes: `latest_timestamp ≈ oracle ≈ yours > plain_rag > floor`
- On **lagged / rollback** changes: `oracle > yours ≫ latest_timestamp ≈ plain_rag ≈ floor` (win-for-the-claimed-reason signature)
- On **unchanged** policies: all rows within 2 points of floor
- On **pre-change** tasks: all rows ≈ floor
