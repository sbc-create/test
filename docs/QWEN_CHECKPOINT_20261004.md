# Checkpoint 2026-10-04 — продолжать отсюда, аудит не повторять

Состояние сквозного процесса Site Factory через Qwen. Аудит цепочки —
`QWEN_WORKFLOW_AUDIT.md`, доказательства прогонов —
`verification/indexing-operation-20261004.md`.

## Выложено через интерфейс MCP: две выкладки

| # | домен | заявка | релиз | исход | что доставлено |
| --- | --- | --- | --- | --- | --- |
| 1 | `zonafilm.space` | `zona-01-code-2a73197f7d74` | `2a73197f7d74` | `activated` / `live_verified` | проверка публичной почты в выпуске (только `checks/`) |
| 2 | `zonafilm.space` | `zona-01-code-10a4609f6b53` | **`10a4609f6b53`** (действующий) | `activated` / `live_verified`, build `10a4609f6b53-zona-01` | **читатель режима индексации в рантайме** + исправленный замок версий |

Вторая выкладка — доставка МЕХАНИЗМА, и её результат измерен:

    /srv/zonafilm-space/current/src/indexing_mode.py   -> ЕСТЬ (прежде отсутствовал)
    domain_indexing_readiness: runtime_reader = /srv/zonafilm-space/current/src/indexing_mode.py
                               release_gap = permission_false (пробел читателя закрыт)
    confirm_indexing           -> CLOSED, подтверждено ответом домена
    audit_page_seo             -> HTTP 200, title «Zona Cinema — кинопортал»,
                                  canonical https://zonafilm.space/, meta robots noindex,
                                  X-Robots-Tag noindex ×2
    страница произведения      -> HTTP 200, 85126 символов, издатель 10252, 15 постеров

Отказ CI у этой ветки (прогон `37166840562`) был разобран, а не обойдён:
`pins-match-sources` сообщал `lords-frontend.py: sha256 7b5cdb77a076 вместо
aaf1593b6c20` — коммит изменил рантайм на +64 строки, а замок версий остался
прежним. Сторож плавающей версии сработал верно; замок пересчитан, в
`verified_against` записано что изменилось и чем проверено, прогон
`checks/run.sh` — 21 проверка PASS, CI `37167548798` success.

## Первая выкладка — подробности

| что | значение |
| --- | --- |
| домен | `zonafilm.space` (site_id `zona-01`) |
| заявка | `zona-01-code-2a73197f7d74` |
| коммит | `2a73197f7d7400c71dc508f3172c7db08f7ad278` |
| прогон CI | `36853058397` (`completed/success`, ветка `claude/extract-zonafilm-space`) |
| digest | `sha256:e6daf2218fc52ccd44e8110f0347b64a8f45618121d58529b6028602fbe9ad3a` |
| исход | `activated`, этап `live_verified`, `build_id 2a73197f7d74-zona-01` |
| этапы исполнителя | `prepare`, `protected_data`, `seed_data`, `install_release`, `warm_up`, `switch_route`, `promote`, `verify` |
| журнал | `/var/lib/site-cells/results/zona-01-code-2a73197f7d74.json` |
| установленный релиз на тот момент | `releases/2a73197f7d74` (сейчас — `10a4609f6b53`) |
| содержимое выпуска | только `checks/contact_email.py` и `checks/run.sh` — рантайм, контент и плеер не затронуты |

Live-проверки после выкладки (инструментами моста и измерением страницы):

    release_plan      -> live_commit 2a73197f7d74, action «нечего выкладывать»
    audit_page_seo    -> HTTP 200, title «Zona Cinema — кинопортал»,
                         canonical https://zonafilm.space/, meta robots noindex,nofollow,
                         X-Robots-Tag noindex ×2, robots.txt 200, sitemap 404
    confirm_indexing  -> CLOSED, подтверждено ответом домена (5 запрещающих сигналов)
    страница произведения /title/fragment-hanumana/ -> HTTP 200, 85126 символов,
                         14 <img>, постеры poster.cdnvideohub.com,
                         плеер player.cdnvideohub.com/s2/stable/video-player.umd.js,
                         data-publisher-id 10252, счётчик Метрики 112582938

**ВОСПРОИЗВЕДЕНИЕ НЕ ПРОВЕРЕНО**: проверено наличие источника плеера и
идентификатора издателя, сам поток не запрашивался.

## Инструменты Qwen: было 9, стало 17

Новые — поверх существующих реализаций, без второго оркестратора и без
оболочки: `release_plan`, `release_site`, `operation_result`, `rollback_site`,
`refresh_executor_access`, `audit_page_seo`, `inspect_sitemap`,
`explain_url_scope`. Версия правил — `2026-10-04.2`.

**Установленная служба моста отдаёт 9 инструментов**: она держит код,
загруженный до их появления. Перезапуск — в блоке администратора ниже.

## Причина отказов SEO & Analytics — найдена и измерена

`editorial._сайт` разбирал реестр на каждый вызов и с опросом СЕТИ: платил
запросами ко всем 23 доменам ради одного.

| измерение | до | после |
| --- | --- | --- |
| `editorial._сайт` | 31,4 с (повтор 29,9 с) | 0,5 с (повтор 0,000 с) |
| `analytics_readiness` | 27,6 с | 0,185 с |
| обход 23 доменов | не укладывался, снимался по тайм-ауту | 1,70 с |

Клиент с таймаутом короче 30 с получал обрыв и показывал строку без причины —
ровно «Error executing tool analytics_readiness». Пишущие редакционные
операции спрашивают сеть ЯВНО: из ответа домена выводится право писать.

