#!/usr/bin/env bash
# Выложить исправление доступности серий на ДВЕ витрины вне очереди ячеек.
#
#   sudo bash automation/host/apply-episode-availability-root.sh [--dry-run]
#
# ИДЕНТИФИКАТОРЫ ЗДЕСЬ ТОЛЬКО ЛАТИНСКИЕ. `bash -n` разбирает кириллические
# имена переменных без ошибки, а при выполнении отвечает `bad substitution` —
# в этом проекте на этом обожглись шесть раз. Комментарии по-русски, код нет.
#
# ЧТО ПОКАЗАЛИ ДВА ПРЕДЫДУЩИХ ПРОГОНА (07:03 и 10:43, 2026-09-29) — установлено
# сверкой байтов в /srv с байтами репозиториев и временем стартов процессов:
#
#   an1mego.site    файлы легли, служба перезапущена — но проверка живой
#                   страницы нашла ещё два места счёта по счётчику, и на
#                   витрине сейчас версия ДО них
#   animeg0.site    ОТКАЗ install.sh: checks/manifest_and_entrypoint.py увидел
#                   artifact_sha256 от прежней сборки. Проверка сработала верно
#   animedia.icu    ОТКАЗ activate.sh: это сценарий ПЕРВИЧНОГО включения, на
#                   работающей службе он отказывает намеренно
#   animedia.space  выкладывается собственной сессией сайта, здесь не трогается
#
# ПОЧЕМУ ЗДЕСЬ БОЛЬШЕ НЕТ animedia.icu. Её выпуск из репозитория ячейки
# ОТКАТИЛ БЫ витрину назад, и это измерено, а не предположено:
#
#   /srv/animedia-icu/app/src/animedia-frontend.py   071762cc7882  11230 строк
#   var/site-repos/animedia-icu/src/animedia-frontend.py 5437610880b2 10644 строк
#
# У живого рантайма ДВЕНАДЦАТЬ функций, которых нет в репозитории ячейки
# (_без_повторов_франшизы, _жанры_ссылками, меню, панель, кнопка и другие —
# работа сессии animedia-icu-visual-01, оформление 1.2.11), а у живого
# `community.py` (ab7eec640854, 987 строк) две функции, которых нет в копии
# ячейки (f82555e8e881, 842 строки): `переключить_избранное` и
# `снять_записи_посетителя`. Установка отсюда убрала бы избранное и удаление
# записей посетителя с работающего сайта. Наличие `deploy/update.sh` готовности
# к этому не доказывает: сценарий раскладывает то, что ему дали, и не знает,
# что даёт более старый код.
#
# Правка доступности для animedia.icu передаётся сессии, которая ведёт её
# выпуск, отдельной передачей: инструмент фабрики приводит ИХ рантайм одной
# командой, и это отрепетировано на копии их файла (см. передачу 104).
#
# ЧЕМ ЭТА ВЕРСИЯ ОТЛИЧАЕТСЯ ОТ ПРЕЖНЕЙ
#
# 1. Пропуск и успех больше НЕ решаются публичным build-id. Совпадение build-id
#    ничего не доказывает: animeg0.site показывает `animego-03-fc741a4a87ec` при
#    `runtime_digest_match: false` — метка берётся из манифеста, а рантайм на
#    диске может быть любым. Сверяется САМ ФАЙЛ: sha256 установленного рантайма
#    против sha256 рантайма репозитория.
# 2. Перед установкой проверяется, что манифест репозитория описывает его же
#    исходники (`code_file_sha256` против файла). Манифест под содержимое /srv
#    здесь не подгоняется никогда: правда — репозиторий, /srv её получает.
# 3. После перезапуска проверяется ТРОЙКА: байты установленного файла, наличие
#    признаков исправления в нём и ответ `/healthz` с `runtime_digest_match`.
#    «Сценарий не выругался» выкладкой не считается.
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

# Признаки исправления в файле рантайма. Это не «слово где-то в тексте», а
# имена, которые вводит именно эта правка: множество доступных номеров,
# наложение поверх снимка конвейера и счёт длиной множества. Их отсутствие
# означает, что исполняется версия без исправления, чем бы ни назвался build-id.
MARKERS=('доступные_номера' '_наложить_номера' 'len(доступные_номера(')

sha_of() { sha256sum "$1" 2>/dev/null | cut -c1-12; }

markers_present() {
  local file="$1" m
  for m in "${MARKERS[@]}"; do
    grep -qF -- "$m" "$file" || return 1
  done
  return 0
}

healthz_match() {
  local port="$1"
  curl -s -m 10 "http://127.0.0.1:$port/healthz" 2>/dev/null \
    | python3 -c 'import json,sys
try:
    d = json.load(sys.stdin)
except Exception:
    print("нет ответа"); raise SystemExit
print("true" if d.get("runtime_digest_match") is True else
      f"false (build_id={d.get(\"build_id\")})")' 2>/dev/null || echo "нет ответа"
}

