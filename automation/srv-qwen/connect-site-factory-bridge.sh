#!/usr/bin/env bash
# Единый пакет: коннектор Open WebUI начинает отвечать ИЗ ФАБРИКИ.
# Запускать НА srv-qwen (администратором):
#
#   sudo bash connect-site-factory-bridge.sh            # проверка + изменение + приёмка
#   sudo bash connect-site-factory-bridge.sh --check     # только проверка, без изменений
#   sudo bash connect-site-factory-bridge.sh --rollback  # вернуть состояние из копии
#
# Что делает и почему именно так
# ------------------------------
# URL коннектора не меняется: `http://site-factory-mcp:9000/mcp`. Меняется то,
# КТО отвечает по этому имени в сети контейнеров.
#
# ПЕРЕНОСА `aliases` НЕДОСТАТОЧНО. В Compose имя сервиса САМО является именем в
# DNS сети проекта: пока сервис называется `site-factory-mcp`, это имя
# разрешается в него независимо от списка `aliases`. Добавить то же имя мосту —
# значит получить ДВА адреса на одно имя и половину вызовов в прежний пустой
# реестр. Поэтому:
#
#   1. прежний сервис переименовывается в `site-factory-mcp-legacy`
#      (образ, `container_name`, томa и healthcheck сохраняются — данные не
#      затрагиваются), а одноимённый лишний alias из него убирается;
#   2. зависимости на него (`depends_on`, в том числе
#      `seo-analytics-mcp: {condition: service_healthy, required: true}`)
#      перенаправляются на новое имя С СОХРАНЕНИЕМ условия и обязательности;
#   3. ссылки вида `http://site-factory-mcp:9000` в переменных и командах
#      ДРУГИХ сервисов тоже переводятся на `site-factory-mcp-legacy`: их
#      поведение сохраняется прежним, на мост переходит только коннектор;
#   4. сервис `site-factory-mcp` создаётся заново — это канал SSH к мосту
#      фабрики. Проброс, и ничего больше: кода фабрики в контейнере нет.
#
# Любая неожиданность в конфигурации — остановка ДО изменений с точной
# причиной. Правка файла идёт только после полной проверки формы, резервная
# копия снимается до неё, а при отказе приёмки состояние возвращается
# автоматически.
#
# Секреты: закрытый ключ канала не читается, не печатается и не копируется —
# он остаётся в /opt/qwen/site-factory-channel и монтируется только для чтения.
# Ограничения SSH не ослабляются: разрешение на стороне фабрики выдано одной
# учётной записи `sfbridge` ровно на `127.0.0.1:9000`.
set -Eeuo pipefail

COMPOSE_FILE="/opt/qwen/compose.yaml"
CHANNEL_DIR="/opt/qwen/site-factory-channel"
BRIDGE_IMAGE="alpine:3.20"
FACTORY_TARGET="sfbridge@45.131.182.225"
SERVICE_NAME="site-factory-mcp"
LEGACY_NAME="site-factory-mcp-legacy"
WEBUI_CONTAINER=""
MODE="apply"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_ROOT="/opt/qwen/backups"

#: Ожидаемое от фабрики. Значения снимаются с работающего моста и сверяются
#: приёмкой: совпадение числа, отпечатка и источника отличает фабрику от
#: любого другого ответчика на том же порту.
EXPECT_HOST="claude-control-01"
EXPECT_VERSION="2026-10-03.6"
EXPECT_SITES="23"
EXPECT_DIGEST16="4511cf3add1b3e88"
EXPECT_SOURCE="config/site-cells.json"
CONTROL_DOMAIN="lordserials22.info"

while [ $# -gt 0 ]; do
  case "$1" in
    --compose-file) COMPOSE_FILE="$2"; shift 2 ;;
    --webui-container) WEBUI_CONTAINER="$2"; shift 2 ;;
    --channel-dir) CHANNEL_DIR="$2"; shift 2 ;;
    --bridge-image) BRIDGE_IMAGE="$2"; shift 2 ;;
    # Цель канала. Значение по умолчанию — фабрика; параметр существует для
    # проверки пакета на макете, где обращаться к живому хосту незачем.
    --factory-target) FACTORY_TARGET="$2"; shift 2 ;;
    --backup-root) BACKUP_ROOT="$2"; shift 2 ;;
    --check) MODE="check"; shift ;;
    --rollback) MODE="rollback"; shift ;;
    --apply) MODE="apply"; shift ;;
    -h|--help) grep '^#' "$0" | head -45; exit 0 ;;
    *) printf 'неизвестный аргумент: %s\n' "$1" >&2; exit 2 ;;
  esac
done

