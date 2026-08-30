"""Собирает курируемый набор доказательств последнего чистого прогона.

Запускается после `bash tests/run-all.sh`: в git попадает не весь runtime-вывод,
а фиксированный набор файлов, по которым можно проверить заявленные результаты.
"""
import json
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

# Каталог больше не стирается целиком.
#
# Раньше здесь стоял `rmtree`, и обычный прогон удалял восемь файлов
# `multisite-*.json`: их производит другой набор, при этом прогоне источник
# отсутствует, и копировать было нечего. Так исчезало доказательство
# состоявшейся проверки из-за того, что НЕ запускалась другая. Репозиторий
# запрещает отчёт о непроведённой проверке; молчаливое исчезновение
# доказательства проведённой — ошибка того же рода в обратную сторону.
#
# Файл, оставшийся от прошлого прогона, попадает в манифест как перенесённый:
# устаревшее доказательство, о котором известно, что оно устаревшее, честнее и
# удалённого, и выданного за свежее.
evidence.mkdir(parents=True, exist_ok=True)
existing_before = {p.name for p in evidence.iterdir() if p.is_file()}
refreshed: list[str] = []


def put(src, name):
    """Копирует файл и отмечает его обновлённым в этом прогоне."""
    shutil.copy(src, evidence / name)
    refreshed.append(name)

put(latest, "job-result.json")
for src, name in (
    (PATHS.artifacts / "qa" / "run-all.json", "run-all.json"),
    (PATHS.artifacts / "env" / "env-report.json", "env-report.json"),
    (PATHS.artifacts / "input-request" / "input-request.json", "input-request.json"),
    (PATHS.artifacts / "qa" / SITE / "screenshots.md", "screenshots.md"),
):
    if src.exists():
        put(src, name)

qa_dir = PATHS.artifacts / "qa" / SITE / job["job_id"]
for name in ("seo-lint.json", "seo-crawl.json", "seo-render.json", "security-smoke.json",
             "acceptance-routes.json", "performance-budget.json", "major-findings-budget.json",
             "browser-audit.json"):
    if (qa_dir / name).exists():
        put(qa_dir / name, name)

seo_dir = PATHS.artifacts / "seo" / SITE / job["job_id"]
for name in ("seo-report.json", "seo-report.md"):
    if (seo_dir / name).exists():
        put(seo_dir / name, name)

# Доказательства второго blueprint лежат в var/artifacts: собираются тем же
# прогоном, но другими инструментами. Без них отчёт по payload-next-multisite
# опирался бы на слова, а не на файлы.
multisite = PATHS.var / "artifacts"
for name in ("restore-proof.json", "cross-site-uniqueness.json", "mutation-isolation.json",
             "secret-scan.json", "admin-smoke.json", "frontend-http.json",
             "performance-lab.json", "playwright-multisite.json"):
    src = multisite / name
    if src.exists():
        put(src, f"multisite-{name}")

playwright = PATHS.artifacts / "qa" / SITE / "playwright-report.json"
if playwright.exists():
    data = json.loads(playwright.read_text(encoding="utf-8"))
    (evidence / "playwright-summary.json").write_text(json.dumps({
        "stats": data.get("stats", {}),
        "projects": sorted({s.get("title", "") for s in data.get("suites", [])}),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    refreshed.append("playwright-summary.json")

carried_over = sorted(existing_before - set(refreshed) - {"README.md", "MANIFEST.json"})
(evidence / "MANIFEST.json").write_text(json.dumps({
    "job_id": job["job_id"],
    "job_status": job["status"],
    "refreshed": sorted(set(refreshed)),
    "carried_over": carried_over,
    "note": "carried_over — доказательства прошлых прогонов: их источник в этот раз "
            "не производился. Они не удаляются, но и свежими не считаются.",
}, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"evidence обновлён: {len(set(refreshed))} файлов из задания {job['job_id']} "
      f"({job['status']}), перенесено из прошлых прогонов: {len(carried_over)}")
