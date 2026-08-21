"""Собирает курируемый набор доказательств последнего чистого прогона.

Запускается после `bash tests/run-all.sh`: в git попадает не весь runtime-вывод,
а фиксированный набор файлов, по которым можно проверить заявленные результаты.
"""
import json
import pathlib
import shutil
import sys

sys.path.insert(0, ".")
from factory.paths import PATHS  # noqa: E402

SITE = sys.argv[1] if len(sys.argv) > 1 else "pilot-local"
evidence = PATHS.artifacts / "evidence"

jobs = list((PATHS.artifacts / "jobs" / SITE).glob("*.json"))
if not jobs:
    print(f"нет результатов заданий для {SITE}", file=sys.stderr)
    raise SystemExit(1)
latest = max(jobs, key=lambda p: json.loads(p.read_text(encoding="utf-8")).get("finished_at", ""))
job = json.loads(latest.read_text(encoding="utf-8"))

readme = (evidence / "README.md").read_text(encoding="utf-8") if (evidence / "README.md").exists() else ""
shutil.rmtree(evidence, ignore_errors=True)
evidence.mkdir(parents=True)
if readme:
    (evidence / "README.md").write_text(readme, encoding="utf-8")

shutil.copy(latest, evidence / "job-result.json")
for src, name in (
    (PATHS.artifacts / "qa" / "run-all.json", "run-all.json"),
    (PATHS.artifacts / "env" / "env-report.json", "env-report.json"),
    (PATHS.artifacts / "input-request" / "input-request.json", "input-request.json"),
    (PATHS.artifacts / "qa" / SITE / "screenshots.md", "screenshots.md"),
):
    if src.exists():
        shutil.copy(src, evidence / name)

qa_dir = PATHS.artifacts / "qa" / SITE / job["job_id"]
for name in ("seo-lint.json", "seo-crawl.json", "seo-render.json", "security-smoke.json",
             "acceptance-routes.json", "performance-budget.json", "major-findings-budget.json",
             "browser-audit.json"):
    if (qa_dir / name).exists():
        shutil.copy(qa_dir / name, evidence / name)

seo_dir = PATHS.artifacts / "seo" / SITE / job["job_id"]
for name in ("seo-report.json", "seo-report.md"):
    if (seo_dir / name).exists():
        shutil.copy(seo_dir / name, evidence / name)

playwright = PATHS.artifacts / "qa" / SITE / "playwright-report.json"
if playwright.exists():
    data = json.loads(playwright.read_text(encoding="utf-8"))
    (evidence / "playwright-summary.json").write_text(json.dumps({
        "stats": data.get("stats", {}),
        "projects": sorted({s.get("title", "") for s in data.get("suites", [])}),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"evidence обновлён: {len(list(evidence.iterdir()))} файлов из задания {job['job_id']} ({job['status']})")
