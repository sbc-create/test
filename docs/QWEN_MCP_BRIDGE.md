# Инструменты Qwen и фактическая фабрика: что подключено и чего не хватает

Дата измерений: 2026-10-03, хост `claude-control-01`, учётная запись `claude`.

## 1. Установленная причина расхождения `sites: []`

Симптом: в сессии Qwen `list_registered_sites` возвращает
`{"version": 1, "sites": []}`, а `site-factory_system_readiness` сообщает
`registry.valid: true`.

Измерено на хосте, без догадок:

| проверка | результат |
| --- | --- |
| поиск `list_registered_sites`, `get_registered_site`, `system_readiness` в этом репозитории | **ни одного совпадения** |
| тот же поиск по всему `/srv/site-factory` | **ни одного совпадения** |
| перебор ВСЕХ слушающих портов хоста (`/proc/net/tcp*` + сопоставление с процессами) | служб, отдающих оболочку `{"version": 1, "sites": [...]}`, нет |
| местный Control API `127.0.0.1:8790` (юнит `site-factory-control-api.service`, релиз `e698e2adf502` от 2026-09-12, корень состояния `/srv/site-factory/repo`) | `GET /api/v1/ready` -> `{"ready": true}`; `GET /api/v1/sites` -> `{"items": [...], "total": 13, "registry_version": 32, "source": "registry"}` — **непустой** список, оболочка `items`, БЕЗ полей `version`/`sites` |
| состав того списка | 13 записей, из них три синтетических (`synthetic-*.test`, `demo-books.invalid`) и нет шести доменов авторитетного реестра (`lordserials22.*`, `zonafilm.cc`, `zonafilm12.site`, `an1meg0.site`, `yummyani7.*`) — это ДРУГОЙ реестр (`/srv/site-factory/repo`), а не реестр ячеек |
| авторитетный реестр ячеек `config/site-cells.json` этого worktree | 23 записи, читается (`registry.состояние_источников()`) |

**Вывод по доказательствам.** Инструменты Qwen обслуживает НЕ этот хост и не
этот код: ни имён, ни оболочки `{"version":1,"sites":[]}` здесь нет, а местный
Control API отвечает другой оболочкой (`items`) и непустым списком. Значит
`sites: []` при `registry.valid: true` — согласованный ответ ДРУГОГО источника,
у которого свой (пустой) реестр.

Чего я НЕ утверждаю, потому что не проверял: что виновата авторизация, что
реестр того источника «сломан» и что он вообще находится в сети этого хоста.
Связь между сессией Qwen и `claude-control-01` по-прежнему НЕ ПОДТВЕРЖДЕНА — и
подтвердить её можно ровно одним способом: сравнить окружение, которое
возвращает ответ, с тем, что ниже.

## 2. Что доставлено: мост к авторитетному реестру и штатным операциям

`factory/qwen/mcp.py` — MCP-сервер без внешних зависимостей (JSON-RPC 2.0 по
stdio: `initialize`, `tools/list`, `tools/call`). Ни второго реестра, ни
второго оркестратора: каждый инструмент вызывает существующий модуль, и это
закреплено тестом `test_мост_не_заводит_второй_реестр_и_второй_оркестратор`
(разбор дерева исходника: никаких своих путей к реестру и очереди, никакой
своей логики разрешений, никакой произвольной оболочки).

Имена трёх инструментов СОВПАДАЮТ с теми, что уже есть в сессии Qwen, поэтому
переключение — только настройка коннектора:

