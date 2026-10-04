# Checkpoint 2026-10-04 — продолжать отсюда, аудит не повторять

Состояние сквозного процесса Site Factory через Qwen. Аудит цепочки —
`QWEN_WORKFLOW_AUDIT.md`, доказательства прогонов —
`verification/indexing-operation-20261004.md`.

## Состояние двух действий администратора — измерено 2026-10-04 07:08–07:10 UTC

| пункт | состояние | чем измерено |
| --- | --- | --- |
| 1. перезапуск службы моста | **ПРИМЕНЁН** в 07:08:14 UTC | до него `/healthz` отдавал `2026-10-04.1` и 9 инструментов; после — `2026-10-04.2` и 17. Журнал службы называет момент запуска и перечень |
| 2. обновление корневой копии исполнителя | **ПРИМЕНЁН** в 07:10:34 UTC | `cell-install.json` от `2026-10-04T07:10:34Z`, `code_source: /home/claude/wt-portable-site-cell-01`; установленный `protected.py` байт в байт совпадает с исходником (44287 Б, sha256 `6e50c553161ddc44`, три вхождения `_непусто`). Дефекта в установщике нет: мой прежний замер опередил установку на секунды |

### lordserials22.info ВЫЛОЖЕН

Та же заявка `lords-05-code-09d6db02828e` (подача была `requeued-after-failure`)
переразобрана исполнителем после обновления копии и прошла:

    журнал изменён 2026-10-04 07:15:51 UTC: status ok / outcome activated /
    stage live_verified / build 09d6db02828e-lords-05, error None
    шаг protected_data: present [indexing_journal, indexing_state, nginx_indexing],
                        empty_kinds ["editorial"], missing_readers [], compatible true
    current -> /srv/lordserials22-info/releases/09d6db02828e (ссылка от 07:15:22)
    confirm_indexing -> CLOSED, подтверждено; файл состояния CLOSED revision 1
    вердикт -> AWAITING_OWNER, release_gap null, release_permits_open true,
               owner_authorized_open false

Отказ, на который ссылался владелец, — результат ДО обновления копии: прежний
код считал ПУСТОЕ хранилище материалов присутствующими данными. Ни заглушки, ни
удаления данных, ни отключения защиты: ворота стали точными, и их собственный
шаг подтверждает `empty_kinds: ["editorial"]` при `missing_readers: []`.
Защищённые данные, которые выпуск обязан был сохранить, — `indexing_state`,
`indexing_journal`, `nginx_indexing`; все сохранены, читатель режима в выпуске
есть. Редакционных данных у этого сайта НЕТ (хранилище пусто), поэтому читатель
правок для корректности ЭТОГО выпуска не требовался; отсутствие возможности
показа остаётся отдельным, названным пунктом.

Где читатель правок ДЕЙСТВИТЕЛЬНО нужен — `lords-02` (lordserial33.biz):
измерено, что там редакционные данные НЕ пусты, а `src/editorial_overlay.py`
в репозитории отсутствует, и ворота отказывают. Это отдельная работа.

### Прежняя запись (на момент до 07:10)

Выкладка `lordserials22.info` была заперта пунктом 2: `release_plan` через
установленную службу говорит «подал бы заявку» без препятствий
(коммит `09d6db02828e`, CI `37165307203`, digest `sha256:4f9f96adcc43…`), а
записанный результат прежней заявки — `rejected` с текстом ворот защищённых
данных.

После пункта 2 выкладка выполняется одной командой Qwen:
`release_site {"site": "lordserials22.info"}`.

Инструментов в коде стало **22** (добавлена публикация материала), в
работающей службе — 17: перезапуск отдаёт то, что лежит на диске в его момент.

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
| публикация материала | инструменты ПОДКЛЮЧЕНЫ (editorial_facts, editorial_status, prepare_material, publish_material, unpublish_material); нового материала не публиковалось | у контрольных сайтов нет возможностей `deliver`/`display`; публиковать можно на `animedia.icu`, `animedia.space`, `zonafilm.space` |
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

## Публикация материала: что подключено и почему ничего не опубликовано

Подключены существующие операции: `editorial_facts`, `editorial_status`
(чтение) и `prepare_material`, `publish_material`, `unpublish_material`
(запись). Своей логики качества, фактов и прав у моста нет — он зовёт
`editorial.факты/состояние/подготовить/публиковать/снять`.

Ворота проверены на живом сайте: `publish_material` для `lordserials22.info`
отказывает словами операции — «сайту не хватает возможностей ['deliver',
'display'] — операция publish недоступна», потому что в выпущенном рантайме нет
`src/editorial_overlay.py`.