log()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
ok()   { printf '   \033[32mOK\033[0m   %s\n' "$*"; }
info() { printf '        %s\n' "$*"; }
die()  { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

COMPOSE_DIR="$(cd "$(dirname "$COMPOSE_FILE")" && pwd)"
BACKUP_DIR="${BACKUP_ROOT}/site-factory-bridge-${STAMP}"
#: Имя проекта Compose. Пустое значение означает «определить по работающему
#: контейнеру» — см. шаг 0. Полагаться на неявное имя (каталог файла) нельзя:
#: стек мог быть создан с `-p`, с `COMPOSE_PROJECT_NAME` или с ключом `name:`
#: в самом файле. Тогда `stop`/`rm` уходят в ДРУГОЙ проект, ничего не находят,
#: а `up` упирается в занятое `container_name` — проверено на макете.
PROJECT=""
dc() {
  if [ -n "$PROJECT" ]; then
    docker compose -p "$PROJECT" --project-directory "$COMPOSE_DIR" -f "$COMPOSE_FILE" "$@"
  else
    docker compose --project-directory "$COMPOSE_DIR" -f "$COMPOSE_FILE" "$@"
  fi
}

# Снять ВСЕ контейнеры данного сервиса в этом проекте. Нужно и при откате:
# контейнер моста носит имя сервиса в DNS сети и при `restart: unless-stopped`
# поднимается снова. Если его оставить, после возврата состояния имя
# разрешалось бы и в мост, и в восстановленный прежний сервис — ровно то
# двойное разрешение, которого нельзя допускать. Проверено на макете:
# осиротевший контейнер моста там оставался после отката.
drop_service_containers() {
  if [ -n "$PROJECT" ]; then
    docker ps -a --filter "label=com.docker.compose.project=${PROJECT}" \
                 --filter "label=com.docker.compose.service=$1" --format '{{.ID}}'
  else
    docker ps -a --filter "label=com.docker.compose.service=$1" --format '{{.ID}}'
  fi | while read -r cid; do
    if [ -n "$cid" ]; then docker rm -f "$cid" >/dev/null 2>&1 || true; fi
  done
}

# Вызов MCP ИЗНУТРИ контейнера Open WebUI — тем же путём, которым ходит
# коннектор. Клиент выбирается по тому, что в контейнере есть: python3, curl
# или busybox wget. Тело запроса передаётся файлом, а не в командной строке:
# иначе кавычки JSON ломаются о слои оболочек (docker exec -> sh -c).
call_in_webui() {
  printf '%s' "$1" | docker exec -i "$WEBUI_CONTAINER" sh -c "
cat > /tmp/sfb-request.json
if command -v python3 >/dev/null 2>&1; then
  python3 -c \"
import json, sys, urllib.request
body = open('/tmp/sfb-request.json','rb').read()
req = urllib.request.Request('http://${SERVICE_NAME}:9000${2:-/mcp}', data=body,
                             headers={'Content-Type': 'application/json'})
sys.stdout.write(urllib.request.urlopen(req, timeout=120).read().decode())
\"
elif command -v curl >/dev/null 2>&1; then
  curl -sS -m 120 -X POST -H 'Content-Type: application/json' \
       --data-binary @/tmp/sfb-request.json 'http://${SERVICE_NAME}:9000${2:-/mcp}'
else
  wget -qO- --header='Content-Type: application/json' \
       --post-file=/tmp/sfb-request.json 'http://${SERVICE_NAME}:9000${2:-/mcp}'
fi
rc=\$?
rm -f /tmp/sfb-request.json
exit \$rc
"
}

# Простой GET тем же способом: для /healthz, где тела запроса нет.
get_in_webui() {
  docker exec "$WEBUI_CONTAINER" sh -c "
if command -v python3 >/dev/null 2>&1; then
  python3 -c \"
import sys, urllib.request
sys.stdout.write(urllib.request.urlopen('http://${SERVICE_NAME}:9000$1', timeout=10).read().decode())
\"
elif command -v curl >/dev/null 2>&1; then
  curl -sS -m 10 'http://${SERVICE_NAME}:9000$1'
else
  wget -qO- 'http://${SERVICE_NAME}:9000$1'
fi
"
}

# --- 0. Предпосылки ---------------------------------------------------------
log "0. окружение и предпосылки"
# Проверяются ПРАВА НА КОНКРЕТНЫЕ ПУТИ, а не `id -u = 0`: под root сценарий
# работает, но важно не звание, а возможность записать файл, создать каталог
# копий и обратиться к docker. Такая проверка называет точную причину отказа
# и позволяет прогнать пакет на макете, не выдавая ему лишних прав.
command -v docker >/dev/null || die "нет docker"
docker compose version >/dev/null 2>&1 || die "нет плагина docker compose"
docker info >/dev/null 2>&1 \
  || die "docker недоступен этой учётной записи: нужен root или членство в группе docker"
[ -f "$COMPOSE_FILE" ] || die "нет файла $COMPOSE_FILE"
[ -w "$COMPOSE_FILE" ] || die "нет права записи в $COMPOSE_FILE (запустите через sudo)"
[ -w "$(dirname "$COMPOSE_FILE")" ] \
  || die "нет права записи в $(dirname "$COMPOSE_FILE") — копию рядом положить не получится"
install -d -m 0750 "$BACKUP_ROOT" 2>/dev/null \
  || die "не удаётся создать каталог копий $BACKUP_ROOT"
info "docker $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo '?')"
info "compose $(docker compose version --short 2>/dev/null || echo '?')"

# Имя проекта берётся у РАБОТАЮЩЕГО контейнера, а не из имени каталога.
# В шаблонах `docker ps` метки доступны функцией `.Label "ключ"`:
# `index .Labels "ключ"` там не работает — `.Labels` это строка, а не словарь.
PROJECTS="$(docker ps -a --filter "label=com.docker.compose.service=${SERVICE_NAME}" \
  --format '{{.Label "com.docker.compose.project"}}' | sort -u | grep -v '^$' || true)"
PROJECT_COUNT="$(printf '%s\n' "$PROJECTS" | grep -c . || true)"
if [ "$PROJECT_COUNT" -gt 1 ]; then
  die "сервис ${SERVICE_NAME} найден в нескольких проектах Compose ($(printf '%s' "$PROJECTS" | tr '\n' ' ')) — остановлено, нужен ручной разбор"
fi
if [ "$PROJECT_COUNT" = 1 ]; then
  PROJECT="$PROJECTS"
  info "проект Compose: ${PROJECT} (определён по метке работающего контейнера)"
else
  info "работающего контейнера ${SERVICE_NAME} не найдено: имя проекта оставлено на усмотрение compose"
fi
dc config -q 2>/tmp/sfb-config.err \
  || die "ИСХОДНЫЙ compose не проходит проверку, менять нельзя: $(head -3 /tmp/sfb-config.err | tr '\n' ' ')"
ok "исходная конфигурация compose валидна"

CONFIG_JSON="$(mktemp)"
trap 'rm -f "$CONFIG_JSON" /tmp/sfb-config.err' EXIT
dc config --format json > "$CONFIG_JSON" 2>/tmp/sfb-config.err \
  || die "docker compose config --format json не поддерживается этой версией: $(head -2 /tmp/sfb-config.err | tr '\n' ' ')"
ok "полная конфигурация получена в машинном виде ($(wc -c < "$CONFIG_JSON") байт)"

if [ "$MODE" = rollback ]; then
  LAST="$(ls -1d "${BACKUP_ROOT}"/site-factory-bridge-* 2>/dev/null | tail -1 || true)"
  [ -n "$LAST" ] || die "нет ни одной резервной копии в ${BACKUP_ROOT}"
  log "откат из копии $LAST"
  [ -f "${LAST}/compose.yaml" ] || die "в копии нет compose.yaml"
  cp -a "$COMPOSE_FILE" "${COMPOSE_FILE}.before-rollback.${STAMP}"
  cp -a "${LAST}/compose.yaml" "$COMPOSE_FILE"
  dc config -q || die "восстановленный compose невалиден — файл оставлен, разберитесь вручную"
  # Мост и переименованный сервис снимаются: в восстановленном файле их нет, а
  # контейнер моста носит имя сервиса в DNS и поднялся бы снова.
  drop_service_containers "$SERVICE_NAME"
  drop_service_containers "$LEGACY_NAME"
  dc up -d --no-deps "$SERVICE_NAME" || die "прежний сервис не поднялся"
  ok "файл и прежний сервис восстановлены; копия изменённого: ${COMPOSE_FILE}.before-rollback.${STAMP}"
  exit 0
fi

# --- 1. Разбор фактической конфигурации -------------------------------------
# Решения принимаются по машинному виду конфигурации, а не по предположениям о
# тексте: имена сервисов, сеть, зависимости и ссылки на имя хоста вычисляются.
log "1. фактическая конфигурация: что именно будет изменено"
FACTS="$(python3 - "$CONFIG_JSON" "$SERVICE_NAME" "$LEGACY_NAME" <<'PYFACTS'
import json
import sys

path, service, legacy = sys.argv[1], sys.argv[2], sys.argv[3]
cfg = json.load(open(path, encoding="utf-8"))
services = cfg.get("services") or {}


def fail(why):
    sys.stderr.write(why + "\n")
    raise SystemExit(3)


if service not in services:
    fail("в compose нет сервиса %s — это не та конфигурация" % service)
if legacy in services:
    fail("сервис %s уже существует: изменение, похоже, уже применялось" % legacy)

target = services[service]
nets = target.get("networks") or {}
if not isinstance(nets, dict) or not nets:
    fail("у сервиса %s не объявлены сети — мост некуда подключить" % service)
net_name = sorted(nets)[0]
if len(nets) > 1:
    fail("сервис %s в нескольких сетях (%s): остановлено, нужен ручной разбор"
         % (service, ", ".join(sorted(nets))))

aliases = ((nets.get(net_name) or {}).get("aliases") or [])
dependents = []
for name, body in services.items():
    deps = body.get("depends_on") or {}
    if isinstance(deps, dict) and service in deps:
        cond = (deps[service] or {}).get("condition", "")
        req = (deps[service] or {}).get("required", True)
        dependents.append("%s:%s:%s" % (name, cond, req))
    elif isinstance(deps, list) and service in deps:
        dependents.append("%s:list:True" % name)

hostrefs = []
for name, body in services.items():
    if name == service:
        continue
    env = body.get("environment") or {}
    pairs = env.items() if isinstance(env, dict) else [("", v) for v in env]
    for key, value in pairs:
        if value and service in str(value):
            hostrefs.append("%s/env/%s" % (name, key))
    cmd = body.get("command")
    if cmd and service in json.dumps(cmd, ensure_ascii=False):
        hostrefs.append("%s/command" % name)

print(json.dumps({
    "network": net_name,
    "aliases": aliases,
    "container_name": target.get("container_name") or "",
    "image": target.get("image") or "",
    "volumes": len(target.get("volumes") or []),
    "dependents": dependents,
    "hostrefs": hostrefs,
    "services": sorted(services),
}, ensure_ascii=False))
PYFACTS
)" || die "конфигурация не соответствует ожиданиям — ничего не изменено (причина выше)"

