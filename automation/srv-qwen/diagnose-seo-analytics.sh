#!/usr/bin/env bash
# Одно действие: установить причину «Error executing tool analytics_readiness».
# Запускать НА srv-qwen:
#
#   sudo bash diagnose-seo-analytics.sh
#
# Почему это нужно на вашей стороне. Инструмента `analytics_readiness` в коде
# фабрики НЕТ (проверено поиском по репозиторию): его обслуживает служба
# `seo-analytics-mcp` на srv-qwen. Журналов этой службы на фабрике не бывает,
# поэтому причина устанавливается здесь — одним прогоном, а не перепиской.
#
# Проверяемая ГИПОТЕЗА (не установленная причина): после переименования
# прежнего сервиса в `site-factory-mcp-legacy` служба аналитики обращается не
# туда, куда нужно. Пакет подключения моста намеренно перевёл её ссылки на
# legacy, чтобы её поведение не изменилось; если ей нужен настоящий реестр
# фабрики, именно это и будет причиной — и тогда её upstream надо указать на
# `site-factory-mcp` (мост), у которого есть и реестр ячеек, и реестр аналитики.
#
# Скрипт НИЧЕГО не меняет. Секреты не печатаются: из окружения выводятся имена
# переменных, а значения — только у адресов (URL/HOST/UPSTREAM/ENDPOINT), и
# ничего, что похоже на токен, ключ или пароль.
set -uo pipefail

ANALYTICS="${ANALYTICS_CONTAINER:-}"
WEBUI="${WEBUI_CONTAINER:-}"
BRIDGE_HOST="${BRIDGE_HOST:-site-factory-mcp}"
LEGACY_HOST="${LEGACY_HOST:-site-factory-mcp-legacy}"
DOMAIN="${1:-lordserials22.info}"

say()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
info() { printf '        %s\n' "$*"; }
bad=0

command -v docker >/dev/null || { echo "нет docker"; exit 2; }

say "1. контейнеры"
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}' \
  | grep -i -e analytics -e site-factory -e open-webui || info "подходящих имён нет"
[ -n "$ANALYTICS" ] || ANALYTICS="$(docker ps --format '{{.Names}}' \
  | grep -i -m1 -e seo-analytics -e analytics || true)"
[ -n "$WEBUI" ] || WEBUI="$(docker ps --format '{{.Names}}' \
  | grep -i -m1 -e open-webui -e openwebui || true)"
info "служба аналитики: ${ANALYTICS:-НЕ НАЙДЕНА}"
info "контейнер Open WebUI: ${WEBUI:-НЕ НАЙДЕН}"
[ -n "$ANALYTICS" ] || { echo "без контейнера аналитики разбирать нечего: укажите ANALYTICS_CONTAINER=<имя>"; exit 2; }

say "2. на какой upstream настроена служба аналитики"
# Значения печатаются ТОЛЬКО у переменных-адресов; остальное — именами.
docker inspect "$ANALYTICS" --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | while IFS= read -r pair; do
      name="${pair%%=*}"
      case "$name" in
        *TOKEN*|*KEY*|*SECRET*|*PASSWORD*|*PASS*|*CREDENTIAL*)
          info "$name = <скрыто>" ;;
        *URL*|*HOST*|*UPSTREAM*|*ENDPOINT*|*BASE*|*MCP*|*FACTORY*)
          info "$pair" ;;
        *) info "$name = <не адрес, значение не печатается>" ;;
      esac
    done

say "3. разрешение имён ИЗ контейнера аналитики"
for host_name in "$BRIDGE_HOST" "$LEGACY_HOST"; do
  out="$(docker exec "$ANALYTICS" sh -c "getent hosts $host_name 2>/dev/null || nslookup $host_name 2>&1 | tail -3" 2>&1)"
  info "$host_name -> ${out:-не разрешается}"
done

say "4. отвечает ли каждый из них на MCP ИЗ контейнера аналитики"
probe() {   # probe <имя хоста>
  docker exec "$ANALYTICS" sh -c "
if command -v python3 >/dev/null 2>&1; then
  python3 - <<'PY'
import json, urllib.request
тело = json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call',
                   'params':{'name':'system_readiness','arguments':{}}}).encode()