Сводка аналитики по реестру (19 записей): `READY` 9, `COLLECTION_DISABLED` 10,
`DOMAIN_UNKNOWN` 4 (песочные `.localhost/.test`). `COLLECTION_DISABLED` —
НЕ «аналитика работает»: это объявленный счётчик при выключенном сборе.
Отдельный блокер: `credentials_configured: false` — учётных данных Метрики на
хосте нет, поступление данных проверить нечем.

## Четыре семейства — по отдельности, через тот же интерфейс

| семейство | представитель | что проверено 2026-10-04 | состояние |
| --- | --- | --- | --- |
| zona | `zonafilm.space` (zona-01) | ДВЕ выкладки через MCP, читатель режима в рантайме, индексация CLOSED | **выложено и проверено** |
| lords | `lordserial33.biz` (lords-02) | `refresh_executor_access` → `ok/checked`; `release_plan` отказал названной причиной: рабочая копия на другом коммите | механизм готов, выкладка требует приведения копии к коммиту |
| animego | `an1meg0.site` (animego-04) | `refresh_executor_access` → `ok/checked`; план выпуска читается | шаблон семейства в фабрике ОТСУТСТВУЕТ (прежний блокер): наследование новым сайтам невозможно |
| yummy | `yummyani.site` (yummy-site) | `refresh_executor_access` → `ok/checked` | режимом распоряжается переменная контейнера (`SEO_INDEXING_ENABLED`), операция режима сознательно отказывает: решение объявляется в авторитетном реестре площадки |

Вывод по одному семейству на другие НЕ переносится: у zona доказана выкладка и
доставка механизма, у остальных — только работоспособность операции доступа и
чтения плана.

## Незакрытое и чем именно заперто

| что | состояние | чем заперто |
| --- | --- | --- |
| выпуск `lordserials22.info` (коммит `09d6db0`, CI `37165307203` success) | заявка `lords-05-code-09d6db02828e` отклонена | корневая копия исполнителя `/usr/local/lib/site-factory-cell` не несёт исправления ворот (`_непусто`); нужна переустановка пакета |
| выпуск `zonafilm.cc` (коммит `623c38f`) | CI `37165313024` ОТКАЗ | проверка репозитория требует `release_permits_open is False` — конфликт **D140**, решение владельца |
| выпуск читателя режима `zonafilm.space` | **ВЫПОЛНЕН**: коммит `10a4609`, CI `37167548798` success, релиз `10a4609f6b53` | — |
| публикация материала | инструмента у Qwen нет; на сервере операции есть | у контрольных сайтов нет возможностей `deliver`/`display`; публиковать можно на `animedia.icu`, `animedia.space`, `zonafilm.space` |
| `audit_page_seo` / `inspect_sitemap` / `explain_url_scope` чужой службы | отказывали | служба на srv-qwen, доступа нет; на стороне фабрики те же три задачи закрыты своими инструментами |
| вызов инструментов МОДЕЛЬЮ в чате Qwen | НЕ ПРОВЕРЕНО | проверяется только в сессии Qwen |
| открытие/закрытие на изолированном САЙТЕ | НЕ ПРОВЕРЕНО на живом домене | песочные ячейки — только записи реестра: ни аккаунта, ни `current`, ни рантайма. Доказано на изолированной площадке (7 проверок) |
| воспроизведение видео | НЕ ПРОВЕРЕНО | проверяется наличие источника и издателя |

## Доказательства откката выпуска — из журнала, без опытов на живом сайте

8 заявок в `/var/lib/site-cells/results/` имеют исход `candidate-failed` и шаг
`rollback`: исполнитель сам возвращал трафик, живой релиз не менялся. Среди
них `zona-01-code-f0d1a9413e1a` — тот же сайт в прежней попытке.

## Один блок для администратора

Выполнить на **claude-control-01**, от root, в этом порядке:

    # 1. Дать Qwen восемь новых инструментов (служба держит прежний код).
    #    Зачем: release_plan/release_site/operation_result и SEO-инструменты
    #    в сессии не появятся без перезапуска.
    sudo systemctl restart site-factory-mcp.service
    curl -sS http://127.0.0.1:9000/healthz
    #    Проверка: "read_only": false и "instruction_version": "2026-10-04.2"
    curl -sS -X POST http://127.0.0.1:9000/mcp -H 'Content-Type: application/json' \
      -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | grep -c '"name"'
    #    Проверка: 17
    #    Откат: sudo bash automation/host/enable-mcp-write-mode.sh --undo

    # 2. Обновить корневую копию исполнителя — иначе выпуск lordserials22.info
    #    снова отклонят ворота защищённых данных по пустому хранилищу.
    sudo bash /home/claude/wt-portable-site-cell-01/automation/host/install-cell-executor.sh
    grep -c _непусто /usr/local/lib/site-factory-cell/factory/cell/protected.py
    #    Проверка: больше нуля
    #    Откат: прежняя копия остаётся рядом как <каталог>.old (см. вывод установщика)

После пункта 2 выпуск lordserials22.info подаётся одной командой Qwen:
`release_site {"site": "lordserials22.info"}`, результат — `operation_result`.

## Короткие команды для Qwen (проверенные)

    release_plan        {"site": "zonafilm.space"}
    release_site        {"site": "zonafilm.space"}
    operation_result    {"request_id": "zona-01-code-2a73197f7d74"}
    confirm_indexing    {"site": "zonafilm.space", "expected": "CLOSED"}
    audit_page_seo      {"domain": "zonafilm.space"}
    inspect_sitemap     {"domain": "zonafilm.space"}
    explain_url_scope   {"url": "https://lordserials22.info/api/catalog"}
    analytics_readiness {"domain": "lordserials22.info"}