NETWORK="$(printf '%s' "$FACTS"  | python3 -c 'import json,sys; print(json.load(sys.stdin)["network"])')"
CONTAINER="$(printf '%s' "$FACTS" | python3 -c 'import json,sys; print(json.load(sys.stdin)["container_name"])')"
DEPENDENTS="$(printf '%s' "$FACTS" | python3 -c 'import json,sys; print(" ".join(json.load(sys.stdin)["dependents"]))')"
HOSTREFS="$(printf '%s' "$FACTS"  | python3 -c 'import json,sys; print(" ".join(json.load(sys.stdin)["hostrefs"]))')"
ALIASES="$(printf '%s' "$FACTS"   | python3 -c 'import json,sys; print(",".join(json.load(sys.stdin)["aliases"]))')"
info "сеть=${NETWORK} контейнер=${CONTAINER:-<без имени>} aliases=[${ALIASES}]"
info "зависимости на ${SERVICE_NAME}: ${DEPENDENTS:-нет}"
info "ссылки на это имя у других сервисов: ${HOSTREFS:-нет}"
ok "конфигурация разобрана, неожиданностей нет"

# --- 2. Канал и образ -------------------------------------------------------
log "2. канал к фабрике"
[ -d "$CHANNEL_DIR" ] || die "нет каталога канала $CHANNEL_DIR"
[ -r "${CHANNEL_DIR}/bridge_key" ] || die "нет закрытого ключа ${CHANNEL_DIR}/bridge_key"
[ -r "${CHANNEL_DIR}/known_hosts" ] || die "нет проверенного ${CHANNEL_DIR}/known_hosts"
# Печатается только отпечаток — закрытая часть ключа не выводится.
info "отпечаток ключа канала: $(ssh-keygen -lf "${CHANNEL_DIR}/bridge_key" 2>/dev/null | awk '{print $2}' || echo 'не прочитан')"
grep -q '45.131.182.225' "${CHANNEL_DIR}/known_hosts" \
  || die "в known_hosts нет записи для 45.131.182.225 — закрепите ключ сервера перед подключением"
