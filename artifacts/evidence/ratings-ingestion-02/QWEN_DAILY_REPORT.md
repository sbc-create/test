# Qwen daily report contract

Schema: `ratings_daily_v1`  
Builder: `factory/ratings/daily.py`  
Paths:

```text
reports/ratings/daily/YYYY-MM-DD/REPORT.md
reports/ratings/daily/YYYY-MM-DD/report.json
reports/ratings/daily/YYYY-MM-DD/outcomes.csv
reports/ratings/daily/YYYY-MM-DD/not-added.csv
reports/ratings/daily/YYYY-MM-DD/quality-sample.csv
reports/ratings/daily/YYYY-MM-DD/QWEN_MESSAGE.txt
reports/ratings/daily/latest.json
```

## Delivery

No approved external Qwen report-delivery endpoint/credentials found in repo
(control-plane mentions Qwen API access restrictions only).

```text
REPORT_READY_FOR_QWEN=YES
QWEN_DELIVERY=NOT_CONFIGURED
```

`QwenDelivery` interface supports dry-run only on Stage 2. Never claims DELIVERED
without confirmation.
