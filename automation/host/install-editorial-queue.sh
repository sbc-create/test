#!/usr/bin/env bash
# Установка исправлений редакционной очереди: корневая копия + мост Qwen.
#
#   sudo bash automation/host/install-editorial-queue.sh \
#        --package var/install-packages/pkg-XXXXXXXXXXXX \
#        --expect-digest <64 hex>
#
# Зачем отдельный сценарий, а не две команды руками. Действия ровно два, но
# порядок и проверки у них связаны: мост обязан перезапуститься ПОСЛЕ замены
# корневой копии и ДО того, как кто-то решит, что инструменты уже доступны.
# Разделение на две команды уже дало ошибку в этом проекте: инструмент
# `analytics_data` считался недоступным, хотя дело было в том, что служба
# работала из дерева БЕЗ него.
#
# Что делает — и только это
# -------------------------
#   1. узкая установка корневой копии исполнителя (install-executor-narrow.sh
#      из ПАКЕТА): сверка описи и digest, перенос под root, повторная сверка,
#      отказ при потере полей разрешений корневого реестра, tar прежней копии,
#      обязательная проверка результата с откатом при несовпадении;
#   2. drop-in мосту Qwen с переменной SEO_OPERATOR_ROOT, перезагрузка
#      systemd и перезапуск site-factory-mcp.service;
#   3. проверка результата: готовность моста, версия правил, число
#      инструментов, наличие ТРЁХ инструментов очереди и один фактический
#      вызов editorial_queue_status.
#
# Чего НЕ делает — намеренно
#   * не снимает паузу редакционной автоматизации (kill_switch остаётся
#     engaged): приёмка очереди идёт ДО возобновления публикаций;
#   * не трогает юниты витрин, nginx, выложенные релизы, обработчики Animedia,
#     разрешения индексации и редакционные данные;
#   * не подаёт заявок исполнителю и не выкладывает ни одного сайта;
#   * не подавляет ошибок: любой неуспех — это выход с кодом, а не сообщение.
set -Eeuo pipefail

package=""; expect=""; operator_root="/home/claude/wt-editorial-queue-repair-01"
while [ $# -gt 0 ]; do
  case "$1" in
    --package) package="${2:-}"; shift ;;
    --expect-digest) expect="${2:-}"; shift ;;
    --operator-root) operator_root="${2:-}"; shift ;;
    *) echo "неизвестный аргумент: $1" >&2; exit 2 ;;
  esac
  shift
done
[ -n "$package" ] && [ -n "$expect" ] || { echo "нужны --package и --expect-digest" >&2; exit 2; }
[ "$(id -u)" = 0 ] || { echo "нужен root" >&2; exit 1; }

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
UNIT=site-factory-mcp.service
DROPIN_DIR="/etc/systemd/system/${UNIT}.d"
DROPIN="${DROPIN_DIR}/20-editorial-queue.conf"
LOG_ROOT="/var/backups/site-factory-cell"
T="$(date -u +%Y%m%dT%H%M%SZ)"
JOURNAL="$LOG_ROOT/editorial-queue-$T"
install -d -m 0700 "$JOURNAL"
exec > >(tee -a "$JOURNAL/install.log") 2>&1

log() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
die() { printf '\033[31m[ОТКАЗ]\033[0m %s\n' "$*" >&2; exit 1; }
log "журнал: $JOURNAL/install.log"

# Модуль очереди обязан быть в дереве, на которое указывает мост. Проверяем ДО
# всякой установки: иначе мост перезапустится и будет отвечать «в дереве
# оператора нет модуля очереди» — отказ правильный, но заплаченный зря.
[ -f "$operator_root/seo_engine/content_operator/editorial_queue.py" ] \
  || die "в $operator_root нет seo_engine/content_operator/editorial_queue.py"

log "шаг 1: узкая установка корневой копии исполнителя"
bash "$package/tree/automation/host/install-executor-narrow.sh" \
  --package "$package" --expect-digest "$expect"