ok "ключ и закреплённый known_hosts на месте"

docker image inspect "$BRIDGE_IMAGE" >/dev/null 2>&1 || {
  log "   образ ${BRIDGE_IMAGE} отсутствует — загрузка"
  docker pull "$BRIDGE_IMAGE" >/dev/null 2>&1 \
    || die "образ ${BRIDGE_IMAGE} недоступен: нет доступа к реестру. Загрузите образ и повторите"
}
ok "образ ${BRIDGE_IMAGE} доступен локально"

if [ -z "$WEBUI_CONTAINER" ]; then
  WEBUI_CONTAINER="$(docker ps --format '{{.Names}}' | grep -i -m1 -e open-webui -e openwebui || true)"
fi
[ -n "$WEBUI_CONTAINER" ] \
  || die "не найден контейнер Open WebUI: укажите --webui-container ИМЯ (docker ps)"
WEBUI_CLIENT="$(docker exec "$WEBUI_CONTAINER" sh -c \
  'command -v python3 || command -v curl || command -v wget' 2>/dev/null | head -1 || true)"
[ -n "$WEBUI_CLIENT" ] \
  || die "в контейнере ${WEBUI_CONTAINER} нет ни python3, ни curl, ни wget — приёмку изнутри выполнить нечем"
ok "приёмка пойдёт из ${WEBUI_CONTAINER} через ${WEBUI_CLIENT}"

if [ "$MODE" = check ]; then
  log "режим --check: изменений не делалось"
  exit 0
fi

# --- 3. Резервная копия -----------------------------------------------------
log "3. резервная копия до изменений"
install -d -m 0750 "$BACKUP_DIR"
cp -a "$COMPOSE_FILE" "${BACKUP_DIR}/compose.yaml"
cp -a "$CONFIG_JSON" "${BACKUP_DIR}/compose-resolved-before.json"
dc ps --format json > "${BACKUP_DIR}/ps-before.json" 2>/dev/null || true
docker network inspect "$NETWORK" > "${BACKUP_DIR}/network-before.json" 2>/dev/null || true
# Перечень инструментов ПРЕЖНЕГО ответчика: по нему видно, что именно исчезает
# из сессии Qwen после переключения имени. Снимается ДО изменения.
call_in_webui '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  > "${BACKUP_DIR}/legacy-tools-list.json" 2>/dev/null || true
info "инструменты прежнего ответчика сохранены в ${BACKUP_DIR}/legacy-tools-list.json"
ok "копия: ${BACKUP_DIR}"

