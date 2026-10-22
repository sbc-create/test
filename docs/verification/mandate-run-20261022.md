[//]: # (Сквозной прогон приёмки задания: девять команд с фактическими кодами возврата. Файл собран автоматически, вывод не редактировался.)

# Сквозной прогон приёмки, 22 октября 2026

Собрано 2026-10-22T10:13:17Z из рабочей копии `wt-nova-publish-memory-02`, ветка `claude/nova-publish-memory-02`.

Каждая команда запущена подряд, в один проход. **Код возврата — фактический**, вывод не редактировался. Ожидание указано рядом: код, отличный от нуля, здесь не всегда ошибка — у трёх команд он и есть способ сообщить находку.

| команда | код | ожидание |
| --- | --- | --- |
| `python3 automation/local/cycle-coverage.py` | **1** | 1 — восемь витрин K2 вне цикла (MOD-137, решение владельца) |
| `python3 automation/local/brief.py --list` | **0** | 0 — 25 домéнов, у каждого этап и число задач |
| `python3 automation/local/pick-work.py` | **0** | 0 — есть доступная задача |
| `python3 automation/local/first-cycle.py` | **0** | 0 — изменений состояния 0 |
| `python3 automation/local/record-isolation.py` | **1** | 1 — одна аномалия (отсоединённый HEAD у zonafilm.cc) |
| `python3 automation/local/owner-report.py --status` | **0** | 0 — расписание, пояс, ближайшая отправка |
| `python3 automation/local/owner-report.py --slot 10:00` | **4** | 4 — слот уже обработан, отчёт не собран |
| `python3 scripts/validate_registries.py` | **0** | 0 — каждый реестр сопоставлен схеме и прошёл её |
| `python3 -m factory knowledge verify` | **0** | 0 — freeze и целостность |

## охват цикла по активным доменам

```
$ python3 automation/local/cycle-coverage.py
охват регулярного цикла: ВНЕ ЦИКЛА
   цикл живёт в wt-portable-site-cell-01, прогон daily-2026-10-22 (2026-10-22T05:45:14Z)
   активных домéнов 25, цикл объявил 21, проверил 21 (источник: check.json (переиспользованная проверка))
   ВНЕ ЦИКЛА (8): lordfilm.group, lordfilm.msk.ru, lordfilm.spb.ru, lordserial.group, lordserial.msk.ru, lordserial.net.ru, lordserial.spb.ru, lordserial.su
   цикл проверяет домены вне активного списка: lordfilm077.site, lordserial101.site, lordserials22.site, lordserials22.space
      семья k2: 8 вне работы
   «таймеры включены» охватом НЕ является: цикл читает реестр ТОЙ копии, в которой работает
(код возврата: 1)
```

## инструктаж: кто активен и на каком этапе

```
$ python3 automation/local/brief.py --list
yummyani.site            yummy     этап 1 задач  9 
yummyani.org             yummy     этап 1 задач  7 
yummyani.biz             yummy     этап 1 задач  9 
yummyani7.site           yummy     этап 1 задач  7 
yummyani7.info           yummy     этап 1 задач  7 
animedia.icu             animedia  этап 2 задач  2 
animedia.space           animedia  этап 2 задач  4 
animeg0.site             animego   этап 2 задач  3 
an1meg0.site             animego   этап 1 задач  3 
an1mego.site             animego   этап 1 задач  3 
lordserials22.info       lords     этап 2 задач  3 
1lordserials1.online     lords     этап 1 задач  3 
lordfilm47.space         lords     этап 2 задач  3 
lordserial33.biz         lords     этап 2 задач  2 
zonafilm12.site          zona      этап 2 задач  2 
zonafilm.space           zona      этап 2 задач  3 
zonafilm.cc              zona      этап 2 задач  4 
lordfilm.group           k2        этап 1 задач  3 
lordfilm.spb.ru          k2        этап 1 задач  3 
lordfilm.msk.ru          k2        этап 1 задач  3 
lordserial.su            k2        этап 1 задач  3 
lordserial.group         k2        этап 1 задач  3 
lordserial.spb.ru        k2        этап 1 задач  3 
lordserial.msk.ru        k2        этап 1 задач  3 
lordserial.net.ru        k2        этап 1 задач  3 

активных домéнов: 25
(код возврата: 0)
```

## выбор работы по порядку правил сети

```
$ python3 automation/local/pick-work.py
что делать: ЗАДАЧА ДОМЕНА
   {"домен": "1lordserials1.online", "задача": "Q-1lordserials1.online-001", "название": "Карта сайта 1lordserials1.online не обновлялась с 2026-10-15, пока каталог рос", "срочность": "P0", "состояние": "подготовлено"}
   почему: самая срочная доступная задача по порядку из правил сети, §6
   домéнов 25, доступных задач 85, ждущих 9, учебных в очереди 4
(код возврата: 0)
```

## первый цикл повторно: идемпотентность

```
$ python3 automation/local/first-cycle.py
1lordserials1.online     состояния не менялись
                         шаг: Q-1lordserials1.online-001: Карта сайта 1lordserials1.online не обновлял
an1meg0.site             состояния не менялись
                         шаг: Q-an1meg0.site-001: an1meg0.site и an1mego.site отдают дословно одну и т
an1mego.site             состояния не менялись
                         шаг: Q-an1mego.site-001: an1meg0.site и an1mego.site отдают дословно одну и т
animedia.icu             состояния не менялись
                         шаг: Q-animedia.icu-001: снять спрос и конкурентов по домену
animedia.space           состояния не менялись
                         шаг: Q-animedia.space-002: снять спрос и конкурентов по домену
animeg0.site             состояния не менялись
                         шаг: Q-animeg0.site-001: снять спрос и конкурентов по домену
lordfilm.group           состояния не менялись
                         шаг: Q-lordfilm.group-001: доставка каталога на узел K2 отказывает каждые сут
lordfilm.msk.ru          состояния не менялись
                         шаг: Q-lordfilm.msk.ru-001: доставка каталога на узел K2 отказывает каждые су
lordfilm.spb.ru          состояния не менялись
                         шаг: Q-lordfilm.spb.ru-001: доставка каталога на узел K2 отказывает каждые су
lordfilm47.space         состояния не менялись
                         шаг: Q-lordfilm47.space-001: снять спрос и конкурентов по домену
lordserial.group         состояния не менялись
                         шаг: Q-lordserial.group-001: доставка каталога на узел K2 отказывает каждые с
lordserial.msk.ru        состояния не менялись
                         шаг: Q-lordserial.msk.ru-001: доставка каталога на узел K2 отказывает каждые 
lordserial.net.ru        состояния не менялись
                         шаг: Q-lordserial.net.ru-001: доставка каталога на узел K2 отказывает каждые 
lordserial.spb.ru        состояния не менялись
                         шаг: Q-lordserial.spb.ru-001: доставка каталога на узел K2 отказывает каждые 
lordserial.su            состояния не менялись
                         шаг: Q-lordserial.su-001: доставка каталога на узел K2 отказывает каждые сутк
lordserial33.biz         состояния не менялись
                         шаг: Q-lordserial33.biz-001: снять спрос и конкурентов по домену
lordserials22.info       состояния не менялись
                         шаг: Q-lordserials22.info-001: снять спрос и конкурентов по домену
yummyani.biz             состояния не менялись
                         шаг: Q-yummyani.biz-001: Просмотр каталога на всех пяти витринах
(код возврата: 0)
```

## изоляция: своя копия и своя ветка

```
$ python3 automation/local/record-isolation.py
yummyani.site            claude/extract-yummyani-site-perf-02         своя копия и своя ветка
yummyani.org             claude/extract-yummyani-org                  своя копия и своя ветка
yummyani.biz             claude/extract-yummyani-biz                  своя копия и своя ветка
yummyani7.site           claude/extract-yummyani7-site                своя копия и своя ветка
yummyani7.info           claude/extract-yummyani7-info                своя копия и своя ветка
animedia.icu             claude/extract-animedia-icu-seo-01           своя копия и своя ветка
animedia.space           claude/extract-animedia-space-seo-01         своя копия и своя ветка
animeg0.site             claude/extract-animeg0-seo-01                своя копия и своя ветка
an1meg0.site             claude/extract-an1meg0-seo-01                своя копия и своя ветка
an1mego.site             claude/extract-an1mego-seo-01                своя копия и своя ветка
lordserials22.info       claude/extract-lordserials22-info-seo-01     своя копия и своя ветка
1lordserials1.online     claude/extract-1lordserials1-online-seo-01   своя копия и своя ветка
lordfilm47.space         claude/extract-lordfilm47-space-seo-01       своя копия и своя ветка
lordserial33.biz         claude/extract-lordserial33-biz-seo-01       своя копия и своя ветка
zonafilm12.site          claude/extract-zonafilm12-site-seo-01        своя копия и своя ветка
zonafilm.space           claude/extract-zonafilm-space-seo-01         своя копия и своя ветка
zonafilm.cc              HEAD                                         ОТСОЕДИНЁННЫЙ HEAD: работа не привязана 
lordfilm.group           claude/extract-lordfilm-group                своя копия и своя ветка
lordfilm.spb.ru          claude/extract-lordfilm-spb-ru               своя копия и своя ветка
lordfilm.msk.ru          claude/extract-lordfilm-msk-ru               своя копия и своя ветка
lordserial.su            claude/extract-lordserial-su                 своя копия и своя ветка
lordserial.group         claude/extract-lordserial-group              своя копия и своя ветка
lordserial.spb.ru        claude/extract-lordserial-spb-ru             своя копия и своя ветка
lordserial.msk.ru        claude/extract-lordserial-msk-ru             своя копия и своя ветка
lordserial.net.ru        claude/extract-lordserial-net-ru             своя копия и своя ветка

домéнов 25; со своей веткой 25; отсоединённых 1
общих веток нет: работа по домéнам изолирована
ОТСОЕДИНЁННЫЙ HEAD: zonafilm.cc — работа там не привязана к ветке
(код возврата: 1)
```

## отчётность: расписание и состояние

```
$ python3 automation/local/owner-report.py --status
{
 "расписание": {
  "10:00": "результаты ночи, состояние всех сайтов, приоритеты дня",
  "18:00": "результаты дневной работы, выявленные проблемы, корректировки плана",
  "22:00": "результаты вечера и конкретный план ночной работы"
 },
 "часовой_пояс": "Europe/Moscow",
 "ближайшая_отправка": "2026-10-22T18:00+03:00",
 "последний_отчёт": {
  "слот": "10:00",
  "at_utc": "2026-10-22T09:15:47Z",
  "at_msk": "2026-10-22T12:15+03:00",
  "период_с": "2026-10-21T21:15:47Z",
  "период_откуда": "предыдущего отчёта нет — взяты последние 12 часов",
  "коммитов": 252,
  "охват": "ВНЕ ЦИКЛА",
  "вне_цикла": [
   "lordfilm.group",
   "lordfilm.msk.ru",
   "lordfilm.spb.ru",
   "lordserial.group",
   "lordserial.msk.ru",
   "lordserial.net.ru",
   "lordserial.spb.ru",
   "lordserial.su"
  ],
  "файл": "docs/reports/owner-2026-10-22-1000.md",
  "доставлено": false,
  "причина_доставки": "нет CREDENTIALS_DIRECTORY: telegram_bot_token выдаётся только службе через LoadCredential",
  "повторов": 1
 },
 "отправлено_слотов": 1,
 "журнал": "/home/claude/wt-nova-publish-memory-02/var/owner-reports/state.json",
 "каталог_отчётов": "/home/claude/wt-nova-publish-memory-02/docs/reports"
}
(код возврата: 0)
```

## отчёт того же слота повторно: защита от дубля

```
$ python3 automation/local/owner-report.py --slot 10:00
слот 2026-10-22-1000 уже обработан 2026-10-22T09:15:47Z: повторный отчёт не собирается (защита от дублирования)
(код возврата: 4)
```

## реестры против схем

```
$ python3 scripts/validate_registries.py
OK: config/active-domains.json -> active-domains.schema.json
OK: config/analytics.json -> analytics-registry.schema.json
OK: config/anime-year-corrections.json -> anime-year-corrections.schema.json
OK: config/content-backlog.json -> content-backlog.schema.json
OK: config/data-sources.json -> data-source-registry.schema.json
OK: config/demand-snapshot.json -> demand-snapshot.schema.json
OK: config/editor-coverage-blockers.json -> editor-coverage-blockers.schema.json
OK: config/editor-run.json -> editor-run.schema.json
OK: config/editorial-calendar.json -> editorial-calendar.schema.json
OK: config/editorial-protected-fields.json -> editorial-protected-fields.schema.json
OK: config/editorial-sources.json -> editorial-sources.schema.json
OK: config/experiments.json -> experiment-registry.schema.json
OK: config/learning-queue.json -> learning-queue.schema.json
OK: config/load-bearing-paths.json -> load-bearing-paths.schema.json
OK: config/portfolio.fixture.json -> portfolio-registry.schema.json
OK: config/portfolio.json -> portfolio-registry.schema.json
OK: config/revision-findings-20261017.json -> revision-findings.schema.json
OK: config/secret-hub.json -> secret-hub.schema.json
OK: config/seo-changes.json -> seo-changes.schema.json
OK: config/seo-module-defects.json -> seo-module-defects.schema.json
OK: config/site-cells.json -> site-cells.schema.json
OK: config/template-pool.json -> template-pool.schema.json
OK: config/SITE-MATRIX.json -> site-matrix.schema.json
(код возврата: 0)
```

## целостность базы знаний

```
$ python3 -m factory knowledge verify
freeze: 2026-10-22.1 | целостность: OK
(код возврата: 0)
```

