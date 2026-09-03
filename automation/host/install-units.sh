#!/usr/bin/env bash
# Install (or refresh) the site-factory systemd units on a control host.
#
# Idempotent: re-running replaces the unit files and reloads systemd without
# changing which timers are enabled. Enabling is a separate, deliberate step,
# because a timer that starts doing real work must be turned on by a person who
# knows the queue has real input.
#
# Можно поставить не всё, а названные unit'ы:
#
#     install-units.sh                                  — все, как раньше
#     install-units.sh yummy-site-backup.service yummy-site-backup.timer
#
# Зачем выбор. Ставить всё из ветки, где менялся один unit, значит заодно
# заменить остальные их версиями из этой ветки — а они там могли не меняться
# вовсе или меняться чужой рукой. Владельцу приходилось выбирать между
# «поставить лишнее» и «не ставить ничего», и он обоснованно выбирал второе.
#
# При явном списке timer'ы НЕ включаются: включение и здесь остаётся отдельным
# шагом, а какой именно timer уместно поднять, знает тот, кто ставит.
set -euo pipefail

SRC="$(cd "$(dirname "$0")/systemd" && pwd)"
DEST=/etc/systemd/system

# Что ставим: явный список или всё, что есть. Отбор идёт ДО проверки root —
# опечатку в имени unit'а незачем ловить только под sudo.
SELECTED=()
if [ "$#" -gt 0 ]; then
  for name in "$@"; do
    if [ ! -f "$SRC/$name" ]; then
      echo "нет такого unit'а в $SRC: $name" >&2
      exit 66
    fi
    SELECTED+=("$SRC/$name")
  done
else
  SELECTED=("$SRC"/*.service "$SRC"/*.timer)
fi

# Корень того дерева, ИЗ КОТОРОГО ставят. Шаблоны написаны под канонический
# /srv/site-factory/repo, но ставить их могут из review-worktree — и тогда
# WorkingDirectory указывал бы в одно дерево, а ExecStart в другое. Служба при
# этом запускается и молча исполняет чужой код: worktree рядом обычно стоит на
# другой ветке. Подстановка убирает целый класс таких расхождений.
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TEMPLATE_ROOT=/srv/site-factory/repo

[ "$(id -u)" -eq 0 ] || { echo "нужен root: sudo $0" >&2; exit 1; }

echo "устанавливаю unit'ы из $REPO_ROOT"
[ "$#" -gt 0 ] && echo "  только названные: $*"
if [ "$REPO_ROOT" != "$TEMPLATE_ROOT" ]; then
  echo "  пути в шаблонах: $TEMPLATE_ROOT -> $REPO_ROOT"
fi

if [ ! -x "$REPO_ROOT/.venv/bin/python" ]; then
  echo "нет окружения $REPO_ROOT/.venv — unit'ы с FACTORY_REQUIRE_VENV=1 откажутся стартовать." >&2
  echo "создай его: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 78
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

for unit in "${SELECTED[@]}"; do
  name="$(basename "$unit")"
  sed "s#${TEMPLATE_ROOT}#${REPO_ROOT}#g" "$unit" > "$TMP/$name"
  install -m 0644 -o root -g root "$TMP/$name" "$DEST/$name"
  echo "installed $name"
done

systemctl daemon-reload

# Явный список — значит ставил человек, знающий, что именно поднимает. Включать
# за него чужие timer'ы здесь было бы самоуправством.
if [ "$#" -gt 0 ]; then
  echo
  echo "timer'ы не включены: при явном списке это делает тот, кто ставил."
  for name in "$@"; do
    case "$name" in
      *.timer) echo "  systemctl enable --now $name" ;;
    esac
  done
  exit 0
fi

# Safe by default: monitoring, backup and read-only self-checks run on their own.
# site-factory-worker.timer is deliberately absent from this list.
for timer in site-factory-health.timer \
             site-factory-backup.timer \
             site-factory-selfcheck.timer \
             site-factory-seo-dryrun.timer \
             site-factory-restore-proof.timer; do
  systemctl enable "$timer" >/dev/null
  systemctl start "$timer"
  echo "enabled $timer"
done

echo
echo "НЕ включены намеренно:"
echo "  site-factory-worker.timer — очередь пуста, ни одна цель не production_capable"
echo "  site-factory-analytics-collect.timer — ни один сайт не развёрнут: ежедневный"
echo "      сбор показателей давал бы «0 визитов» вместо «не измерено»."
echo "      Включать после появления первого работающего production-сайта:"
echo "      systemctl enable --now site-factory-analytics-collect.timer"
echo "  site-factory-analytics-apply.service — разовое создание счётчиков Метрики,"
echo "      запускает человек: systemctl start site-factory-analytics-apply.service"
systemctl list-timers 'site-factory*' --no-pager