# --- 4. Точечное изменение файла --------------------------------------------
log "4. правка ${COMPOSE_FILE} (переименование + зависимости + мост)"
NEW_FILE="$(mktemp)"
python3 - "$COMPOSE_FILE" "$NEW_FILE" "$SERVICE_NAME" "$LEGACY_NAME" "$NETWORK" \
         "$CHANNEL_DIR" "$BRIDGE_IMAGE" "$FACTORY_TARGET" <<'PYEDIT'
"""Точечная правка compose БЕЗ сторонних библиотек и без переписывания файла.

Каждый шаг обязан найти ровно то, что ожидает; иначе ничего не записывается и
причина называется строкой. Так неожиданная конфигурация останавливает работу
ДО изменений, а не после.
"""
import re
import sys

src, dst, service, legacy, network, channel, image, target = sys.argv[1:9]
lines = open(src, encoding="utf-8").read().splitlines()


def fail(why):
    sys.stderr.write("правка не выполнена: %s\n" % why)
    raise SystemExit(4)


def indent_of(line):
    return len(line) - len(line.lstrip(" "))


# --- границы блока services и отступ ключей сервисов
top = [i for i, s in enumerate(lines) if re.match(r"^services:\s*$", s)]
if len(top) != 1:
    fail("ожидался ровно один ключ `services:` на верхнем уровне, найдено %d" % len(top))
start = top[0]
end = len(lines)
for i in range(start + 1, len(lines)):
    if lines[i].strip() and indent_of(lines[i]) == 0 and not lines[i].lstrip().startswith("#"):
        end = i
        break
body = range(start + 1, end)
key_re = re.compile(r"^(\s+)([A-Za-z0-9_.-]+):\s*$")
indents = {indent_of(lines[i]) for i in body
           if key_re.match(lines[i]) and lines[i].strip() and not lines[i].lstrip().startswith("#")}
if not indents:
    fail("внутри `services:` не найдено ни одного ключа сервиса")
svc_indent = min(indents)

# --- блок целевого сервиса
target_line = None
for i in body:
    m = key_re.match(lines[i])
    if m and indent_of(lines[i]) == svc_indent and m.group(2) == service:
        target_line = i
        break
if target_line is None:
    fail("не найдена строка сервиса `%s:` с отступом %d" % (service, svc_indent))
block_end = end
for i in range(target_line + 1, end):
    if lines[i].strip() and indent_of(lines[i]) <= svc_indent and not lines[i].lstrip().startswith("#"):
        block_end = i
        break

# --- 1) лишний alias, равный имени сервиса: имя и так разрешается в сервис
removed_alias = 0
for i in range(target_line + 1, block_end):
    if re.match(r"^\s*-\s+%s\s*$" % re.escape(service), lines[i]):
        lines[i] = None
        removed_alias += 1
lines = [s for s in lines if s is not None]

# повторный расчёт после удаления
def find_service_line(name):
    for i, s in enumerate(lines):
        m = key_re.match(s or "")
        if m and indent_of(s) == svc_indent and m.group(2) == name:
            return i
    return None


target_line = find_service_line(service)
if target_line is None:
    fail("строка сервиса потеряна после удаления alias — изменения не записаны")

# --- 2) переименование сервиса
lines[target_line] = "%s%s:" % (" " * svc_indent, legacy)

# --- 3) зависимости и ссылки на имя хоста
dep_long = re.compile(r"^(\s*)%s:\s*$" % re.escape(service))
dep_short = re.compile(r"^(\s*)-\s+%s\s*$" % re.escape(service))
renamed_deps = 0
renamed_hostrefs = 0
inside_depends = False
depends_indent = 0
for i, s in enumerate(lines):
    if s is None:
        continue
    if re.match(r"^\s*depends_on:\s*$", s):
        inside_depends = True
        depends_indent = indent_of(s)
        continue
    if inside_depends:
        if s.strip() and indent_of(s) <= depends_indent:
            inside_depends = False
        else:
            m = dep_long.match(s) or dep_short.match(s)
            if m:
                lines[i] = s.replace(service, legacy, 1)
                renamed_deps += 1
                continue
    # Ссылка на имя хоста в переменной или команде: URL или host:port.
    if i != target_line and re.search(r"(//|@|\s|\"|')%s(:\d+|/|\"|'|\s|$)" % re.escape(service), s):
        if "depends_on" in s or s.strip().startswith("#"):
            continue
        if re.search(r"%s:9000|//%s" % (re.escape(service), re.escape(service)), s):
            lines[i] = s.replace(service, legacy)
            renamed_hostrefs += 1

