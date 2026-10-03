# Проверка доставки моста на srv-qwen — 2026-10-03

Команды, фактические коды возврата и артефакты. Строки «проверено» без запуска
здесь не допускаются: каждая запись соответствует одному прогону.

## 1. Сторона фабрики — настоящие вызовы MCP

    systemctl is-active site-factory-mcp.service      -> active
    systemctl is-enabled site-factory-mcp.service     -> enabled
    GET  http://127.0.0.1:9000/healthz                -> HTTP 200, ready=true, read_only=true
    POST .../mcp initialize                           -> HTTP 200, site-factory 2026-10-03.6, host=claude-control-01
    POST .../mcp tools/list                           -> HTTP 200, 6 инструментов, пишущего нет
    POST .../mcp system_readiness                     -> HTTP 200, sites=23, digest=4511cf3add1b3e88fb4b…,
                                                         источник /home/claude/wt-portable-site-cell-01/config/site-cells.json
    POST .../mcp list_registered_sites                -> HTTP 200, version=1, 23 записи, lordserials22.info есть
    POST .../mcp get_registered_site lordserials22.info -> HTTP 200, site_id=lords-05

## 2. Пакет: программы разбора, правки, проверки и приёмки

    python3 -m pytest tests/unit/test_srv_qwen_bridge_package.py -q     -> exit 0, 16 passed

Включает 4 негативных случая неожиданной конфигурации (нет сервиса, несколько
сетей, изменение уже применено, сети не объявлены) и 7 случаев подменённого
ответа (чужой host, 0 сайтов, иной отпечаток, иная версия, `read_only=false`,
иной домен, `isError`).

## 3. Правка на фактической форме compose — настоящим compose

    docker compose -f compose.new.yaml config -q                        -> exit 0
    docker compose -f compose.new.yaml config --format json             -> exit 0

Разрешённая зависимость после правки:

    {"site-factory-mcp-legacy": {"condition": "service_healthy", "required": true}}

Команда моста, как её разобрал compose: список из трёх элементов
(`sh`, `-c`, многострочный сценарий).

## 4. Исполнение многострочной команды SSH в контейнере

    docker run --rm --network none -v <stub>:/stub:ro --entrypoint sh redis:7-alpine -c <команда из compose>
    -> exit 0

Фактический набор аргументов, полученный подставным `ssh` (18 аргументов):

    [-N] [-i] [/channel/bridge_key] [-o] [UserKnownHostsFile=/channel/known_hosts]
    [-o] [BatchMode=yes] [-o] [StrictHostKeyChecking=yes] [-o] [ExitOnForwardFailure=yes]
    [-o] [ServerAliveInterval=20] [-o] [ServerAliveCountMax=3]
    [-L] [0.0.0.0:9000:127.0.0.1:9000] [sfbridge@45.131.182.225]

`apk` при наличии `ssh` не вызывается.

## 5. Пакет целиком на макете с настоящим docker compose

    python3 automation/local/mock-srv-qwen-package.py    -> exit 0, проверок 19, сбоев 0

Макет воспроизводит подтверждённую форму: сервис `site-factory-mcp` с
`container_name`, двумя alias и healthcheck; зависимый `seo-analytics-mcp` с
`condition: service_healthy, required: true` и ссылкой
`SITE_FACTORY_URL=http://site-factory-mcp:9000/mcp`; контейнер Open WebUI.

Подтверждено прогоном: `--check` не меняет файл и называет зависимость с
условием; полный проход снимает копию, переименовывает сервис, переводит
зависимость и ссылку, поднимает только нужное, пересоздаёт сервис со ссылкой;
при недостижимом канале приёмка отказывает и состояние возвращается — файл
байт в байт, имя `site-factory-mcp` у ровно одного контейнера (включая
остановленные), зависимый сервис и том данных на месте.

Два настоящих дефекта, найденных этим прогоном и исправленных:

1. имя проекта Compose определялось неявно (по каталогу) — `stop`/`rm` уходили в
   другой проект, `up` упирался в занятое `container_name`. Теперь имя берётся
   из метки `com.docker.compose.project`;
2. при откате оставался контейнер моста: он носит имя сервиса в DNS и с
   `restart: unless-stopped` поднимался снова, давая двойное разрешение имени.
   Откат снимает контейнеры моста и переименованного сервиса.

## 6. Приёмка пакета на НАСТОЯЩИХ ответах моста

    python3 -c "<блок PYACCEPT из пакета>" <каталог ответов> claude-control-01 2026-10-03.6 23 \
            4511cf3add1b3e88 config/site-cells.json lordserials22.info
    -> exit 0
    приёмка: host=claude-control-01 версия=2026-10-03.6 сайтов=23
             отпечаток=4511cf3add1b3e88… источник=config/site-cells.json
             домен lordserials22.info на месте

Ответы получены живым мостом (1398 / 29066 / 2312 байт). Проверка подтверждает
не только значения, но и ПУТИ к полям: `registry.sources.site_cells.path`,
`environment.instruction.version`.

## 7. Клиентская ветка без python3 — из контейнера

    docker run --rm --network host -v <req>:/req:ro --entrypoint sh redis:7-alpine -c \
      "wget -qO- --header='Content-Type: application/json' --post-file=/req/request.json http://127.0.0.1:9000/mcp"
    -> exit 0, 1398 байт, в ответе claude-control-01, sites=23, config/site-cells.json, 4511cf3add1b3e88

## 8. Дефект отчёта установщика «сайтов=4511»

    python3 -m pytest tests/unit/test_install_mcp_bridge_grant.py -q    -> exit 0, 6 passed

До исправления тест воспроизводил дефект дословно:
`реестр: сайтов=4511 отпечаток=4511cf3add1b3e88` — `sed` с жадным `.*` брал
цифры из `sites_digest`. Извлечение заменено разбором JSON; тот же шаблон
исправлен в `verify-channel-from-srv-qwen.sh`.

## 9. Доставка пакета на srv-qwen — исполнением того же конвейера

Передачи файлов на srv-qwen нет (ключ канала: `command="/bin/false"`,
`permitopen="127.0.0.1:9000"`; обратного доступа в inventory нет), поэтому пакет
вкладывается в инструкцию: gzip + base64.

    размер пакета : 42415 байт
    SHA-256       : 083647f974d210b03caddfc3402257e1c01d9a04837b92de17f94f62b1af225e
    вложение      : 12935 байт сжато -> 17248 символов base64, 227 строк

Прогнан ровно тот блок, который попадёт в терминал (heredoc → `base64 -d` →
`gzip -dc` → `tee`), с подменой путей на песочницу:

    bash <блок>                        -> exit 0, sha256sum -c: OK
    SHA-256 доставленного файла        -> 083647f974d210b03caddfc3402257e1c01d9a04837b92de17f94f62b1af225e (совпал)
    bash -n доставленного              -> exit 0
    bash <доставленный> --help         -> exit 0, 45 строк

Попутно исправлено: `--help` завершался кодом 141 (SIGPIPE от `head` под
`pipefail`); заменено на `sed -n`. После исправления пакет пересобран,
вложение перестроено, SHA-256 пересчитан, макет прогнан заново.

## Остаётся НЕ ПРОВЕРЕННЫМ

- приёмка из контейнера Open WebUI на srv-qwen (шаг 7 пакета): доступа к
  srv-qwen нет — `inventory/ssh-hosts.yaml` содержит `hosts: []`;
- вызов инструмента непосредственно в сессии Qwen;
- полная конфигурация `/opt/qwen/compose.yaml`;
- настоящий туннель из контейнера моста.
