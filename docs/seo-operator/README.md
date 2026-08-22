# SEO-оператор: карта документации

Автономный SEO-редакционный контур для портфеля сайтов.

## Состояние

Контур реализован и проверен: **270 тестов**, **8 стадий верификации**.
Реальных сайтов под управлением нет, источники данных не подключены.
Всё в демонстрациях выполнено на синтетическом тенанте `fixture-*`.

**Начните с** [`blockers.md`](blockers.md) — единый список того, что нужно от владельца.

## Документы

| Документ | О чём |
| --- | --- |
| [`blockers.md`](blockers.md) | Единый список внешних блокеров |
| [`runbook.md`](runbook.md) | Как запускать и что делать при сбое |
| [`baseline.md`](baseline.md) | Baseline и почему он пока не измерен |
| [`protected-guardrails.md`](protected-guardrails.md) | Что запрещено всегда |
| [`experiment-policy.md`](experiment-policy.md) | Гипотезы, границы canary, пороги |
| [`rollback-policy.md`](rollback-policy.md) | Обратимость и защита ручных правок |
| [`automation-policy.md`](automation-policy.md) | Расписание, Routines, резервный worker |
| [`query-taxonomy.md`](query-taxonomy.md) | Классы запросов и отвечающие страницы |
| [`new-release-priority-model.md`](new-release-priority-model.md) | Приоритет новинок |
| [`per-site-editorial-strategy.md`](per-site-editorial-strategy.md) | Стратегия по каждому сайту |
| [`content-style-guide.md`](content-style-guide.md) | Редакционный стандарт и запреты |
| [`homepage-plan.md`](homepage-plan.md) | Блоки главной и их устаревание |
| [`learning-playbook.md`](learning-playbook.md) | Накопленные паттерны |

## Демонстрации

| Демонстрация | Что доказывает |
| --- | --- |
| [`demo-canary-rollback.md`](demo-canary-rollback.md) | canary → ухудшение → откат, защита ручной правки |
| [`demo-editorial-cycle.md`](demo-editorial-cycle.md) | анонс → релиз → перенос → снятие |
| [`demo-scheduled-run.md`](demo-scheduled-run.md) | запуск по расписанию, лок, повтор, восстановление |

Воспроизводятся командами:

```bash
.venv/bin/python scripts/demo_canary.py
.venv/bin/python scripts/demo_editorial.py
.venv/bin/python scripts/demo_scheduled_run.py
```

## Реестры

| Файл | Содержимое | Состояние |
| --- | --- | --- |
| `config/portfolio.json` | Сайты под управлением | пуст |
| `config/portfolio.fixture.json` | Синтетический тенант | 2 сайта |
| `config/data-sources.json` | Источники и их доступность | 0 из 6 доступны |
| `config/editorial-sources.json` | Разрешённые источники фактов | только синтетические |
| `config/editorial-calendar.json` | Календарь по сайтам | только синтетический |
| `config/content-backlog.json` | Backlog по сайтам | только синтетический |
| `config/experiments.json` | Эксперименты и вердикты | 1 демонстрационный |

## Отчёты

`reports/` — ежедневные и недельные отчёты. Формируются командами
`./bin/seo-operator report` и `./bin/seo-operator weekly`.

## Доказательства

`evidence/demo-canary-audit.jsonl` — audit log демонстрации canary: два
применения и два отката с before/after и rollback payload.