# --- 4) блок моста в конец секции services
bridge = """{i}{service}:
{i}{i}# Канал к мосту MCP фабрики на claude-control-01. Кода фабрики здесь нет:
{i}{i}# только проброс SSH. Имя сервиса само является именем в DNS сети, и по
{i}{i}# нему коннектор Open WebUI обращается к http://{service}:9000/mcp.
{i}{i}image: {image}
{i}{i}restart: unless-stopped
{i}{i}volumes:
{i}{i}{i}- {channel}:/channel:ro
{i}{i}# Список, а не одна строка: при сворачивании многострочной команды YAML
{i}{i}# легко получить не тот набор аргументов. `exec` оставляет ssh процессом
{i}{i}# номер 1, иначе остановка контейнера не доходит до туннеля.
{i}{i}command:
{i}{i}{i}- sh
{i}{i}{i}- -c
{i}{i}{i}- |
{i}{i}{i}{i}command -v ssh >/dev/null 2>&1 || apk add --no-cache openssh-client >/dev/null
{i}{i}{i}{i}exec ssh -N \\
{i}{i}{i}{i}  -i /channel/bridge_key \\
{i}{i}{i}{i}  -o UserKnownHostsFile=/channel/known_hosts \\
{i}{i}{i}{i}  -o BatchMode=yes \\
{i}{i}{i}{i}  -o StrictHostKeyChecking=yes \\
{i}{i}{i}{i}  -o ExitOnForwardFailure=yes \\
{i}{i}{i}{i}  -o ServerAliveInterval=20 \\
{i}{i}{i}{i}  -o ServerAliveCountMax=3 \\
{i}{i}{i}{i}  -L 0.0.0.0:9000:127.0.0.1:9000 \\
{i}{i}{i}{i}  {target}
{i}{i}networks:
{i}{i}{i}{network}:
{i}{i}{i}{i}aliases:
{i}{i}{i}{i}{i}- {service}-bridge
{i}{i}# Проверяется мост на ТОЙ стороне, а не живость контейнера: канал может
{i}{i}# стоять, а служба фабрики лежать.
{i}{i}healthcheck:
{i}{i}{i}test: ["CMD", "sh", "-c", "wget -qO- http://127.0.0.1:9000/healthz | grep -q '\\"ready\\": true'"]
{i}{i}{i}interval: 30s
{i}{i}{i}timeout: 5s
{i}{i}{i}retries: 3
{i}{i}{i}start_period: 40s
""".format(i=" " * svc_indent, service=service, image=image, channel=channel,
           network=network, target=target)

# конец секции services после всех правок
section_end = len(lines)
seen_services = False
for i, s in enumerate(lines):
    if re.match(r"^services:\s*$", s or ""):
        seen_services = True
        continue
    if seen_services and (s or "").strip() and indent_of(s) == 0 and not s.lstrip().startswith("#"):
        section_end = i
        break
lines = lines[:section_end] + bridge.rstrip("\n").split("\n") + lines[section_end:]

if removed_alias > 1:
    fail("alias %s встречался %d раз — остановлено" % (service, removed_alias))
open(dst, "w", encoding="utf-8").write("\n".join(lines) + "\n")
sys.stderr.write("правка: alias убран=%d, зависимостей перенаправлено=%d, "
                 "ссылок на имя хоста исправлено=%d\n"
                 % (removed_alias, renamed_deps, renamed_hostrefs))
PYEDIT
[ -s "$NEW_FILE" ] || die "правка не дала результата — файл не изменён"

# --- 5. Проверка новой конфигурации ДО применения ---------------------------
log "5. проверка новой конфигурации"
cp -a "$NEW_FILE" "${BACKUP_DIR}/compose-candidate.yaml"
CANDIDATE_DIR="$(mktemp -d)"
cp -a "$NEW_FILE" "${CANDIDATE_DIR}/compose.yaml"
if ! docker compose --project-directory "$COMPOSE_DIR" -f "${CANDIDATE_DIR}/compose.yaml" config -q 2>/tmp/sfb-config.err; then
  rm -rf "$CANDIDATE_DIR"
  die "новая конфигурация невалидна, исходный файл НЕ ТРОНУТ: $(head -3 /tmp/sfb-config.err | tr '\n' ' ')"
fi
docker compose --project-directory "$COMPOSE_DIR" -f "${CANDIDATE_DIR}/compose.yaml" \
  config --format json > "${BACKUP_DIR}/compose-resolved-after.json"
python3 - "${BACKUP_DIR}/compose-resolved-after.json" "$SERVICE_NAME" "$LEGACY_NAME" \
         "$NETWORK" "$CONTAINER" <<'PYCHECK'
import json
import sys

path, service, legacy, network, container = sys.argv[1:6]
cfg = json.load(open(path, encoding="utf-8"))
services = cfg.get("services") or {}
problems = []

if service not in services:
    problems.append("нет сервиса %s" % service)
if legacy not in services:
    problems.append("нет переименованного %s" % legacy)

# Имя коннектора обязано разрешаться РОВНО в один сервис: имя сервиса плюс
# aliases. Два источника одного имени — половина вызовов в прежний реестр.
owners = []
for name, body in services.items():
    if name == service:
        owners.append(name)
        continue
    for net, cfg_net in (body.get("networks") or {}).items():
        if service in ((cfg_net or {}).get("aliases") or []):
            owners.append("%s/alias" % name)
if sorted(owners) != [service]:
    problems.append("имя %s разрешается в: %s" % (service, ", ".join(sorted(owners)) or "никуда"))

old = services.get(legacy) or {}
if container and old.get("container_name") != container:
    problems.append("у %s изменилось container_name: %r" % (legacy, old.get("container_name")))

bridge = services.get(service) or {}
if network not in (bridge.get("networks") or {}):
    problems.append("мост не подключён к сети %s" % network)