| инструмент | что делает | источник |
| --- | --- | --- |
| `system_readiness` | окружение (хост, учётная запись, каталог), источники реестра с путями и числом записей, версия правил и версия кода; `registry.valid` ставится ТОЛЬКО по факту прочитанных источников | `registry.собрать`, `registry.состояние_источников` |
| `list_registered_sites` | `{"version": 1, "sites": [...]}` из авторитетного реестра | тот же |
| `get_registered_site` | одна запись по домену или `site_id` | тот же |
| `domain_indexing_readiness` | вердикт готовности домена (7 статусов, `release_gap`, `required_release`, `next_action`) | `indexing.готовность` |
| `set_indexing_mode` | смена режима ШТАТНОЙ операцией со всеми предпроверками | `indexing.установить` |
| `confirm_indexing` | что домен отдаёт сейчас | `indexing.подтвердить` |
| `indexing_journal` | файл состояния, записи операций, результаты заявок слоя с фактическими `nginx_test`/`nginx_reload` | `indexing.текущее`, `indexing.ЖУРНАЛ`, `queue.состояние` |

Три правила ответа:

1. **пустой успех запрещён** — нечитаемый реестр, прочитанный но пустой
   реестр, неизвестный домен и неизвестный инструмент возвращают `isError`
   с названной причиной и путями источников;
2. **идентичность окружения в каждом ответе** (включая отказ): хост, учётная
   запись, каталог, ветка и коммит кода, путь и версия инструкции;
3. **проверки владельца и выпуска остаются на месте** — смена режима идёт
   через `indexing.установить`, произвольной команды оболочки сервер не
   предоставляет вовсе.

## 3. Чего не хватает для подключения: один параметр

Сервер запускается одной командой:

    /usr/bin/python3 -m factory.qwen.mcp

с рабочим каталогом `/home/claude/wt-portable-site-cell-01` на
`claude-control-01` под учётной записью `claude`.

**Недостающий параметр — адрес/команда MCP-сервера в настройках приложения
Qwen.** Он находится на стороне приложения, и мне он недоступен. Возможны две
формы, и нужна ровно одна из них:

**(а) если приложение Qwen запускает локальные MCP-серверы командой** — в его
настройках MCP (экран «Connectors»/«MCP Servers», пункт «Add server» ->
«Command»/«stdio») завести сервер с именем `site-factory`:

    command: /usr/bin/python3
    args:    ["-m", "factory.qwen.mcp"]
    cwd:     /home/claude/wt-portable-site-cell-01

Готовый к копированию файл —
`/srv/site-factory/indexing-operator-2026-10-03/qwen-mcp-server.json`.

**(б) если приложение Qwen ходит к серверу по сети** — назовите, какой
транспорт оно умеет (SSE/HTTP), и укажите, через какой канал оно видит
`claude-control-01`. Без этого ответа мост остаётся локальным: сам он сетевого
слушателя не поднимает намеренно — публичная точка управления фабрикой
требует отдельного решения владельца.

Пока коннектор не перенастроен, Qwen продолжит получать `sites: []` от
прежнего источника: его конфигурация в приложении пользователя, и из этой
сессии её не видно.

## 4. Приёмка из сессии Qwen: три шага

После перенастройки коннектора:

1. **сервер и версия** — вызвать `system_readiness`. Ожидаемое:
   `environment.host = claude-control-01`, `environment.host_matches_factory =
   true`, `environment.instruction.version` совпадает с
   `grep -m1 instruction_version /srv/site-factory/qwen-seo-handover-2026-10-01/QWEN-CANONICAL.md`,
   `registry.sources.site_cells.path` заканчивается на
   `wt-portable-site-cell-01/config/site-cells.json`, `registry.sites = 23`;
2. **сайты** — вызвать `list_registered_sites`. Ожидаемое: `version = 1`,
   `sites` содержит 23 записи; `lordserials22.info` среди них;
3. **домен без изменений** — вызвать `domain_indexing_readiness` с
   `{"site": "lordserials22.info"}`. Ожидаемое: `verdict.status =
   MECHANISM_UNSUPPORTED`, `release_gap = permission_false`,
   `public_mode = CLOSED`,
   `evidence.nginx_layer.managed_by_this_operation = true`. Ни одного
   изменения эта проверка не делает.

Если первый шаг вернул другой хост или другую версию инструкции — коннектор
смотрит не на эту фабрику, и дальше идти нельзя: это и есть та самая
неразличимость, с которой задача началась.

