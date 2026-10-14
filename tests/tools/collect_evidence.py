"""Собирает курируемый набор доказательств последнего чистого прогона.

Запускается после `bash tests/run-all.sh`: в git попадает не весь runtime-вывод,
а фиксированный набор файлов, по которым можно проверить заявленные результаты.

Два правила, и оба появились из измеренных потерь
-------------------------------------------------

1. **Сборщик трогает только СВОИ файлы.** Прежняя редакция удаляла
   `artifacts/evidence` целиком (`shutil.rmtree`), оставляя `README.md`, и
   вместе со своими копиями уносила ЧУЖИЕ наборы, лежащие в git:
   `arch-player-content-010/`, `lords-template-1.1.0/`, `portable-site-cell/`,
   `playback/`, `new-sites/` — 57 файлов, измерено 2026-10-14 по `git status`
   после полного прогона. Инструмент, который ведёт набор доказательств, сам
   его и стирал, а следующий коммит зафиксировал бы пропажу как намеренную.

2. **Своя копия удаляется только тогда, когда её есть чем заменить.** Вторая
   редакция чистила весь свой список и этим удаляла доказательства, которые на
   этом хосте воспроизвести НЕЧЕМ: шаг `payload-blueprint` здесь пропускается
   (нет зависимостей приложения), и восемь файлов `multisite-*` исчезли из
   набора — измерено в том же прогоне. Поэтому файл, для которого источник
   отсутствует, остаётся как есть: он документирует прогон на машине, которая
   этот шаг выполняет. Какие шаги шли в ЭТОМ прогоне, видно из `run-all.json`,
   где у каждого стоит статус и exit code.
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

qa_dir = PATHS.artifacts / "qa" / SITE / job["job_id"]
seo_dir = PATHS.artifacts / "seo" / SITE / job["job_id"]
multisite = PATHS.var / "artifacts"

#: Что сборщик считает своим: имя в наборе → откуда берётся. Всё, чего в этой
#: таблице нет, принадлежит другим работам и не трогается.
СВОИ: list[tuple[str, object]] = [
    ("job-result.json", latest),
    ("run-all.json", PATHS.artifacts / "qa" / "run-all.json"),
    ("env-report.json", PATHS.artifacts / "env" / "env-report.json"),
    ("input-request.json", PATHS.artifacts / "input-request" / "input-request.json"),
    ("screenshots.md", PATHS.artifacts / "qa" / SITE / "screenshots.md"),
]
for имя in ("seo-lint.json", "seo-crawl.json", "seo-render.json", "security-smoke.json",
            "acceptance-routes.json", "performance-budget.json",
            "major-findings-budget.json", "browser-audit.json"):
    СВОИ.append((имя, qa_dir / имя))
for имя in ("seo-report.json", "seo-report.md"):
    СВОИ.append((имя, seo_dir / имя))
# Доказательства второго blueprint: собираются тем же прогоном, но другими
# инструментами, и на хосте без зависимостей приложения не собираются вовсе.
for имя in ("restore-proof.json", "cross-site-uniqueness.json", "mutation-isolation.json",
            "secret-scan.json", "admin-smoke.json", "frontend-http.json",
            "performance-lab.json", "playwright-multisite.json"):
    СВОИ.append((f"multisite-{имя}", multisite / имя))

evidence.mkdir(parents=True, exist_ok=True)
обновлено: list[str] = []
сохранено: list[str] = []
for имя, источник in СВОИ:
    цель = evidence / имя
    if источник.exists():
        shutil.copy(источник, цель)
        обновлено.append(имя)
    elif цель.exists():
        # Заменить нечем. Удалить значило бы потерять доказательство, которое
        # этот хост воспроизвести не может.
        сохранено.append(имя)

playwright = PATHS.artifacts / "qa" / SITE / "playwright-report.json"
if playwright.exists():
    data = json.loads(playwright.read_text(encoding="utf-8"))
    (evidence / "playwright-summary.json").write_text(json.dumps({
        "stats": data.get("stats", {}),
        "projects": sorted({s.get("title", "") for s in data.get("suites", [])}),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    обновлено.append("playwright-summary.json")
elif (evidence / "playwright-summary.json").exists():
    сохранено.append("playwright-summary.json")

print(f"evidence обновлён: {len(обновлено)} файлов из задания {job['job_id']} "
      f"({job['status']}); сохранено без замены: {len(сохранено)}"
      + (f" ({', '.join(сохранено)})" if сохранено else "")
      + "; чужие наборы в каталоге не тронуты")