for name, body in services.items():
    deps = body.get("depends_on") or {}
    if isinstance(deps, dict) and service in deps:
        problems.append("%s всё ещё зависит от %s вместо %s" % (name, service, legacy))

if problems:
    sys.stderr.write("новая конфигурация не годится:\n  " + "\n  ".join(problems) + "\n")
    raise SystemExit(5)
print("проверка новой конфигурации пройдена: имя %s принадлежит только мосту" % service)
PYCHECK
rm -rf "$CANDIDATE_DIR"
ok "новая конфигурация валидна и имя принадлежит только мосту"

# --- 6. Применение ----------------------------------------------------------
# Прежний контейнер снимается ДО правки файла: у него фиксированное
# container_name, и новый сервис под тем же именем иначе не создастся.
log "6. применение"
restore() {
  printf '\033[31m[x]\033[0m %s\n' "$1" >&2
  log "возврат состояния из ${BACKUP_DIR}"
  cp -a "${BACKUP_DIR}/compose.yaml" "$COMPOSE_FILE"
  drop_service_containers "$SERVICE_NAME"
  drop_service_containers "$LEGACY_NAME"
  [ -n "$CONTAINER" ] && docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  if dc up -d --no-deps "$SERVICE_NAME" >/dev/null 2>&1; then
    ok "прежний сервис ${SERVICE_NAME} восстановлен"
  else
    printf '   не удалось поднять прежний сервис — разберитесь вручную\n'
  fi
  OWNERS_AFTER="$(docker ps --format '{{.Names}}' | while read -r c; do
    if docker inspect "$c" --format \
        "{{range \$k, \$v := .NetworkSettings.Networks}}{{range \$v.Aliases}}{{.}} {{end}}{{end}}" \
        2>/dev/null | tr ' ' '\n' | grep -qx "$SERVICE_NAME"; then printf '%s ' "$c"; fi
  done)"
  info "после возврата имя ${SERVICE_NAME} у: ${OWNERS_AFTER:-никого}"
  exit 1
}

dc stop "$SERVICE_NAME" >/dev/null 2>&1 || true
dc rm -f "$SERVICE_NAME" >/dev/null 2>&1 || true
ok "прежний контейнер остановлен и снят (томa и данные не затронуты)"

cp -a "$NEW_FILE" "$COMPOSE_FILE"
rm -f "$NEW_FILE"
ok "файл заменён; копия исходного — ${BACKUP_DIR}/compose.yaml"

dc up -d --no-deps "$LEGACY_NAME" || restore "переименованный прежний сервис не поднялся"
dc up -d --no-deps "$SERVICE_NAME" || restore "мост не поднялся"
ok "поднято только нужное: ${LEGACY_NAME} и ${SERVICE_NAME}"

# Сервисы, которые ссылались на имя хоста, пересоздаются: иначе в них остаётся
# прежнее значение переменной и они обратятся к мосту вместо прежней службы.
if [ -n "$HOSTREFS" ]; then
  for ref in $HOSTREFS; do
    svc="${ref%%/*}"
    dc up -d --no-deps "$svc" >/dev/null 2>&1 \
      && info "пересоздан ${svc} (в нём была ссылка на имя ${SERVICE_NAME})" \
      || info "ВНИМАНИЕ: ${svc} пересоздать не удалось"
  done
fi

log "   ожидание готовности моста"
BRIDGE_READY=no
ATTEMPT=0
while [ "$ATTEMPT" -lt 30 ]; do
  ATTEMPT=$((ATTEMPT + 1))
  if get_in_webui /healthz 2>/dev/null | grep -q '"ready": true'; then
    BRIDGE_READY=yes
    break
  fi
  sleep 2
done
[ "$BRIDGE_READY" = yes ] || restore "мост не отвечает на /healthz из контейнера ${WEBUI_CONTAINER} за 60 с"
ok "мост отвечает из контейнера Open WebUI"

# --- 7. Приёмка настоящими вызовами MCP -------------------------------------
# HTTP 200 и healthy приёмкой не считаются: проверяются ТРИ инструмента,
# окружение, версия инструкции, источник и отпечаток реестра, число сайтов и
# контрольный домен. Вызовы делаются ИЗ контейнера Open WebUI — тем же путём,
# которым ходит коннектор.
log "7. приёмка: настоящие вызовы MCP из контейнера Open WebUI"
ANSWERS="$(mktemp -d)"
call_in_webui '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"system_readiness","arguments":{}}}' \
  > "${ANSWERS}/system_readiness.json" || restore "system_readiness не ответил"
call_in_webui '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_registered_sites","arguments":{}}}' \
  > "${ANSWERS}/list_registered_sites.json" || restore "list_registered_sites не ответил"
call_in_webui "{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{\"name\":\"get_registered_site\",\"arguments\":{\"site\":\"${CONTROL_DOMAIN}\"}}}" \
  > "${ANSWERS}/get_registered_site.json" || restore "get_registered_site не ответил"