Без MCP-клиента то же самое проверяется на сервере одной командой:

    python3 -m factory.qwen.mcp --self-check

Выполнено 2026-10-03: `ok: true`, `registry_valid: true`, `sites: 23`,
`version: 1`, окружение `claude-control-01 / claude /
home/claude/wt-portable-site-cell-01`, инструкция `2026-10-03.5`.

## 5. Подключение существующего HTTP-коннектора Open WebUI

Фактические настройки коннектора (из интерфейса): Open WebUI v0.11.4 на
`http://83.237.185.70:8500`, подключение `site-factory` (read-only), транспорт
MCP Streamable HTTP, URL `http://site-factory-mcp:9000/mcp`, аутентификации
нет.

### Где что находится — по измерению 2026-10-03

| проверка с `claude-control-01` | результат |
| --- | --- |
| принадлежит ли `83.237.185.70` этому хосту | **нет**: `bind()` отвечает `Cannot assign requested address`; публичный адрес фабрики — `45.131.182.225` (A-запись `lordserials22.info`) |
| разрешается ли имя `site-factory-mcp` | **нет**: `gaierror` — это имя сети контейнеров ДРУГОГО хоста |
| есть ли здесь контейнер `site-factory-mcp` или `open-webui` | **нет**: из 61 контейнера ни одного подходящего |
| достижимость хоста Open WebUI | `83.237.185.70:8500` открыт, `:22` открыт, **`:9000` отказывает** соединение |
| авторизованный доступ к этому хосту у сессии | **нет**: `inventory/ssh-hosts.yaml` содержит `hosts: []`, а `ssh` запрещён профилем сессии. Расширять список хостов по своей инициативе нельзя |

Чего эти факты НЕ доказывают: что сервис `site-factory-mcp` не существует.
Отказ `:9000` снаружи одинаково выглядит и у остановленного сервиса, и у
сервиса, который слушает только внутри сети контейнеров (а именно так и
правильно). Поэтому ниже — одно действие, которое различает эти случаи ИЗ ТОГО
окружения, где они различимы.

### Топология подключения без публичного порта

    Open WebUI (83.237.185.70, сеть контейнеров)
      └── контейнер site-factory-mcp  ──ssh -L 9000──▶ claude-control-01
                 слушает :9000 в сети контейнеров        127.0.0.1:9000
                 (наружу порт НЕ публикуется)            site-factory-mcp.service
                                                          --http 127.0.0.1:9000
                                                          --read-only

Почему так, а не слушателем на публичном адресе: управляющая точка фабрики в
интернет не публикуется. Мост сам отвергает привязку вне петли без явного
ключа `--allow-nonlocal` — проверено тестом.

Нового кода на хосте Open WebUI не требуется: контейнер только пробрасывает
TCP туннелем SSH. Готовый фрагмент —
`/srv/site-factory/indexing-operator-2026-10-03/open-webui-site-factory-mcp.compose.yaml`
(без `ports:`, ключи SSH монтируются только на чтение, `healthcheck` опрашивает
`/healthz` моста). Перед правкой compose — резервная копия, команда указана в
самом фрагменте.

### Сторона фабрики: служба готова

    sudo install -m 0644 /home/claude/wt-portable-site-cell-01/automation/host/site-factory-mcp.service \
        /etc/systemd/system/site-factory-mcp.service
    sudo systemctl daemon-reload && sudo systemctl enable --now site-factory-mcp.service

Служба запускает `python3 -m factory.qwen.mcp --http 127.0.0.1:9000 --read-only`
от учётной записи `claude` из рабочего дерева фабрики. Порт 9000 на петле
свободен (проверено). Пока служба не установлена, то же самое поднимается
вручную той же командой.

### Проверено по HTTP на этой стороне

Транспорт опрошен настоящим сокетом (не обработчик в отрыве):