log "шаг 2: мост Qwen — drop-in и перезапуск"
if [ -f "$DROPIN" ]; then cp -a "$DROPIN" "$JOURNAL/20-editorial-queue.conf.before"; fi
install -d -m 0755 "$DROPIN_DIR"
cat > "$DROPIN" <<EOF
# Корень кода оператора содержания для моста Qwen. Поставлен
# install-editorial-queue.sh $T.
#
# Модуль канонической редакционной очереди
# (seo_engine/content_operator/editorial_queue.py) лежит в ветке ремонта
# оператора, а суточный цикл исполняет другое дерево. Эта переменная говорит
# мосту, где брать код очереди, и снимается, когда ветка ремонта будет влита в
# дерево суточного цикла: тогда строку нужно удалить, а не менять.
[Service]
Environment=SEO_OPERATOR_ROOT=$operator_root
EOF
chmod 0644 "$DROPIN"
echo "   $DROPIN"
systemctl daemon-reload
systemctl restart "$UNIT"

log "шаг 3: проверка результата"
failed=0
# Служба отвечает не мгновенно: ждём готовности, а не считаем перезапуск
# успехом. Отсутствие ответа за срок — это неуспех с названной причиной.
ready=""
for _ in $(seq 1 30); do
  ready="$(curl -sS --max-time 5 http://127.0.0.1:9000/healthz 2>/dev/null || true)"
  [ -n "$ready" ] && break
  sleep 1
done
[ -n "$ready" ] || die "мост не ответил на /healthz за 30 с после перезапуска"
echo "$ready" > "$JOURNAL/healthz.json"

/usr/bin/python3 - "$JOURNAL/healthz.json" <<'PYH' || failed=1
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print(f"   ready={d.get('ready')} read_only={d.get('read_only')} "
      f"instruction_version={d.get('instruction_version')}")
ок = bool(d.get("ready")) and d.get("instruction_version") == "2026-10-06.1"
if not ок:
    print("   [нет] мост не готов либо версия правил не 2026-10-06.1")
sys.exit(0 if ок else 1)
PYH

curl -sS --max-time 20 -X POST -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  http://127.0.0.1:9000/mcp > "$JOURNAL/tools.json" || die "tools/list не ответил"
/usr/bin/python3 - "$JOURNAL/tools.json" <<'PYT' || failed=1
import json, sys
имена = [и["name"] for и in json.load(open(sys.argv[1], encoding="utf-8"))["result"]["tools"]]
нужные = ("editorial_queue_next", "editorial_queue_result", "editorial_queue_status")
нет = [и for и in нужные if и not in имена]
print(f"   инструментов объявлено: {len(имена)}")
if нет:
    print(f"   [нет] в tools/list отсутствуют: {', '.join(нет)}")
sys.exit(1 if нет else 0)
PYT

# Один ФАКТИЧЕСКИЙ вызов, а не только перечень имён: объявленный инструмент,
# который падает при вызове, — это не работающий инструмент.
curl -sS --max-time 60 -X POST -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"editorial_queue_status","arguments":{"site":"yummyani.site"}}}' \
  http://127.0.0.1:9000/mcp > "$JOURNAL/queue-status.json" || die "вызов editorial_queue_status не ответил"
/usr/bin/python3 - "$JOURNAL/queue-status.json" <<'PYQ' || failed=1
import json, sys
о = json.load(open(sys.argv[1], encoding="utf-8"))
if о.get("error") or (о.get("result") or {}).get("isError"):
    print("   [нет] editorial_queue_status вернул ошибку:",
          json.dumps(о, ensure_ascii=False)[:300])
    sys.exit(1)
текст = (о["result"]["content"][0]["text"] if о.get("result", {}).get("content")
         else json.dumps(о, ensure_ascii=False))
д = json.loads(текст) if текст.lstrip().startswith("{") else {}
с = д.get("queue_status") or д
print(f"   очередь отвечает: произведений {с.get('works_total')}, "
      f"записей {с.get('records_total')}, проверенных текстов {с.get('texts_verified')}, "
      f"активных аренд {с.get('leases_active')}")
sys.exit(0 if с.get("records_total") else 1)
PYQ

echo
if [ "$failed" -ne 0 ]; then
  echo "ПРОВЕРКА НЕ ПРОЙДЕНА. Корневая копия: откат описан в журнале узкой"
  echo "установки. Мост: удалить $DROPIN и выполнить"
  echo "  systemctl daemon-reload && systemctl restart $UNIT"
  exit 4
fi
echo "ГОТОВО. Пакет установлен, мост перезапущен, очередь отвечает."
echo "Пауза редакционной автоматизации НЕ снята (это отдельное решение после приёмки)."
echo "Журнал: $JOURNAL"
