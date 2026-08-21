"""Сводная таблица полного прогона."""
import json
import os
import sys

rows = []
with open(os.environ["FACTORY_ROWS"], encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if line:
            rows.append(json.loads(line))

summary = {
    "rows": rows,
    "passed": sum(1 for r in rows if r["status"] == "PASS"),
    "failed": sum(1 for r in rows if r["status"] == "FAIL"),
    "skipped": sum(1 for r in rows if r["status"] == "SKIPPED"),
}
report = os.environ["FACTORY_REPORT"]
os.makedirs(os.path.dirname(report), exist_ok=True)
with open(report, "w", encoding="utf-8") as fh:
    json.dump(summary, fh, ensure_ascii=False, indent=2)

width = max((len(r["check"]) for r in rows), default=12) + 2
line = "=" * (width + 44)
print()
print(line)
print(f"{'ПРОВЕРКА':<{width}} {'СТАТУС':<9} {'EXIT':<6} ПРИМЕЧАНИЕ")
print(line)
for row in rows:
    print(f"{row['check']:<{width}} {row['status']:<9} {str(row['exit_code']):<6} {row['note']}")
print(line)
print(f"pass={summary['passed']}  fail={summary['failed']}  skipped={summary['skipped']}")
print(f"отчёт: {report}")
sys.exit(1 if summary["failed"] else 0)