| вызов | результат |
| --- | --- |
| `GET /healthz` | `200`, `ready: true`, `read_only: true`, сервер `site-factory`, правила `2026-10-03.6`, хост `claude-control-01` |
| `POST /mcp initialize` | `200 application/json`, `serverInfo.name = site-factory`, `version = 2026-10-03.6`, `read_only = true`, `environment.host = claude-control-01` |
| `POST /mcp tools/list` | `200`, **6** инструментов, `set_indexing_mode` отсутствует (режим только чтения) |
| `POST /mcp tools/call system_readiness` | `200`, `registry.valid = true`, `sites = 23`, источник `/home/claude/wt-portable-site-cell-01/config/site-cells.json` |
| `POST /mcp tools/call list_registered_sites` | `200`, `version = 1`, **23** сайта, `lordserials22.info` в списке; при `Accept: text/event-stream` тот же ответ одним событием `data:` |
| `POST /mcp tools/call set_indexing_mode` | `isError` с названной причиной: сервер только читает, смена режима — командой `factory.qwen indexing-set` на сервере |
| `GET /mcp` | `405 stream_not_supported` с объяснением, а не молчание |
| уведомление без `id` | `202` без тела |
| `--http 0.0.0.0:9000` без ключа | отказ запуска: «управляющая точка фабрики в интернет не публикуется» |

### Одно действие для терминала хоста Open WebUI

    sh /путь/к/diagnose-open-webui-mcp.sh

Скрипт лежит здесь:
`/srv/site-factory/indexing-operator-2026-10-03/diagnose-open-webui-mcp.sh`
(скопировать на тот хост любым доступным способом; весь он — три команды и
подсказка, как читать вывод). Он отвечает сразу на три вопроса:

1. существует ли сервис `site-factory-mcp` и что он сейчас делает
   (`docker ps -a` + последние строки журнала);
2. что получает САМ Open WebUI по настроенному адресу
   (`docker exec open-webui curl -i -X POST http://site-factory-mcp:9000/mcp`
   с телом `initialize`);
3. достижима ли фабрика по SSH **из контейнера** — успешный SSH из Agent
   Workspace (`6265eddb1580`) этого не доказывает: другой контекст, другая
   сеть, другие ключи.

Как читать результат — напечатано самим скриптом в конце.

## 6. srv-qwen: подключение существующего сервиса к мосту

Полученные факты (от администратора, 2026-10-03): на `srv-qwen` работают
контейнеры `qwen-open-webui` и `qwen-site-factory-mcp`; из первого адрес
`http://site-factory-mcp:9000/mcp` отвечает `HTTP 200`; `initialize` даёт
`serverInfo.name = "Qwen Site Factory"`, `version = ""`; `system_readiness`
даёт `registry.valid: true`, `site_count: 0`, пустые `errors` и `warnings`;
образ `qwen-agent-modules:1.0.0`; compose `/opt/qwen/compose.yaml`; примонтированы
`/opt/qwen/data → /data` и `/opt/qwen/knowledge → /knowledge`.

Это закрывает вопрос о причине: отвечает ДРУГОЙ сервер со своим пустым
реестром. Его `site_count: 0` при `valid: true` — согласованный ответ о пустом
источнике, а не поломка фабрики. **Заполнять его реестр руками нельзя**:
авторитетный реестр один и живёт на `claude-control-01`.

### Состояние моста на фабрике — проверено, НЕ установлен

| проверка | результат |
| --- | --- |
| `/etc/systemd/system/site-factory-mcp.service` | **отсутствует** |
| слушает ли `127.0.0.1:9000` | **нет** (`ConnectionRefusedError`) |
| процесс `factory.qwen.mcp` | **нет** |
| юнит подготовлен | да: `automation/host/site-factory-mcp.service` (петля + `--read-only`) |

Установить его из сессии невозможно: `sudo` запрещён её профилем. Это первое
действие владельца на фабрике:

    sudo install -m 0644 /home/claude/wt-portable-site-cell-01/automation/host/site-factory-mcp.service \
        /etc/systemd/system/site-factory-mcp.service
    sudo systemctl daemon-reload && sudo systemctl enable --now site-factory-mcp.service
    curl -sS http://127.0.0.1:9000/healthz     # ready: true, read_only: true

