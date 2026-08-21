"""Проверяет артефакт браузерной приёмки последнего задания.

Шаг «браузерная проверка пройдена» доказывается артефактом, а не памятью о том,
что она когда-то запускалась.
"""
import json
import pathlib
import sys

sys.path.insert(0, ".")
from factory.paths import PATHS  # noqa: E402

jobs = list((PATHS.artifacts / "jobs" / "pilot-local").glob("*.json"))
if not jobs:
    print("нет результатов заданий пилота", file=sys.stderr)
    raise SystemExit(1)
latest = max(jobs, key=lambda p: json.loads(p.read_text(encoding="utf-8")).get("finished_at", ""))
data = json.loads(latest.read_text(encoding="utf-8"))
check = next((c for c in data["checks"] if c["id"] == "seo-render"), None)
if check is None:
    print("в последнем задании нет проверки seo-render", file=sys.stderr)
    raise SystemExit(1)
artifact = PATHS.root / check["artifact"]
if not artifact.exists():
    print(f"артефакт {artifact} отсутствует", file=sys.stderr)
    raise SystemExit(1)
report = json.loads(artifact.read_text(encoding="utf-8"))
if not check["passed"] or not report.get("passed"):
    print(f"браузерная проверка не пройдена: {report.get('totals')}", file=sys.stderr)
    raise SystemExit(1)
print(f"browser-audit OK: {report['counts'].get('pages')} страниц, "
      f"{report['counts'].get('screenshots')} скриншотов, "
      f"lab LCP max {report['counts'].get('lab_lcp_ms_max')} мс, "
      f"CLS max {report['counts'].get('lab_cls_max')}")
