#!/usr/bin/env bash
# Установка зафиксированного пакета и, по требованию, запуск нового домена.
#
#   sudo bash <пакет>/tree/automation/host/unblock-transfer.sh [--with-launch <site>] [--dry-run]
#
# Почему запускать надо ИЗ ПАКЕТА
# --------------------------------
#
# 26.09 установка в 13:30 «выполнилась», а ни один ожидаемый результат не
# появился. Установщик был исправен: он читал рабочий каталог, в котором
# обязательные части пакета появились в 13:33, 13:35, 13:47 и 13:54 — то есть
# ПОСЛЕ запуска. Каждый шаг честно скопировал то, что видел.
#
# Вывод не «быть внимательнее». Источник, который может измениться во время
# установки, не должен быть доступен установщику вообще. Поэтому:
#
#   * пакет собирается из коммита (automation/host/freeze-package.py) и
#     сопровождается описью с sha256 каждого файла и общим digest;
#   * этот сценарий сверяет digest ДО работы, переносит дерево в
#     root-владение и перезапускает себя уже оттуда: учётная запись claude
#     физически не может изменить источник во время установки;
#   * digest сверяется ещё раз в конце. Расхождение — отказ, а не
#     предупреждение.
#
# Что ставится и что это разблокирует
# ------------------------------------
#
#   1. исполнитель      приёмка читает build-id из заголовка; контракт данных
#                       ищет репозиторий сам
#                       -> перенос Yummy перестаёт откатывать исправного
#                          кандидата, первый выпуск не требует чужого файла
#   2. юниты по реестру только недостающие
#   3. пути издателя    ReadWritePaths=-<путь> и снятие устаревшего drop-in
#                       -> 226/NAMESPACE снят
#   4. новый домен      юниты, nginx, сертификат (только с --with-launch)
#
# Службы не включаются и не запускаются: это работа исполнителя.
set -Eeuo pipefail

dry_run=""
launch=""
package=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run="--dry-run" ;;
    --with-launch) launch="${2:-}"; shift ;;
    --package) package="${2:-}"; shift ;;
    *) echo "неизвестный аргумент: $1" >&2; exit 2 ;;
  esac
  shift
done

SELF="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/$(basename -- "${BASH_SOURCE[0]}")"
REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
INSTALLED=/usr/local/lib/site-factory-cell
DROPIN_DIR=/etc/systemd/system/nova-daily-refresh.service.d
STAGE_ROOT=/var/lib/site-cells/packages

log()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
ok()   { printf '   \033[32m[ок]\033[0m %s\n' "$*"; }
bad()  { printf '   \033[31m[нет]\033[0m %s\n' "$*"; }

[ -n "$dry_run" ] || [ "$(id -u)" = 0 ] || { echo "нужен root" >&2; exit 1; }

# --- шаг 0: пакет ------------------------------------------------------------
# Если сценарий лежит в <пакет>/tree/automation/host, пакет — это его дед.
[ -n "$package" ] || { [ -f "$REPO/../manifest.json" ] && package="$(cd -- "$REPO/.." && pwd)"; } || true
if [ -z "$package" ]; then
  cat >&2 <<'NOPKG'
[x] запуск не из зафиксированного пакета.

    Именно так была потеряна установка 26.09: источник менялся во время
    работы установщика. Сначала зафиксируйте пакет, потом ставьте из него:

      python3 automation/host/freeze-package.py
      sudo bash "$(python3 automation/host/freeze-package.py --latest)/tree/automation/host/unblock-transfer.sh"

    Осознанный запуск из рабочего каталога: --package <каталог пакета>.
NOPKG
  exit 2
fi

log "шаг 0: зафиксированный пакет"
python3 "$REPO/automation/host/freeze-package.py" --check "$package" || {
  bad "состав пакета не совпадает с описью — установка отменена"
  exit 3
}
pkg_id="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]+'/manifest.json',encoding='utf-8'))['package_id'])" "$package")"
pkg_digest="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]+'/manifest.json',encoding='utf-8'))['digest'])" "$package")"
ok "пакет $pkg_id, digest ${pkg_digest:0:16}"

