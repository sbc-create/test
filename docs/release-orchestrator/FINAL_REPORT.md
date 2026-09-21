# FINAL REPORT — SITE-FACTORY-RELEASE-ORCHESTRATOR-01

```text
VERDICT=BLOCKED_LORDS_P1_DEPENDENCY
STAGE=SITE-FACTORY-RELEASE-ORCHESTRATOR-01
DEPENDENCY=LORDS-CURSOR-WORK-RECONCILIATION-01
DEPENDENCY_STATE=NOT_CLOSED

START_HEAD=4119c6746c7990c55a56bc22f7597afd53c27512
BRANCH=cursor/site-factory-release-orchestrator-01
WORKTREE=/home/claude/wt-site-factory-release-orchestrator-01
WORKTREE_CLEAN=1

P1_DEFECTS_OPEN=1            (требовалось 0)
DOMAIN_TRIPLE_MATCH=1_of_3   (требовалось 3 из 3)
READY_FOR_LORDS_50_FACTORY=NO

LIVE_DEPLOY_PERFORMED=0
RESTART_PERFORMED=0
SYSTEMD_MUTATIONS=0
INDEXABILITY_MUTATIONS=0
DNS_MUTATIONS=0
PUSH_PERFORMED=0
MERGE_PERFORMED=0
OWNER_CANARY_APPROVAL_ID=ABSENT

TESTS=tests/unit/test_release_orchestrator.py + test_release_orchestrator_resilience.py
      + test_permission_matrix.py + test_validate_registries_derived.py
TEST_RUNS_CONSECUTIVE=2 (249 passed + 249 passed, exit 0)
NEW_TESTS=36 (resilience)
MUTATION_CHECKED=3 (resume-skip, atomic write, bypass gate — каждая мутация роняет свой тест)
```

## Вердикт

Зависимость `LORDS-CURSOR-WORK-RECONCILIATION-01` не закрыта ни по одному из
трёх требуемых условий, поэтому живой прогон не выполнялся. Независимая часть
задания выполнена полностью; подготовлен точный owner canary packet для
lords-02.

## Проверка зависимости (только чтение)

Источник — `HANDOFF.json` и `BLOCKERS.json` ветки
`claude/lords-cursor-reconciliation-01` (вершина `6c49663`,
2026-09-21T11:22:16Z), плюс независимое измерение живого хоста.

| Условие | Требовалось | Измерено | Итог |
| --- | --- | --- | --- |
| `P1_DEFECTS_OPEN` | 0 | 1 (B-02 на lords-03) | не пройдено |
| source/artifact/runtime match | 3 из 3 | 1 из 3 | не пройдено |
| `READY_FOR_LORDS_50_FACTORY` | YES | `false` | не пройдено |

Флаг в `HANDOFF.json` снимает владелец после выбора по OA-1; это решение
владельца, а не самооценка агента. Более нового коммита на ветке нет.

## Что измерено на живом хосте

| Витрина | Объявлено | Исполняется | Итог |
| --- | --- | --- | --- |
| lords-01 / lordfilm47.space | `b32438c9` | процесс старше миграции | `UNMEASURED` |
| lords-02 / lordserial33.biz | `b32438c9` | `b32438c9` | **COHERENT** |
| lords-03 / 1lordserials1.online | `5dd817fe` | `b32438c9` | **DIVERGED** |

Полные измерения — `reports/releases/rel-owner-canary-lords02-20260921-01/LIVE_STATE.json`.

## Блокеры, найденные этим этапом

**RO-01 (P1) — реестр называет юнит, который не обслуживает домен.**
`config/release-registry.json` объявляет `lords-0N.service`; nginx маршрутизирует
каждый домен на порт, который слушает `*-nova-*` юнит:

```text
lordfilm47.space     → 9110 → lords-nova-01.service  ≠ lords-01.service (9101)
lordserial33.biz     → 9111 → nova-lords-02.service  ≠ lords-02.service (9102)
1lordserials1.online → 9112 → nova-lords-03.service  ≠ lords-03.service (9103)
```

Оба юнита каждой пары живы, поэтому ошибка не проявляется отказом. Живой
прогон перезапустил бы объявленный, но не маршрутизируемый юнит: витрина
осталась бы нетронутой, а smoke — он ходит на домен — всё равно бы прошёл.
Ложный PASS. Независимо подтверждено `lords-runtime-registry.json`, который
другой поток работ построил из своих источников и который называет те же юниты.

Закрыто воротами: `service_binding.py` выводит настоящий юнит из nginx и
unit-файлов, мутирующий прогон отказывает с `BLOCKED_SERVICE_BINDING` до
первого перезапуска. Теневой прогон не затронут.

**RO-02 (P1) — хост не в покое.** Во время сессии другой поток работ мигрировал
общий рантайм на по-доменный диспетчер: `/srv/lords/.frontend/lords-frontend.py`
сменился с 418858 байт (`b32438c9`) на 6843 байта (`2495eac5`) между 11:45Z и
12:06Z; lords-02 перезапускался дважды. Canary сейчас гонялся бы с чужой
выкладкой.

**RO-03 (P2) — smoke ×2 по живым доменам неисполним.** HTTP к трём доменам
закрыт guard'ом (B-01 зависимости), поэтому `catalog_revision` и
`details_revision` помечены `UNMEASURED_REQUIRES_HTTP`, а не заполнены догадкой.

## Что сделано

Ворота точного соответствия домена и юнита (`05ff4e7`), 36 тестов
устойчивости (`13464c7`), сопоставление `release-registry.json` его схеме
(`f6241d9`).

Тесты закрывают то, чего не было в основном наборе: resume после обрыва
(включая продолжение витрины со стадии STAGED, а не с начала), идемпотентность
трёх прогонов подряд, атомарность чекпойнта при обрыве между записью и
переименованием, поведение при `Too many open files` (stderr systemd не
доказательство отказа, но и не отбеливание провала постусловий; EMFILE всплывает
ошибкой, а не половиной состояния), обходные пути выкладки, точный реестр
доменов с отказом на подстроке, поддомене и соседнем TLD, и откат с побайтовой
сверкой.

Тесты проверены мутациями: снятие пропуска `POST_DEPLOY_PASS`, замена атомарной
записи прямой и удаление bypass-ворот из `lords-staging-apply.sh` — каждая
роняет свой тест. Источник после мутаций восстановлен из git.

## Известный незакрытый тест

`tests/unit/test_job_result.py::test_real_pilot_results_are_schema_valid` падает
в полном прогоне: он требует `artifacts/jobs/pilot-local/*.json`, которые
создаёт пилотный прогон и которые сознательно не коммитятся (`667bb02`). Отказ
воспроизводится на чистом `HEAD` без изменений этого этапа, к релиз-оркестратору
отношения не имеет и здесь не чинился — подделывать артефакт ради зелёного
прогона запрещено правилом.

## Owner canary packet

`reports/releases/rel-owner-canary-lords02-20260921-01/` — подготовлен, **не
исполнен**. Область: только lords-02, единственная витрина с совпадающими
объявленным, назначенным и исполняемым. lords-01 и lords-03 не затрагиваются.
DNS и индексация не меняются.

Исполнение требует отдельного `OWNER_CANARY_APPROVAL_ID` и снятия четырёх
блокирующих условий, перечисленных в `OWNER_CANARY_PACKET.md`.

## Чего этот отчёт не утверждает

Живой canary не проходил. Он не запускался. Все `PASS` в пакете получены в
теневой репетиции и помечены как таковые.
