# FACTS — только подтверждённые факты

Дата фиксации: 2026-08-21. Каждый факт снабжён способом проверки.
Всё, что не проверено в этой сессии, находится в `UNKNOWNS.md`, а не здесь.

## F1. Состояние репозитория и переданных материалов

| ID | Факт | Проверка |
|----|------|----------|
| F1.1 | Репозиторий `sbc-create/test` был полностью пуст: 0 коммитов, 0 файлов, только `.git`. | `git log --all` (пусто), `find . -not -path './.git/*'` → 0 записей |
| F1.2 | Пользовательских материалов по инфраструктуре, доменам, DLE, VK не передано ни одного файла. | `ls -la /home/user`, `find /home/user/test` |
| F1.3 | SSH-ключей и `known_hosts` в окружении нет: `~/.ssh` пуст. | `ls -la ~/.ssh` → только `.` и `..` |
| F1.4 | Переменных окружения с DNS/VK/DLE/deploy-реквизитами нет. Присутствуют только служебные токены среды (GITHUB_TOKEN, CLAUDE_*, AWS_*, CLOUDSDK_*), не относящиеся к целевой инфраструктуре. | `env \| cut -d= -f1 \| grep -iE 'ssh\|dns\|vk\|dle\|deploy\|token\|key\|secret\|host\|domain'` |
| F1.5 | Ранее существующих компонентов (DLE-модуль публикации, сервис анализа описаний, сервис разворачивания, сервис мониторинга) в переданном контуре нет — аудитировать нечего. | F1.1, F1.2 |

## F2. Окружение исполнения

| ID | Факт | Проверка |
|----|------|----------|
| F2.1 | Ubuntu 24.04.4 LTS, ядро 6.18.44, 4 CPU, 16 GB RAM, ~30 GB свободного диска. Контейнер эфемерный. | `artifacts/env-probe.txt` |
| F2.2 | Установлены: Python 3.11.15, PHP 8.4.19 (CLI), Node 22.22.2, npm 10.9.7, git 2.43, curl 8.5, jq 1.7, yq. | `python3 -V`, `php -v`, `node -v` … |
| F2.3 | PHP-расширения включают mysqli, pdo_mysql, pdo_sqlite, gd, intl, mbstring, curl, zip, opcache, sodium. | `php -m` |
| F2.4 | Ansible, nginx, mysql/mariadb-клиент, shellcheck, rsync **не установлены**. | `command -v` для каждого |
| F2.5 | Docker CLI установлен, но демон недоступен (`/var/run/docker.sock` отсутствует) → контейнерный пилот невозможен. | `docker info` → "failed to connect to the docker API" |
| F2.6 | PyPI и npm registry доступны (в `noProxy`), установка пакетов работает. | `pip3 install jsonschema pytest` → успех |

## F3. Сетевая политика (влияет на Mode A)

| ID | Факт | Проверка |
|----|------|----------|
| F3.1 | Исходящий HTTPS идёт через policy-enforcing egress proxy; TLS переустанавливается, CA — `/root/.ccr/ca-bundle.crt`. | `/root/.ccr/README.md`, `$HTTPS_PROXY/__agentproxy/status` |
| F3.2 | `code.claude.com` доступен (HTTP 200). | `curl -o /dev/null -w '%{http_code}'` |
| F3.3 | `dle-news.com`, `developers.google.com`, `yandex.ru`, `web.dev`, `playwright.dev`, `w3.org` **заблокированы** политикой организации: гейт отвечает 403 на CONNECT. | коды 000 у curl + `recentRelayFailures` со значением `connect_rejected: gateway answered 403 to CONNECT` |
| F3.4 | Обход политики не выполнялся: TLS-верификация не отключалась, HTTPS_PROXY не снимался, зеркала/пересказы вместо официальных источников не подставлялись. | `knowledge/SOURCE_REGISTRY.yaml` |

## F4. Claude Code (подтверждено официальной документацией, доступной в сессии)

| ID | Факт | Источник |
|----|------|----------|
| F4.1 | CLAUDE.md — это контекст, а не enforcement. Жёсткие запреты реализуются PreToolUse-хуками. | SRC-CC-MEMORY |
| F4.2 | Целевой размер CLAUDE.md — до 200 строк; свыше — падает адгезия. | SRC-CC-MEMORY |
| F4.3 | `.claude/rules/*.md` с frontmatter `paths:` грузятся только при работе с совпадающими файлами. | SRC-CC-MEMORY |
| F4.4 | Порядок permission-правил: deny > ask > allow; deny нельзя ослабить более узким allow. | SRC-CC-PERMISSIONS |
| F4.5 | Bash-правила матчатся отдельно для каждой подкоманды (`&&`, `\|\|`, `;`, `\|`, `&`, перевод строки). | SRC-CC-PERMISSIONS |
| F4.6 | Путевые правила вида `Write(path)`/`Glob(path)` не проверяются; нужны `Edit(path)`/`Read(path)`. | SRC-CC-PERMISSIONS |
| F4.7 | Обёртки `timeout, time, nice, nohup, stdbuf, command, builtin, xargs` срезаются перед матчингом; `npx`, `docker exec`, `devbox run` — нет, поэтому их нельзя разрешать префиксом. | SRC-CC-PERMISSIONS |
| F4.8 | PreToolUse-хук с exit 2 блокирует вызов до оценки permission rules, то есть сильнее любого allow. | SRC-CC-HOOKS |
| F4.9 | Формат решения хука: exit 0 + `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"…"}}`, либо exit 2 со stderr. | SRC-CC-HOOKS |
| F4.10 | Ключи sandbox: `sandbox.enabled`, `sandbox.failIfUnavailable`, `sandbox.allowUnsandboxedCommands`, `sandbox.excludedCommands`, `sandbox.filesystem.*`, `sandbox.network.allowedDomains`, `sandbox.credentials.{files,env}`. | SRC-CC-SANDBOX |
| F4.11 | Без `--bare` режим `claude -p` исполняет hooks и `.mcp.json` из каталога проекта без диалога доверия. | SRC-CC-HEADLESS |
| F4.12 | `--output-format json\|stream-json` + `--json-schema` дают машиночитаемый результат для worker'а. | SRC-CC-HEADLESS |

## F5. Утверждения пользователя, принятые как нормативные (официальный первоисточник заблокирован)

| ID | Утверждение | Статус |
|----|-------------|--------|
| F5.1 | Базовая версия — DataLife Engine 20.0, релиз 29.05.2026. | принято от пользователя; сверка с SRC-DLE-RELEASE-20 обязательна при открытии доступа |
| F5.2 | Одна лицензия DLE покрывает один домен второго уровня и его поддомены. | принято от пользователя; сверка с SRC-DLE-LICENSE обязательна. Реализовано как жёсткий гейт `BLOCKED_LICENSE` |
| F5.3 | DLE — проприетарный продукт; допустим только официальный лицензионный дистрибутив, переданный пользователем. | принято; реализовано запретом на скачивание дистрибутивов |
| F5.4 | Базовый источник видео — переданный лицензионный каталог VK / VK Видео; монетизация — только через согласованный контур VK/Adman/AdTech. | принято; реализовано как обязательные поля пакета и адаптеры без выдуманных методов |