**НЕ ПРОВЕРЕНО** до установки: что служба поднимается именно этим юнитом на
этом хосте (сам модуль по HTTP проверен настоящим сокетом, см. раздел 5).

### Как подключается srv-qwen, сохраняя URL коннектора

Имя `site-factory-mcp` в сети контейнеров отдаётся новому сервису-мосту,
прежний остаётся под именем `site-factory-mcp-legacy`. URL коннектора
(`http://site-factory-mcp:9000/mcp`) и тип транспорта не меняются.

    qwen-open-webui ──http://site-factory-mcp:9000/mcp──▶ qwen-site-factory-bridge
                                                            │ ssh -L 9000:127.0.0.1:9000
                                                            ▼
                                                   claude-control-01 (45.131.182.225)
                                                   127.0.0.1:9000  site-factory-mcp.service
                                                   --read-only, авторитетный реестр

Готовые артефакты в `/srv/site-factory/indexing-operator-2026-10-03/`:

| файл | что это |
| --- | --- |
| `srv-qwen-bridge.compose.yaml` | фрагмент для `/opt/qwen/compose.yaml`: мост + переименование алиаса прежнего сервиса, без `ports:`, том канала только на чтение, `healthcheck` по `/healthz` моста |
| `channel-grant-line.txt` | строка доверенного ключа с ограничениями `restrict,permitopen="127.0.0.1:9000",command="/bin/false"` — добавляет ВЛАДЕЛЕЦ на фабрике; ключей сессия не читает и не пишет (профиль это запрещает) |
| `acceptance-from-open-webui.sh` | приёмка изнутри `qwen-open-webui`, только чтение; проверена против моста по HTTP (`rc=0`) |

Резервная копия и откат названы в самом фрагменте compose: копия
`/opt/qwen/compose.yaml.bak.<UTC>` перед правкой; откат — вернуть файл и
`docker compose up -d`, после чего имя снова указывает на прежний сервис.
Отзыв доступа — удалить строку ключа; канал исчезает сразу.

### Что требуется от администратора и чего я не выдумываю

Нужны ровно три величины, и ни одна из них не секрет:

1. **открытый ключ** канала (строка `ssh-ed25519 AAAA…`) — её печатает команда
   ниже; закрытая часть остаётся на `srv-qwen`;
2. **имя сети контейнеров** Open WebUI (`SF_BRIDGE_NETWORK`);
3. **каталог канала** на `srv-qwen`, куда положены ключ и `known_hosts`
   (`SF_BRIDGE_SSH_DIR`) — путь выбирает администратор, я его не придумываю.

**НЕ ПРОВЕРЕНО** (из этой сессии проверить нечем):

* доступность `45.131.182.225:22` с `srv-qwen` — успешный SSH из Agent
  Workspace (`6265eddb1580`) этого не доказывает: другой контекст и другие ключи;
* наличие `ssh` в образе `qwen-agent-modules:1.0.0` — поэтому мост сделан
  отдельным контейнером `alpine:3.20`, который ставит клиента сам, а прежний
  образ не трогается;
* имя сети контейнеров и фактические имена томов на `srv-qwen`.

### Приёмка (после подключения)

    sudo docker exec -i qwen-open-webui sh -s < acceptance-from-open-webui.sh

Проверяет: `serverInfo.name = site-factory`, непустую версию правил
(`2026-10-03.6`), `environment.host = claude-control-01`, `read_only: true`,
отсутствие пишущего инструмента, `registry.valid`, число сайтов **23**,
источник `config/site-cells.json` и **отпечаток списка доменов**
`4511cf3add1b3e88` (sha256 отсортированных доменов — одно значение вместо
сверки двадцати трёх имён). Прогон против моста на фабрике: все проверки OK,
`rc=0`.
