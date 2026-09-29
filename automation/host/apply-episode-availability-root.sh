#!/usr/bin/env bash
# Выложить исправление доступности серий на ЧЕТЫРЕ витрины вне очереди ячеек.
#
#   sudo bash automation/host/apply-episode-availability-root.sh [--dry-run]
#
# ЧТО ПОКАЗАЛ ПРЕДЫДУЩИЙ ПРОГОН (2026-09-29, 07:03). Установлено сверкой байтов
# в /srv с байтами репозиториев и временем стартов процессов, а не по словам:
#
#   an1mego.site    файлы легли, служба перезапущена в 07:03 — выложено
#   animeg0.site    то же — выложено
#   animedia.space  файлы легли (install.sh), но служба НЕ перезапускалась с
#                   28.09 15:54: процесс исполнял прежний код из памяти
#   animedia.icu    не легло ничего: её deploy/activate.sh требует --artifact
#                   («установка из рабочего каталога запрещена») и без него
#                   выходит с кодом 2
#
# Отсюда три изменения против прошлой версии:
#   1. где сценарий витрины требует артефакт — он СОБИРАЕТСЯ здесь же
#      (tools/build_release.py) и передаётся с манифестом; проверка digest у
#      витрины остаётся на месте и не обходится;
#   2. перезапуск делается ОТДЕЛЬНО и всегда: разложить файлы мало, рантайм
#      читает их при старте;
#   3. итог пишется в файл и сверяется по build-id до и после — «сценарий не
#      выругался» выкладкой не считается.
#
# Юниты названы фактические, снятые из /proc/<pid>/cgroup работающих процессов:
# nova-an1mego-site, nova-animeg0-site, nova-animedia-icu, nova-animedia-space.
# Юниты nova-animedia-01/02 запускают ОБЩИЙ загрузчик и эти домены не
# обслуживают — перезапуск их выглядел бы успехом и не менял бы ничего.
#
# Сценарий НЕ меняет: DNS, firewall, sudoers, индексацию, счётчики, данные
# пользователей, оценки, комментарии и соседние сайты.
set -Eeuo pipefail

dry_run=0
[ "${1:-}" = "--dry-run" ] && dry_run=1

