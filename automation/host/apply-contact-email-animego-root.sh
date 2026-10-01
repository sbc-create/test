#!/usr/bin/env bash
# Публичная почта обратной связи на двух витринах AnimeGo, которым нужен root.
#
#   sudo bash automation/host/apply-contact-email-animego-root.sh --dry-run
#   sudo bash automation/host/apply-contact-email-animego-root.sh
#
# ПОЧЕМУ ЭТО НЕ ДЕЛАЕТ СЕССИЯ САМА
#
# an1mego.site и animeg0.site — не ячейки реестра: их нет в
# config/site-cells.json, и очередь выпуска их не обслуживает. Адрес читается из
# /srv/<витрина>/app/config/site.json, каталог принадлежит учётной записи
# витрины (drwxrwxr-x <витрина>:<витрина>), а сессия работает под `claude` и в
# эту группу не входит — запись невозможна. Перезапуск юнита тоже требует root.
# Ни одной разрешённой wrapper-команды для этого в inventory/ssh-hosts.yaml нет
# (sudo_allowlist пуст). Поэтому один root-запуск, а не обход ограничений.
#
# ИДЕНТИФИКАТОРЫ ТОЛЬКО ЛАТИНСКИЕ. `bash -n` разбирает кириллические имена
# переменных без ошибки, а исполнение отвечает `bad substitution` — в этом
# проекте на этом обожглись семь раз, последний раз 2026-10-01 в deploy.sh.
#
# ЧТО СЦЕНАРИЙ ДЕЛАЕТ
#
#   1. сверяет, что рабочая копия витрины чистая и стоит на ожидаемом коммите —
#      выкладывается коммит, а не рабочий стол;
#   2. делает резервную копию действующего config/site.json рядом, с меткой
#      времени: откат не требует ни git, ни этого сценария;
#   3. копирует config/site.json из репозитория, сохраняя владельца и права;
#   4. перезапускает юнит витрины и ждёт, пока она начнёт отвечать;
#   5. ПРОВЕРЯЕТ публичную страницу: новый адрес есть, прежнего нет, ссылка
#      mailto ведёт на новый. Без этой проверки «скопировал файл» выдавалось бы
#      за «адрес виден посетителю», а это разные утверждения.
#
# ЧЕГО НЕ ДЕЛАЕТ: не трогает данные витрины, плеер, счётчики, режим индексации,
# nginx, DNS, sudoers и соседние сайты. Отказ на одной витрине не отменяет
# вторую. Секретов не печатает.
set -Eeuo pipefail

NEW_MAIL="spam.abusekp@proton.me"
OLD_MAIL="sbc.claude@yandex.ru"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
dry_run=0
[ "${1:-}" = "--dry-run" ] && dry_run=1

results=()
log()  { printf '[contact] %s\n' "$*"; }
run()  { if [ "$dry_run" = 1 ]; then printf '   [сухой прогон] %s\n' "$*"; else "$@"; fi; }