cp -a "${ANSWERS}"/*.json "$BACKUP_DIR"/ 2>/dev/null || true

if ! python3 - "$ANSWERS" "$EXPECT_HOST" "$EXPECT_VERSION" "$EXPECT_SITES" \
       "$EXPECT_DIGEST16" "$EXPECT_SOURCE" "$CONTROL_DOMAIN" <<'PYACCEPT'
import json
import pathlib
import sys

каталог = pathlib.Path(sys.argv[1])
host, version, sites, digest16, source, domain = sys.argv[2:8]
плохо = []


def payload(имя):
    envelope = json.loads((каталог / имя).read_text(encoding="utf-8"))
    if "error" in envelope:
        плохо.append("%s: ошибка %s" % (имя, envelope["error"]))
        return {}
    content = (envelope.get("result") or {}).get("content") or []
    if not content:
        плохо.append("%s: пустой ответ инструмента" % имя)
        return {}
    if envelope.get("result", {}).get("isError"):
        плохо.append("%s: инструмент вернул ошибку: %s" % (имя, content[0].get("text", "")[:160]))
        return {}
    try:
        return json.loads(content[0]["text"])
    except Exception as err:
        плохо.append("%s: содержимое не JSON (%s)" % (имя, err))
        return {}


готовность = payload("system_readiness.json")
окружение = готовность.get("environment") or {}
реестр = готовность.get("registry") or {}
источник = ((реестр.get("sources") or {}).get("site_cells") or {}).get("path") or ""
if окружение.get("host") != host:
    плохо.append("host=%r, ожидался %r — отвечает не фабрика" % (окружение.get("host"), host))
if ((окружение.get("instruction") or {}).get("version")) != version:
    плохо.append("версия инструкции=%r, ожидалась %r"
                 % ((окружение.get("instruction") or {}).get("version"), version))
if реестр.get("sites") != int(sites):
    плохо.append("сайтов=%r, ожидалось %s" % (реестр.get("sites"), sites))
if not str(реестр.get("sites_digest", "")).startswith(digest16):
    плохо.append("отпечаток реестра=%r, ожидался начинающийся на %s"
                 % (реестр.get("sites_digest"), digest16))
if not источник.endswith(source):
    плохо.append("источник реестра=%r, ожидался .../%s" % (источник, source))
if готовность.get("read_only") is not True:
    плохо.append("read_only=%r — на этом этапе ожидается только чтение" % готовность.get("read_only"))

список = payload("list_registered_sites.json")
сайты = список.get("sites") or []
домены = {str(с.get("domain")) for с in сайты}
if len(сайты) != int(sites):
    плохо.append("list_registered_sites вернул %d записей, ожидалось %s" % (len(сайты), sites))
if domain not in домены:
    плохо.append("в списке нет контрольного домена %s" % domain)

сайт = payload("get_registered_site.json")
тело = сайт.get("site") or сайт
if str(тело.get("domain")) != domain:
    плохо.append("get_registered_site вернул domain=%r вместо %s" % (тело.get("domain"), domain))

if плохо:
    sys.stderr.write("ПРИЁМКА НЕ ПРОЙДЕНА:\n  " + "\n  ".join(плохо) + "\n")
    raise SystemExit(6)
print("   приёмка: host=%s версия=%s сайтов=%s отпечаток=%s… источник=%s домен %s на месте"
      % (host, version, sites, digest16, source, domain))
PYACCEPT
then
  restore "приёмка не пройдена — состояние возвращено"
fi
rm -rf "$ANSWERS"
ok "три инструмента MCP отвечают данными фабрики из контейнера Open WebUI"

# --- 8. Единственность имени в работающей сети ------------------------------
log "8. имя ${SERVICE_NAME} в работающей сети"
docker network inspect "$NETWORK" \
  --format '{{range .Containers}}{{.Name}} {{end}}' > "${BACKUP_DIR}/network-after.txt" 2>/dev/null || true
OWNERS="$(docker ps --format '{{.Names}}' | while read -r c; do
  if docker inspect "$c" --format \
      "{{range \$k, \$v := .NetworkSettings.Networks}}{{range \$v.Aliases}}{{.}} {{end}}{{end}}" \
      2>/dev/null | tr ' ' '\n' | grep -qx "$SERVICE_NAME"; then printf '%s ' "$c"; fi
done)"
info "контейнеры с именем/alias ${SERVICE_NAME}: ${OWNERS:-нет}"
COUNT="$(printf '%s' "$OWNERS" | wc -w)"
[ "$COUNT" = 1 ] || restore "имя ${SERVICE_NAME} разрешается в ${COUNT} контейнеров — двойное разрешение"
ok "имя принадлежит ровно одному контейнеру"

log "готово"
cat <<SUMMARY
   Коннектор Open WebUI не меняется: http://${SERVICE_NAME}:9000/mcp теперь
   обслуживает мост фабрики (режим только чтения, 23 сайта, claude-control-01).
   Прежний сервис сохранён как ${LEGACY_NAME}; его зависимости и данные на месте.
   Перечень инструментов прежнего ответчика: ${BACKUP_DIR}/legacy-tools-list.json

   Откат одной командой:
     sudo bash $0 --rollback
   Копия исходного файла и снимки состояния: ${BACKUP_DIR}
SUMMARY