Фактическое состояние материалов: у `animedia.space` два подтверждённых и один
черновик; у `zonafilm.space` и `animedia.icu` материалов нет.

Нового материала не публиковалось, и это не упущение:

1. проверенного материала нет — старые черновики без доказанной проверки
   одобренными не считаются, а выдумывать сведения запрещено;
2. публиковать на `animedia.space` нельзя: это production и он ОТКРЫТ, то есть
   текст сразу попал бы на живую публичную страницу;
3. закрытого ТЕСТОВОГО сайта с возможностью показа не существует: песочные
   ячейки `pilot.localhost.test`, `site-a/b/c.localhost` — только записи
   реестра, без аккаунта, `current` и рантайма.

Отсюда недостающая реализация названа точно: нужен закрытый тестовый экземпляр
с работающим рантаймом и читателем правок. Это отдельная работа, а не оговорка.

## Исходное SEO-подключение: что проверено и что нет

Исправлено на стороне фабрики и измерено: причина отказов по тайм-ауту (разбор
реестра опрашивал сеть по всем доменам ради одного) — 31,4 с → 0,5 с, вызов
`analytics_readiness` 27,6 с → 0,185 с.

Это НЕ проверка исходной службы. Четыре инструмента `seo-analytics-mcp` на
srv-qwen (`audit_page_seo`, `inspect_sitemap`, `analytics_readiness`,
`explain_url_scope`) остаются **НЕ ПРОВЕРЕННЫМИ**: доступа к srv-qwen нет
(`inventory/ssh-hosts.yaml`: `hosts: []`), её журналов на фабрике не
существует. Со стороны фабрики измерено только то, что канал установлен
(учётная запись `sfbridge` uid 973, порт 9000 слушает мост) и что в момент
замера установленных соединений извне не было.

Установить причину можно одним прогоном НА srv-qwen:
`automation/srv-qwen/diagnose-seo-analytics.sh` — он печатает upstream службы
(значения только у переменных-адресов, секреты скрыты), разрешение имён
`site-factory-mcp` и `site-factory-mcp-legacy`, кто из них отвечает, полный
текст ошибки инструмента и след из её журнала.

## Четыре выкладки через интерфейс MCP — итог дня

| # | домен | заявка | релиз | исход | содержимое выпуска |
| --- | --- | --- | --- | --- | --- |
| 1 | `zonafilm.space` | `zona-01-code-2a73197f7d74` | `2a73197f7d74` | `activated`/`live_verified` | проверка публичной почты (только `checks/`) |
| 2 | `zonafilm.space` | `zona-01-code-10a4609f6b53` | `10a4609f6b53` | `activated`/`live_verified` | читатель режима в рантайме + замок версий |
| 3 | `lordserials22.info` | `lords-05-code-09d6db02828e` | `09d6db02828e` | `activated`/`live_verified` | разрешение выпуска + исправление проверки live-switch |
| 4 | `zonafilm.cc` | `zona-02-code-b834f2525aa5` | `b834f2525aa5` | `activated`/`live_verified` | исправленный контракт разрешений (D141) |

Выкладка 4, подтверждения:

    план через службу: коммит b834f2525aa5, CI 37185780209, live 050649648481
    ворота данных В ПЛАНЕ: present ["nginx_indexing"], empty_kinds [],
                           missing_readers [], compatible true
    digest sha256:82a38e01b29438d2…, build b834f2525aa5-zona-02
    журнал /var/lib/site-cells/results/zona-02-code-b834f2525aa5.json
    current -> b834f2525aa5
    confirm_indexing -> CLOSED, подтверждено ответом домена
    вердикт -> AWAITING_OWNER, release_permits_open true, owner_authorized_open FALSE
    installed_release называет источники: /srv/zonafilm-cc/current и
                           /srv/zonafilm-cc/current/config/site.json
    страница: 200, «Zona — фильмы и сериалы онлайн», meta robots noindex,
              canonical https://zonafilm.cc/
    контент и плеер: главная 127635 символов, 87 ссылок на произведения,
              /title/ad-dzheffri/ 200 (82860 символов), издатель 10238,
              15 постеров poster.cdnvideohub.com, плеер player.cdnvideohub.com
    защищённые данные: файла состояния нет (закрыт отсутствием),
              слой nginx «режим: CLOSED», default "noindex, nofollow"

Воспроизведение НЕ ПРОВЕРЕНО: проверено наличие источника плеера и
идентификатора издателя.