# Перенос в root-владение и перезапуск оттуда. Без этого «неизменность»
# держалась бы на обещании: каталог пакета доступен на запись подающей стороне.
if [ -z "$dry_run" ] && [ "${CELL_PKG_STAGED:-}" != "$pkg_digest" ]; then
  staged="$STAGE_ROOT/$pkg_id"
  log "перенос пакета под root: $staged"
  install -d -m 0755 "$STAGE_ROOT"
  rm -rf "$staged.new"
  cp -a "$package" "$staged.new"
  chown -R root:root "$staged.new"
  chmod -R go-w "$staged.new"
  rm -rf "$staged"
  mv "$staged.new" "$staged"
  python3 "$staged/tree/automation/host/freeze-package.py" --check "$staged" >/dev/null || {
    bad "перенесённая копия не совпала с описью"
    exit 3
  }
  ok "источник больше недоступен на запись подающей стороне"
  export CELL_PKG_STAGED="$pkg_digest"
  exec bash "$staged/tree/automation/host/unblock-transfer.sh" \
      --package "$staged" ${launch:+--with-launch "$launch"}
fi

log "шаг 1: исполнитель"
bash "$REPO/automation/host/install-cell-executor.sh" ${dry_run:+--dry-run} || true
if [ -z "$dry_run" ]; then
  if grep -qs 'registry as _registry' "$INSTALLED/factory/cell/privileged.py" &&
     grep -qs 'build_id_source' "$INSTALLED/factory/cell/privileged.py"; then
    ok "контракт данных ищет репозиторий сам; приёмка читает build-id из заголовка"
  else
    bad "правки не доехали — дальше идти нельзя"
    exit 3
  fi
fi

log "шаг 2: недостающие юниты ячеек"
python3 "$REPO/automation/host/install-cell-units.py" ${dry_run:+--dry-run}

log "шаг 3: пути издателя, переживающие отсутствующий каталог"
bash "$REPO/automation/host/install-publisher-cell-paths.sh" ${dry_run:+--dry-run}
if [ -z "$dry_run" ]; then
  dashed="$(grep -hc '^ReadWritePaths=-' "$DROPIN_DIR"/*.conf 2>/dev/null | paste -sd+ | bc || echo 0)"
  if [ "${dashed:-0}" -ge 1 ]; then
    ok "путей с дефисом: $dashed"
  else
    bad "в drop-in нет ни одного пути с дефисом: 226/NAMESPACE вернётся"
    exit 3
  fi
  if [ -f "$DROPIN_DIR/10-cell-data-dirs.conf" ]; then
    bad "устаревший 10-cell-data-dirs.conf на месте: systemd сложит оба drop-in"
    exit 3
  fi
  ok "устаревшего drop-in нет"
fi

if [ -n "$launch" ]; then
  log "шаг 4: подключение нового домена $launch к хосту"
  bash "$REPO/automation/host/launch-new-site.sh" --site "$launch" $dry_run
fi

log "шаг 5: пакет не менялся во время установки"
python3 "$REPO/automation/host/freeze-package.py" --check "$package" || {
  bad "СОСТАВ ПАКЕТА ИЗМЕНИЛСЯ ВО ВРЕМЯ УСТАНОВКИ — результат недостоверен"
  exit 4
}
ok "digest тот же: ${pkg_digest:0:16}"

log "итог"
if [ -n "$dry_run" ]; then
  echo "   сухой прогон: ничего не менялось"
  exit 0
fi
cat <<'TAIL'
   Проверка владельцем, одной командой и без root:

     python3 automation/host/check-installed.py

   Дальше выпуск через очередь — без root:

     python3 -m factory cell trigger --site <site_id> --ci-run <прогон> --confirm-activation
TAIL