req = urllib.request.Request('http://$1:9000/mcp', data=тело,
                             headers={'Content-Type':'application/json'})
print(urllib.request.urlopen(req, timeout=60).read().decode()[:400])
PY
elif command -v curl >/dev/null 2>&1; then
  curl -sS -m 60 -X POST -H 'Content-Type: application/json' \
    -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"system_readiness\",\"arguments\":{}}}' \
    http://$1:9000/mcp | head -c 400
else
  wget -qO- --header='Content-Type: application/json' \
    --post-data='{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"system_readiness\",\"arguments\":{}}}' \
    http://$1:9000/mcp | head -c 400
fi" 2>&1
}
for host_name in "$BRIDGE_HOST" "$LEGACY_HOST"; do
  answer="$(probe "$host_name")"
  kind="?"
  case "$answer" in
    *claude-control-01*) kind="мост ФАБРИКИ (есть реестр ячеек и аналитики)" ;;
    *'"sites": 0'*|*'site_count*0'*) kind="прежний сервис с ПУСТЫМ реестром" ;;
    *) kind="ответ не распознан" ;;
  esac
  info "$host_name: $kind"
  info "   $(printf '%s' "$answer" | head -c 220)"
done

say "5. фактическая ошибка инструмента аналитики"
# Полный текст, а не одна строка UI: именно его не хватало для разбора.
answer="$(docker exec "$ANALYTICS" sh -c "
if command -v curl >/dev/null 2>&1; then
  curl -sS -m 60 -X POST -H 'Content-Type: application/json' \
    -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"analytics_readiness\",\"arguments\":{\"domain\":\"$DOMAIN\"}}}' \
    http://127.0.0.1:9000/mcp
else
  wget -qO- --header='Content-Type: application/json' \
    --post-data='{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"analytics_readiness\",\"arguments\":{\"domain\":\"$DOMAIN\"}}}' \
    http://127.0.0.1:9000/mcp
fi" 2>&1)"
printf '        %s\n' "$(printf '%s' "$answer" | head -c 900)"
case "$answer" in
  *Traceback*|*Error*|*error*) bad=$((bad + 1)) ;;
esac

say "6. журнал службы аналитики (последние строки со следом ошибки)"
docker logs --tail 200 "$ANALYTICS" 2>&1 \
  | grep -i -e traceback -e error -e exception -e analytics_readiness \
  | tail -20 || info "совпадений нет"

say "7. тот же вопрос МОСТУ ФАБРИКИ — для сравнения"
# У моста этот инструмент есть с версии правил 2026-10-04.1, и ошибка у него
# всегда приходит с причиной и источником.
bridge_answer="$(docker exec "${WEBUI:-$ANALYTICS}" sh -c "
if command -v curl >/dev/null 2>&1; then
  curl -sS -m 90 -X POST -H 'Content-Type: application/json' \
    -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"analytics_readiness\",\"arguments\":{\"domain\":\"$DOMAIN\"}}}' \
    http://$BRIDGE_HOST:9000/mcp
else
  wget -qO- --header='Content-Type: application/json' \
    --post-data='{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"analytics_readiness\",\"arguments\":{\"domain\":\"$DOMAIN\"}}}' \
    http://$BRIDGE_HOST:9000/mcp
fi" 2>&1)"
printf '        %s\n' "$(printf '%s' "$bridge_answer" | head -c 700)"

say "итог"
cat <<SUMMARY
   По пунктам 2-4 видно, КУДА смотрит служба аналитики и кто ей отвечает:

     * отвечает прежний сервис с пустым реестром -> причина в upstream:
       служба спрашивает реестр, которого там нет. Указать ей
       http://${BRIDGE_HOST}:9000/mcp (мост фабрики) и перезапустить ТОЛЬКО её;
     * не разрешается имя или нет ответа -> причина в сети/остановленном
       сервисе, а не в данных;
     * ответ приходит, а инструмент всё равно падает (пункты 5-6 с Traceback)
       -> дефект самой службы аналитики; след из пункта 6 называет место.

   Мост фабрики на тот же вопрос отвечает вердиктом и источником (пункт 7):
   строка без причины у него невозможна.
SUMMARY
exit 0
