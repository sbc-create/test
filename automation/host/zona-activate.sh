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
#
# Имена переменных и функций — только ASCII: Bash не принимает не-ASCII
# идентификаторы, и сценарий с кириллическими именами не исполняется вовсе.
set -uo pipefail

site="${1:-zona-01}"
frontend_dir=/srv/lords/.frontend
manifest="${frontend_dir}/template-manifest-${site}.json"
unit="nova-${site}.service"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
verify_script="${repo_root}/automation/host/zona-post-restart-verify.py"

log() { echo "[$(date -u +%H:%M:%S)] $*"; }
die() { echo "ОШИБКА: $*" >&2; exit 1; }

[ -f "$manifest" ] || die "нет манифеста витрины: $manifest"
[ -f "$verify_script" ] || die "нет сценария проверки: $verify_script"

family=$(python3 -c "import json,sys;print(json.load(open('$manifest')).get('template_family',''))")
[ "$family" = "zona" ] || die "манифест объявляет семейство '$family', а не zona"

domain=$(python3 -c "import json;print(json.load(open('$manifest')).get('domain',''))")
rollback_src=$(python3 -c "import json;print(json.load(open('$manifest')).get('rollback_target_file',''))")
artifact=$(python3 -c "import json;print(json.load(open('$manifest')).get('artifact_path',''))")
build_id=$(python3 -c "import json;print(json.load(open('$manifest')).get('build_id',''))")

log "витрина ${site}, домен ${domain}, сборка ${build_id}"
log "перезапуск ${unit}"
systemctl restart "$unit" || die "служба не перезапущена"

# Витрина поднимает снимок каталога десятками секунд: проверять раньше
# готовности значит проверять загрузку, а не витрину.
log "жду готовности"
for _ in $(seq 1 120); do
  if systemctl is-active --quiet "$unit"; then
    if python3 - "$manifest" <<'PY' >/dev/null 2>&1
import json, socket, sys, urllib.request
data = json.load(open(sys.argv[1]))
port = int(data.get("port") or 0)
if not port:
    import re, pathlib
    unit_path = pathlib.Path(f"/etc/systemd/system/nova-{data['service_name'].replace('.service','').replace('nova-','')}.service")
    unit_text = unit_path.read_text() if unit_path.is_file() else ""
    m = re.search(r"--port\s+(\d+)", unit_text)
    port = int(m.group(1)) if m else 0
socket.create_connection(("127.0.0.1", port), timeout=3).close()
PY
    then
      break
    fi
  fi
  sleep 2
done

log "приёмка живого домена"
if python3 "$verify_script" --site "$site" --domain "$domain"; then
  log "PASS — релиз ${build_id} активен на ${domain}"
  exit 0
fi

log "FAIL — возвращаю прежние байты"
[ -n "$rollback_src" ] && [ -f "$rollback_src" ] || die "цель отката недоступна: '$rollback_src'"
cp "$rollback_src" "$artifact" || die "откат не скопирован"
systemctl restart "$unit" || die "служба не перезапущена после отката"
log "откат выполнен: ${artifact} ← ${rollback_src}"
log "витрина возвращена в прежнее состояние; причины провала выше"
exit 2
