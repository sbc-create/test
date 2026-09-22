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
# Что именно исполняется. `ExecStart` юнита указывает на общий загрузчик
# `lords-frontend.py`; тот по порту находит витрину и через `execv` передаёт
# управление релизу, на который смотрит символическая ссылка
# `sites/<витрина>/current`. Значит установленный релиз — это ссылка, а
# перезапуск лишь заставляет процесс её перечитать.
#
# Отсюда и откат: вернуть прежнее поколение можно только переводом ссылки на
# `PREVIOUS_TARGET.txt`. Прежняя версия копировала байты в `artifact_path`
# манифеста — файл, который не исполняет никто: откат рапортовал об успехе,
# а витрина оставалась на сломанном релизе.
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
build_id=$(python3 -c "import json;print(json.load(open('$manifest')).get('build_id',''))")
release_dir=$(python3 -c "import json;print(json.load(open('$manifest')).get('release_dir',''))")

site_dir="${frontend_dir}/sites/${site}"
release_link="${site_dir}/current"
previous_file="${site_dir}/PREVIOUS_TARGET.txt"

# Активируется то, на что смотрит ссылка, а не то, что объявил манифест.
# Расхождение означает, что релиз не установлен: перезапуск поднял бы чужое
# поколение под именем нового, и приёмка ловила бы это уже на живом домене.
[ -L "$release_link" ] || die "нет ссылки релиза: $release_link"
linked=$(readlink -f "$release_link")
[ -n "$release_dir" ] || die "манифест не объявляет release_dir"
[ "$linked" = "$(readlink -f "$release_dir")" ] || \
  die "ссылка релиза ведёт на '$linked', а манифест объявляет '$release_dir'"

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

log "FAIL — возвращаю прежнее поколение"
[ -f "$previous_file" ] || die "цель отката недоступна: нет $previous_file"
previous=$(cat "$previous_file")
[ -n "$previous" ] || die "цель отката пуста: $previous_file"
previous_dir=$(cd "$site_dir" && readlink -f "$previous") || \
  die "цель отката не разрешается: '$previous'"
[ -f "${previous_dir}/lords-frontend.py" ] || \
  die "в цели отката нет рантайма: ${previous_dir}/lords-frontend.py"

# `ln -sfn` заменяет ссылку одним системным вызовом: промежуточного состояния,
# в котором витрина осталась бы без релиза, не возникает.
ln -sfn "$previous" "$release_link" || die "ссылка релиза не переведена"
systemctl restart "$unit" || die "служба не перезапущена после отката"
log "откат выполнен: ${release_link} → ${previous_dir}"

# Откат тоже проверяется: «вернул» без подтверждения — такое же недоказанное
# утверждение, как «выложил» без приёмки.
if python3 "$verify_script" --site "$site" --domain "$domain" > /dev/null 2>&1; then
  log "прежнее поколение отвечает штатно"
else
  log "ВНИМАНИЕ: после отката приёмка тоже не прошла — витрина требует владельца"
fi
log "витрина возвращена в прежнее состояние; причины провала выше"
exit 2
