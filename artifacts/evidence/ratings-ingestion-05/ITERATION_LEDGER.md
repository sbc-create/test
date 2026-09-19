# Iteration ledger — Stage 5

| block | iter | result | notes |
| --- | --- | --- | --- |
| 00 | 1 | PASS | denominators |
| 01 | 1 | PASS | shikimori only |
| 02 | 1 | PASS | 150 queue |
| 03 | 1 | PASS | exact only |
| 04 | 1 | PASS | no qwen config |
| 05 | 1 | PASS | backup ok |
| 06 | 1 | NEEDS_REPAIR | claim limit used 150; inserted 125>100 |
| 06 | 2 | CODE_FIX | claim limit=ACCEPTED_TARGET; no re-run |
| 07 | 1 | PASS | integrity ok |
| 08 | 1 | PASS | gateway 25 |
| 09 | 1 | PASS | isolated fixtures |
| 10 | 1 | PASS | ETA ~70d @100 |
| 11 | 1 | PASS | outbox + dry-run |
| 12 | 1 | PASS | timer off |
| 13 | 1 | PASS | 31d sim |
