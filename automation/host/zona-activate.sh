#!/usr/bin/env bash
# Активация подготовленного релиза Zona: перезапуск, проверка, откат при провале.
#
# Запускает ВЛАДЕЛЕЦ:  sudo bash automation/host/zona-activate.sh [site]
#
# Почему один сценарий, а не три команды. Между перезапуском и проверкой
# витрина уже живая: если проверка провалится, а откат придётся набирать
# руками, домен останется сломанным ровно на время набора. Здесь эти три шага
# связаны: провал проверки сам возвращает прежние байты и перезапускает снова.
#
# Чего сценарий НЕ делает: не собирает артефакт, не трогает манифест, DNS, TLS,
# robots и индексацию, не касается соседних витрин. Только перезапуск того
# юнита, что назван, и проверка того домена, что объявлен его манифестом.
set -uo pipefail

САЙТ="${1:-zona-01}"
ФРОНТ=/srv/lords/.frontend
МАНИФЕСТ="${ФРОНТ}/template-manifest-${САЙТ}.json"
ЮНИТ="nova-${САЙТ}.service"
КОРЕНЬ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ПРОВЕРКА="${КОРЕНЬ}/automation/host/zona-post-restart-verify.py"

сказать() { echo "[$(date -u +%H:%M:%S)] $*"; }
умереть() { echo "ОШИБКА: $*" >&2; exit 1; }

[ -f "$МАНИФЕСТ" ] || умереть "нет манифеста витрины: $МАНИФЕСТ"
[ -f "$ПРОВЕРКА" ] || умереть "нет сценария проверки: $ПРОВЕРКА"

СЕМЕЙСТВО=$(python3 -c "import json,sys;print(json.load(open('$МАНИФЕСТ')).get('template_family',''))")
[ "$СЕМЕЙСТВО" = "zona" ] || умереть "манифест объявляет семейство '$СЕМЕЙСТВО', а не zona"

ДОМЕН=$(python3 -c "import json;print(json.load(open('$МАНИФЕСТ')).get('domain',''))")
ОТКАТ=$(python3 -c "import json;print(json.load(open('$МАНИФЕСТ')).get('rollback_target_file',''))")
АРТЕФАКТ=$(python3 -c "import json;print(json.load(open('$МАНИФЕСТ')).get('artifact_path',''))")
СБОРКА=$(python3 -c "import json;print(json.load(open('$МАНИФЕСТ')).get('build_id',''))")

сказать "витрина ${САЙТ}, домен ${ДОМЕН}, сборка ${СБОРКА}"
сказать "перезапуск ${ЮНИТ}"
systemctl restart "$ЮНИТ" || умереть "служба не перезапущена"

# Витрина поднимает снимок каталога десятками секунд: проверять раньше
# готовности значит проверять загрузку, а не витрину.
сказать "жду готовности"
for _ in $(seq 1 120); do
  if systemctl is-active --quiet "$ЮНИТ"; then
    if python3 - "$МАНИФЕСТ" <<'PY' >/dev/null 2>&1
import json, socket, sys, urllib.request
м = json.load(open(sys.argv[1]))
порт = int(м.get("port") or 0)
if not порт:
    import re, pathlib
    юнит = pathlib.Path(f"/etc/systemd/system/nova-{м['service_name'].replace('.service','').replace('nova-','')}.service")
    текст = юнит.read_text() if юнит.is_file() else ""
    m = re.search(r"--port\s+(\d+)", текст)
    порт = int(m.group(1)) if m else 0
socket.create_connection(("127.0.0.1", порт), timeout=3).close()
PY
    then
      break
    fi
  fi
  sleep 2
done

сказать "приёмка живого домена"
if python3 "$ПРОВЕРКА" --site "$САЙТ" --domain "$ДОМЕН"; then
  сказать "PASS — релиз ${СБОРКА} активен на ${ДОМЕН}"
  exit 0
fi

сказать "FAIL — возвращаю прежние байты"
[ -n "$ОТКАТ" ] && [ -f "$ОТКАТ" ] || умереть "цель отката недоступна: '$ОТКАТ'"
cp "$ОТКАТ" "$АРТЕФАКТ" || умереть "откат не скопирован"
systemctl restart "$ЮНИТ" || умереть "служба не перезапущена после отката"
сказать "откат выполнен: ${АРТЕФАКТ} ← ${ОТКАТ}"
сказать "витрина возвращена в прежнее состояние; причины провала выше"
exit 2
