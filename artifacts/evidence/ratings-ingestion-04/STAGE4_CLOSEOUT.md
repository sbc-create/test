# Stage 4 closeout

Use:

```bash
python -m factory.ratings.stage4_closeout --cycles artifacts/evidence/ratings-ingestion-04/PILOT_CYCLES.json
```

Does **not** run ingestion. After 7 cycles recorded, evaluates shortfalls, duplicates, Qwen receipts, and disables any pilot timer recommendation.