# apply_one <имя> <рабочая копия> <коммит> <каталог /srv> <юнит> <порт> <домен>
apply_one() {
  local name="$1" repo="$2" want="$3" root="$4" unit="$5" port="$6" host="$7"
  log "=== $name"

  if [ ! -d "$repo/.git" ]; then
    results+=("ОТКАЗ $name: нет рабочей копии $repo"); return 0
  fi
  local head dirty
  head="$(git -C "$repo" rev-parse HEAD)"
  dirty="$(git -C "$repo" status --porcelain)"
  if [ -n "$dirty" ]; then
    results+=("ОТКАЗ $name: рабочая копия $repo грязная — выкладывается коммит, а не рабочий стол")
    return 0
  fi
  if [ "$head" != "$want" ]; then
    results+=("ОТКАЗ $name: рабочая копия на ${head:0:12}, ожидался ${want:0:12}")
    return 0
  fi
  log "коммит подтверждён: ${head:0:12}"

  local src="$repo/config/site.json" dst="$root/app/config/site.json"
  if [ ! -f "$src" ]; then results+=("ОТКАЗ $name: нет $src"); return 0; fi
  if [ ! -f "$dst" ]; then results+=("ОТКАЗ $name: нет действующего $dst"); return 0; fi
  if ! grep -q "$NEW_MAIL" "$src"; then
    results+=("ОТКАЗ $name: в $src нет нового адреса — копировать нечего")
    return 0
  fi

  # Резервная копия рядом с файлом: откат одной командой cp, без git.
  run cp -a "$dst" "${dst}.bak-${STAMP}"
  log "резервная копия: ${dst}.bak-${STAMP}"

  # Владелец и права берутся у действующего файла, а не задаются числом:
  # у витрин разные учётные записи, и угадывать их здесь нечем.
  local owner mode
  owner="$(stat -c '%U:%G' "$dst")"
  mode="$(stat -c '%a' "$dst")"
  run install -o "${owner%%:*}" -g "${owner##*:}" -m "$mode" "$src" "$dst"
  log "config/site.json установлен ($owner, $mode)"

  run systemctl restart "$unit"
  if [ "$dry_run" = 0 ]; then
    local i=0
    while [ "$i" -lt 60 ]; do
      if curl -fsS --max-time 3 "http://127.0.0.1:${port}/healthz" >/dev/null 2>&1; then break; fi
      i=$((i + 1)); sleep 1
    done
    if [ "$i" -ge 60 ]; then
      results+=("ОТКАЗ $name: витрина не ответила на /healthz за 60 с после перезапуска")
      return 0
    fi
    log "витрина отвечает на :$port"
  fi

  # Пользовательский результат, а не факт копирования.
  if [ "$dry_run" = 1 ]; then
    results+=("[сухой прогон] $name: скопировал бы config/site.json и перезапустил $unit")
    return 0
  fi
  local page
  page="$(curl -fsS --max-time 20 "https://${host}/" 2>/dev/null || true)"
  if [ -z "$page" ]; then
    results+=("ВНИМАНИЕ $name: файл установлен и витрина отвечает, но публичная страница не прочиталась — проверьте вручную https://${host}/")
    return 0
  fi
  local has_new=0 has_old=0 has_link=0
  printf '%s' "$page" | grep -q "$NEW_MAIL"            && has_new=1
  printf '%s' "$page" | grep -q "$OLD_MAIL"            && has_old=1
  printf '%s' "$page" | grep -q "mailto:$NEW_MAIL"     && has_link=1
  if [ "$has_new" = 1 ] && [ "$has_old" = 0 ] && [ "$has_link" = 1 ]; then
    results+=("ГОТОВО $name: https://${host}/ отдаёт $NEW_MAIL ссылкой mailto, прежнего адреса нет")
  else
    results+=("ОТКАЗ $name: на https://${host}/ новый=$has_new прежний=$has_old mailto=$has_link — откат: cp -a ${dst}.bak-${STAMP} $dst && systemctl restart $unit")
  fi
}

apply_one "an1mego.site (animego-02)" /home/claude/wt-an1mego-site \
          a9df5a04fcded3db617439ac8b7b77b14a46964e \
          /srv/an1mego-site nova-an1mego-site.service 9150 an1mego.site

apply_one "animeg0.site (animego-03)" /home/claude/wt-animeg0-site \
          91365d7a2760c92a6aad24b294427b4b5efae352 \
          /srv/animeg0-site nova-animeg0-site.service 9151 animeg0.site

log "--- итог ---"
fail=0
for line in "${results[@]}"; do
  printf '[contact] %s\n' "$line"
  case "$line" in ОТКАЗ*) fail=1 ;; esac
done
log "доставку писем этот сценарий не подтверждает: mailto не отвечает кодом доставки"
exit "$fail"
