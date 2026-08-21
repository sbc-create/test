# artifacts/evidence

Доказательства последнего чистого прогона, зафиксированные в git. Всё остальное
содержимое `artifacts/` — runtime-вывод: оно накапливается по каждому заданию и в
репозиторий не коммитится (см. `.gitignore`).

| Файл | Что доказывает |
|---|---|
| `run-all.json` | полный прогон всех уровней проверок: команда, статус, exit code |
| `job-result.json` | результат пилотного задания по `schemas/job-result.schema.json` |
| `seo-lint.json`, `seo-crawl.json`, `seo-render.json` | SEO-ворота: статический линт, обход по HTTP, браузерная проверка |
| `security-smoke.json` | закрытость служебных путей, заголовки, авторизация staging |
| `acceptance-routes.json` | маршруты приёмки из пакета сайта |
| `performance-budget.json` | лабораторные бюджеты (не полевые Core Web Vitals) |
| `major-findings-budget.json` | бюджет замечаний уровня major |
| `browser-audit.json` | сырой вывод браузерной приёмки: метрики, a11y, скриншоты |
| `playwright-summary.json` | сводка E2E и accessibility-прогона |
| `seo-report.json/.md` | сводный SEO-отчёт задания |
| `env-report.json` | что доступно на управляющем хосте |
| `input-request.json` | недостающие входные данные одним пакетом |
| `screenshots.md` | индекс скриншотов с размерами и SHA-256 |

Набор обновляется командой `python3 tests/tools/collect_evidence.py` (её вызывает
`tests/run-all.sh` в конце прогона), а не вручную.
