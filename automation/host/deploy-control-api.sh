#!/usr/bin/env bash
# Выкладка и откат управляющей службы.
#
# Релиз — неизменяемый каталог с кодом на конкретном SHA и собственным
# интерпретатором. Переключение версии — подмена символической ссылки current,
# то есть одно атомарное действие: полусостояния, в котором часть файлов новая,
# а часть старая, не возникает.
#
# Состояние фабрики (очередь, журнал, профили) живёт отдельно и общее для всех
# версий. Иначе откат уносил бы вместе с кодом и задания, поставленные новой
# версией, а это потеря работы, о которой никто не узнает.
#
# Ворота перед переключением — тот же протокол запуска, которым служба
# поднимается штатно. Отдельной облегчённой проверки здесь нет намеренно:
# ворота, отличающиеся от запуска, проверяют не то, что потом работает.
set -uo pipefail

BASE=/srv/site-factory/control-api
RELEASES="$BASE/releases"
CURRENT="$BASE/current"
PREVIOUS="$BASE/previous"
SRC_REPO=/srv/site-factory/repo
DATA_ROOT=/srv/site-factory/repo
UNIT=site-factory-control-api.service
KEEP=5
READY_URL="http://127.0.0.1:8790/api/v1/ready"
READY_TIMEOUT=60

die() { echo "ОШИБКА: $*" >&2; exit 1; }
say() { echo "[$(date -u +%H:%M:%S)] $*"; }

usage() {
  cat <<'USAGE'
Использование:
  deploy-control-api.sh deploy <sha> [--source <репозиторий>] [--dry-run]
  deploy-control-api.sh rollback [--to <sha>]
  deploy-control-api.sh status
USAGE
}

# Отпечаток содержимого релиза: аналог digest образа для некотейнерной службы.
# Считается по отсортированному списку файлов кода, без окружения и кэшей —
# иначе он менялся бы от пересборки интерпретатора при том же коде.
digest_of() {
  local dir="$1"
  ( cd "$dir" && find . -type f \
      -not -path "./.venv/*" -not -path "./.git/*" \
      -not -name "*.pyc" -not -path "./__pycache__/*" \
      -print0 | sort -z | xargs -0 sha256sum 2>/dev/null | sha256sum | cut -d" " -f1 )
}

current_sha() { [ -L "$CURRENT" ] && basename "$(readlink -f "$CURRENT")" || echo ""; }

cmd_status() {
  say "текущий релиз: $(current_sha)"
  [ -L "$PREVIOUS" ] && say "предыдущий:    $(basename "$(readlink -f "$PREVIOUS")")" \
                     || say "предыдущий:    нет"
  say "релизов на диске: $(ls -1 "$RELEASES" 2>/dev/null | wc -l)"
  systemctl is-active "$UNIT" >/dev/null 2>&1 && say "служба: активна" || say "служба: НЕ активна"
  curl -sf -m 5 "$READY_URL" >/dev/null 2>&1 && say "готовность: да" || say "готовность: НЕТ"
}