deploy_one() {
  local name="$1" repo="$2" unit="$3" port="$4" entry="$5" live="$6"
  log "$name"
  if [ ! -d "$repo" ]; then
    results+=("ОТКАЗ $name: нет рабочей копии $repo"); return 0
  fi
  local src="$repo/src/$entry"
  if [ ! -f "$src" ]; then
    results+=("ОТКАЗ $name: в репозитории нет $src"); return 0
  fi

  # --- 1. репозиторий сам себе не противоречит -------------------------------
  # Манифест обязан описывать ИСХОДНИКИ репозитория. Разойдясь, он либо
  # остановит установку (так и было у animeg0.site), либо, если его подогнать
  # под /srv, узаконит то, чего нет ни в одном коммите.
  local want_code have_code
  want_code=$(python3 -c 'import json,sys
try:
    print((json.load(open(sys.argv[1])).get("code_file_sha256") or "")[:12])
except Exception:
    print("")' "$repo/config/template-manifest.json" 2>/dev/null || true)
  have_code=$(sha_of "$src")
  if [ -n "$want_code" ] && [ "$want_code" != "$have_code" ]; then
    results+=("ОТКАЗ $name: манифест описывает $want_code, а в репозитории $have_code — перештампуйте манифест ИЗ РЕПОЗИТОРИЯ (tools/stamp_manifest.py), не из /srv")
    return 0
  fi
  if ! markers_present "$src"; then
    results+=("ОТКАЗ $name: в исходнике репозитория нет признаков исправления — выкладывать нечего")
    return 0
  fi

  # --- 2. нужна ли установка вообще ------------------------------------------
  # Решает СРАВНЕНИЕ БАЙТОВ, а не метка. Витрина, у которой на диске ровно тот
  # же файл, что в репозитории, уже обновлена; всё остальное — установка.
  local live_sha=""
  [ -f "$live" ] && live_sha=$(sha_of "$live")
  echo "   репозиторий $have_code   на витрине ${live_sha:-нет файла}"
  if [ -n "$live_sha" ] && [ "$live_sha" = "$have_code" ] && markers_present "$live"; then
    local hm
    hm=$(healthz_match "$port")
    if [ "$hm" = "true" ]; then
      results+=("пропуск $name: на витрине те же байты ($have_code), признаки исправления на месте, /healthz подтверждает")
      return 0
    fi
    echo "   байты совпали, но /healthz отвечает $hm — процесс исполняет не то, что лежит: перезапускаю"
    if [ "$dry_run" = 0 ]; then
      systemctl restart "$unit" || { results+=("ОТКАЗ $name: $unit не перезапустился"); return 0; }
      sleep 8
    fi
    hm=$(healthz_match "$port")
    results+=("$([ "$hm" = true ] && echo ok || echo ВНИМАНИЕ) $name: перезапуск без установки, /healthz=$hm")
    return 0
  fi

  # --- 3. чем ставить ---------------------------------------------------------
  # Сценарий выбирается по СОСТОЯНИЮ витрины, а не по имени файла. `activate.sh`
  # — первичное включение: он сам отказывает на уже работающей службе, и
  # повторять его бессмысленно — так и закончился прогон 10:43 на animedia.icu.
  local script="" candidate
  for candidate in update.sh install.sh activate.sh; do
    [ -f "$repo/deploy/$candidate" ] || continue
    script="$repo/deploy/$candidate"
    break
  done
  if [ -z "$script" ]; then
    results+=("ОТКАЗ $name: в $repo/deploy нет ни update.sh, ни install.sh, ни activate.sh")
    return 0
  fi
  local needs_artifact=0
  grep -q 'не задан --artifact' "$script" && needs_artifact=1

  if [ "$dry_run" = 1 ]; then
    echo "   [сухой прогон] $(basename "$script")$([ "$needs_artifact" = 1 ] && echo ' --artifact <сборка>')"
    echo "   [сухой прогон] systemctl restart $unit"
    echo "   [сухой прогон] ожидаю на витрине $have_code, признаки исправления и /healthz runtime_digest_match=true"
    results+=("ok    $name (сухой прогон): поставил бы $have_code вместо ${live_sha:-ничего}")
    return 0
  fi

  local art=""
  if [ "$needs_artifact" = 1 ]; then
    local out="/tmp/episode-availability-build/$(basename "$repo")"
    rm -rf "$out"; mkdir -p "$out"
    if ! python3 "$repo/tools/build_release.py" --output "$out" >/dev/null 2>&1; then
      results+=("ОТКАЗ $name: артефакт не собрался (tools/build_release.py)"); return 0
    fi
    art=$(find "$out" -name '*.tar.gz' | head -1)
    [ -n "$art" ] || { results+=("ОТКАЗ $name: сборка не дала артефакта"); return 0; }
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

  # --- 4. три независимых доказательства, а не одно ---------------------------
  local after_sha hm
  after_sha=$(sha_of "$live")
  if [ "$after_sha" != "$have_code" ]; then
    results+=("ОТКАЗ $name: после установки на витрине $after_sha, а ожидался $have_code — файлы не легли")
    return 0
  fi
  if ! markers_present "$live"; then
    results+=("ОТКАЗ $name: байты легли, но признаков исправления в файле нет")
    return 0
  fi
  hm=$(healthz_match "$port")
  if [ "$hm" != "true" ]; then
    results+=("ОТКАЗ $name: файл на месте ($after_sha), но /healthz отвечает runtime_digest_match=$hm — процесс исполняет не его")
    return 0
  fi
  results+=("ok    $name: ${live_sha:-ничего} -> $after_sha, признаки исправления на месте, /healthz подтверждает")
}

deploy_one "an1mego.site (animego-02)" /home/claude/wt-an1mego-site \
           nova-an1mego-site.service 9150 animego-frontend.py \
           /srv/an1mego-site/app/src/animego-frontend.py
deploy_one "animeg0.site (animego-03)" /home/claude/wt-animeg0-site \
           nova-animeg0-site.service 9151 animego-frontend.py \
           /srv/animeg0-site/app/src/animego-frontend.py

# animedia.icu и animedia.space здесь НЕ выкладываются — причины в шапке файла.
# Для animedia.icu это не «пока не дошли руки», а измеренный откат витрины
# назад; для animedia.space — её выпуск ведёт собственная сессия сайта.

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