log()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[!]\033[0m %s\n' "$*"; }
die()  { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$dry_run" = 1 ] || [ "$(id -u)" = 0 ] || die "нужен root"

REPORT=/var/log/episode-availability-rollout.json
declare -a results=()

build_artifact() {
  local repo="$1" out="$2"
  [ -f "$repo/tools/build_release.py" ] || return 1
  rm -rf "$out"; mkdir -p "$out"
  python3 "$repo/tools/build_release.py" --output "$out" >/dev/null 2>&1 || return 1
  find "$out" -name '*.tar.gz' | head -1
}

deploy_one() {
  local name="$1" repo="$2" unit="$3" port="$4"
  log "$name"
  if [ ! -d "$repo" ]; then
    results+=("ОТКАЗ $name: нет рабочей копии $repo"); return 0
  fi
  # Сценарий выбирается по СОСТОЯНИЮ витрины, а не по имени файла.
  #
  # `activate.sh` — первичное включение: он сам отказывает на уже работающей
  # службе («уже активна: сайт, похоже, уже переключён»), и повторять его
  # бессмысленно — так и закончился прогон 10:43 на animedia.icu. Обновление
  # уже выложенного сайта делает `update.sh`, и порядок здесь такой:
  # update.sh, потом install.sh, и только для невыложенного — activate.sh.
  local script="" needs_artifact=0
  for candidate in update.sh install.sh activate.sh; do
    [ -f "$repo/deploy/$candidate" ] || continue
    script="$repo/deploy/$candidate"
    break
  done
  if [ -z "$script" ]; then
    results+=("ОТКАЗ $name: в $repo/deploy нет ни update.sh, ни install.sh, ни activate.sh")
    return 0
  fi
  grep -q 'не задан --artifact' "$script" && needs_artifact=1

  if [ "$dry_run" = 1 ]; then
    echo "   [сухой прогон] $script$([ "$needs_artifact" = 1 ] && echo ' --artifact <сборка>')"
    echo "   [сухой прогон] systemctl restart $unit; проверка сборки на :$port"
    results+=("ok    $name (сухой прогон)"); return 0
  fi

  local before after art=""
  before=$(curl -s -m 8 "http://127.0.0.1:$port/" 2>/dev/null \
           | grep -o 'data-build-id="[^"]*"' | head -1 || true)
  # Уже обновлённую витрину не трогаем: «повторно не выкладывать без
  # необходимости» — это не пожелание, а способ не сломать работающее.
  local want
  want=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['build_id'])" \
         "$repo/config/template-manifest.json" 2>/dev/null || true)
  if [ -n "$want" ] && [ "$before" = "data-build-id=\"$want\"" ]; then
    results+=("пропуск $name: уже на $want")
    return 0
  fi
  if [ "$needs_artifact" = 1 ]; then
    art=$(build_artifact "$repo" "/tmp/episode-availability-build/$(basename "$repo")" || true)
    if [ -z "$art" ]; then
      results+=("ОТКАЗ $name: артефакт не собрался (tools/build_release.py)"); return 0
    fi
    echo "   артефакт: $art"
    if ! bash "$script" --artifact "$art"; then
      results+=("ОТКАЗ $name: $(basename "$script") вернул ненулевой код"); return 0
    fi
  else
    if ! bash "$script"; then
      results+=("ОТКАЗ $name: $(basename "$script") вернул ненулевой код"); return 0
    fi
  fi

  systemctl restart "$unit" || {
    results+=("ОТКАЗ $name: $unit не перезапустился"); return 0; }
  sleep 8
  after=$(curl -s -m 15 "http://127.0.0.1:$port/" 2>/dev/null \
          | grep -o 'data-build-id="[^"]*"' | head -1 || true)
  if [ -z "$after" ]; then
    results+=("ОТКАЗ $name: после перезапуска витрина не ответила на :$port"); return 0
  fi
  if [ "$before" = "$after" ]; then
    results+=("ВНИМАНИЕ $name: сборка не изменилась ($after)"); return 0
  fi
  results+=("ok    $name: $before -> $after")
}

FACTORY=/home/claude/wt-portable-site-cell-01/var/site-repos
deploy_one "an1mego.site (animego-02)"    /home/claude/wt-an1mego-site  nova-an1mego-site.service   9150
deploy_one "animeg0.site (animego-03)"    /home/claude/wt-animeg0-site  nova-animeg0-site.service   9151
deploy_one "animedia.icu (animedia-01)"   "$FACTORY/animedia-icu"       nova-animedia-icu.service   9121

# animedia.space СОЗНАТЕЛЬНО не выкладывается отсюда. Выпуск этой витрины ведёт
# сессия claude/animedia-space-visual-01, и она ответила по каналу координации:
# её deploy/update.sh раскладывает собственный артефакт и переключает каталог
# целиком, то есть сторонние файлы в /srv он всё равно перезапишет, а перезапуск
# службы поверх незакреплённых файлов оставил бы витрину в состоянии, которого
# нет ни в одном коммите (`runtime_digest_match: false` в её /healthz).
#
# Согласованный порядок: правка передана веткой claude/extract-animedia-space
# репозитория sbc-create/site-animedia-space, та сессия берёт её обычной
# правкой, прогоняет свои проверки и выпускает штатно — тогда правка попадает в
# замок и артефакт и переживает следующий выпуск. Выкладывать её здесь значило
# бы сделать ровно то, от чего она предостерегла.

log "итог"
for line in "${results[@]}"; do printf '   %s\n' "$line"; done
if [ "$dry_run" = 0 ]; then
  python3 - "$REPORT" "${results[@]}" <<'PYEOF'
import json, sys, time
путь, строки = sys.argv[1], sys.argv[2:]
with open(путь, "w", encoding="utf-8") as ф:
    json.dump({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "results": строки}, ф, ensure_ascii=False, indent=1)
PYEOF
  echo
  log "итог записан в $REPORT — сессии журнала не видно, она читает этот файл"
fi
if printf '%s\n' "${results[@]}" | grep -q '^ОТКАЗ'; then
  echo
  warn "часть шагов не выполнена — остальные применены, повтор безопасен"
  exit 1
fi