wait_ready() {
  local deadline=$(( $(date +%s) + READY_TIMEOUT ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    if curl -sf -m 5 "$READY_URL" 2>/dev/null | grep -q '"ready": *true'; then
      return 0
    fi
    sleep 1
  done
  return 1
}

swap_to() {
  # Подмена ссылки через временную и rename: ln -sf над существующей ссылкой
  # не атомарен, между удалением и созданием current не существует.
  local target="$1"
  local tmp="$BASE/.current.$$"
  ln -s "$target" "$tmp" || die "не создана временная ссылка"
  mv -T "$tmp" "$CURRENT" || { rm -f "$tmp"; die "подмена ссылки не удалась"; }
}

cmd_deploy() {
  local sha="${1:-}"; shift || true
  local source_repo="$SRC_REPO" dry=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --source) source_repo="${2:-}"; shift 2 ;;
      --dry-run) dry=1; shift ;;
      *) die "неизвестный аргумент: $1" ;;
    esac
  done
  [ -n "$sha" ] || { usage; exit 64; }

  local full
  full="$(git -C "$source_repo" rev-parse "$sha" 2>/dev/null)" || die "SHA $sha не найден в $source_repo"
  local target="$RELEASES/$full"

  say "выкладка $full из $source_repo"
  mkdir -p "$RELEASES" || die "нет каталога релизов"

  if [ -d "$target" ]; then
    say "релиз уже собран, пересборка не нужна"
  else
    say "сборка релиза"
    local staging="$RELEASES/.staging.$$"
    rm -rf "$staging"; mkdir -p "$staging"
    # git archive, а не копирование: в релиз попадает ровно то, что в коммите,
    # без незафиксированных правок и мусора рабочего дерева.
    git -C "$source_repo" archive "$full" | tar -x -C "$staging" \
      || { rm -rf "$staging"; die "архив коммита не распакован"; }
    # В репозитории .venv отслеживается как символическая ссылка на окружение
    # разработчика. После распаковки путь занят этой ссылкой, и venv в него не
    # создаётся: "Unable to create directory". Релиз обязан иметь собственное
    # окружение, не зависящее от чужого домашнего каталога.
    rm -rf "$staging/.venv"
    say "создание окружения"
    python3 -m venv "$staging/.venv" >/dev/null 2>&1 || { rm -rf "$staging"; die "venv не создан"; }
    "$staging/.venv/bin/pip" install -q --upgrade pip >/dev/null 2>&1
    "$staging/.venv/bin/pip" install -q -r "$staging/requirements.txt" \
      || { rm -rf "$staging"; die "зависимости не установлены"; }
    "$staging/.venv/bin/pip" install -q pyyaml >/dev/null 2>&1
    mv -T "$staging" "$target" || { rm -rf "$staging"; die "релиз не перемещён"; }
  fi

  local dg; dg="$(digest_of "$target")"
  say "отпечаток релиза: ${dg:0:16}"

  # Ворота: тот же протокол, которым поднимается служба.
  say "протокол запуска на новом релизе"
  ( cd "$target" && FACTORY_ROOT="$DATA_ROOT" PYTHONPATH="$target" \
      "$target/.venv/bin/python" -c "
import os, sys
from factory.site_engine.api import startup
r = startup.run(os.environ.get('FACTORY_ROOT', '.'), dict(os.environ))
print(r.as_text())
sys.exit(0 if r.ok else 70)
" ) || die "протокол запуска не пройден: релиз не переключён"

  if [ "$dry" -eq 1 ]; then
    say "dry-run: переключение не выполняется"
    return 0
  fi

  local before; before="$(current_sha)"
  if [ -n "$before" ]; then
    rm -f "$PREVIOUS"; ln -s "$RELEASES/$before" "$PREVIOUS"
    say "предыдущий релиз запомнен: ${before:0:12}"
  fi

  swap_to "$target"
  say "ссылка current переключена на ${full:0:12}"

  say "перезапуск службы"
  sudo -n systemctl restart "$UNIT" || die "служба не перезапущена"

  if wait_ready; then
    say "служба готова"
  else
    say "готовность не подтверждена за ${READY_TIMEOUT}s — откат"
    cmd_rollback
    die "выкладка отменена, выполнен откат"
  fi

  # Манифест релиза: что именно сейчас работает.
  cat > "$BASE/release-manifest.json" <<MANIFEST
{
  "sha": "$full",
  "digest": "$dg",
  "deployed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "previous_sha": "$before",
  "unit": "$UNIT",
  "data_root": "$DATA_ROOT",
  "source": "$source_repo"
}
MANIFEST
  say "манифест записан"

  # Уборка: релизы, на которые никто не ссылается, старше последних KEEP.
  local keep_sha="$full" prev_sha="$before"
  ls -1t "$RELEASES" 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
    [ "$old" = "$keep_sha" ] && continue
    [ "$old" = "$prev_sha" ] && continue
    say "удаляю старый релиз ${old:0:12}"
    rm -rf "${RELEASES:?}/$old"
  done
  cmd_status
}

cmd_rollback() {
  local to=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --to) to="${2:-}"; shift 2 ;;
      *) die "неизвестный аргумент: $1" ;;
    esac
  done
  local target
  if [ -n "$to" ]; then
    target="$RELEASES/$to"
    [ -d "$target" ] || die "релиз $to не найден на диске"
  else
    [ -L "$PREVIOUS" ] || die "предыдущего релиза нет: откатываться некуда"
    target="$(readlink -f "$PREVIOUS")"
  fi
  say "откат на $(basename "$target")"

  # Тот же протокол и на откате: версия, которая не проходит проверку, не
  # станет рабочей только оттого, что она старая.
  ( cd "$target" && FACTORY_ROOT="$DATA_ROOT" PYTHONPATH="$target" \
      "$target/.venv/bin/python" -c "
import os, sys
from factory.site_engine.api import startup
r = startup.run(os.environ.get('FACTORY_ROOT', '.'), dict(os.environ))
print(r.as_text())
sys.exit(0 if r.ok else 70)
" ) || die "протокол запуска не пройден на целевом релизе"

  local before; before="$(current_sha)"
  swap_to "$target"
  sudo -n systemctl restart "$UNIT" || die "служба не перезапущена"
  if wait_ready; then
    say "откат выполнен, служба готова"
    [ -n "$before" ] && { rm -f "$PREVIOUS"; ln -s "$RELEASES/$before" "$PREVIOUS"; }
  else
    die "после отката служба не готова — требуется вмешательство"
  fi
  cmd_status
}

case "${1:-}" in
  deploy)   shift; cmd_deploy "$@" ;;
  rollback) shift; cmd_rollback "$@" ;;
  status)   cmd_status ;;
  *)        usage; exit 64 ;;
esac
