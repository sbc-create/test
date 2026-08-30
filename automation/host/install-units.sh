#!/usr/bin/env bash
# Install (or refresh) the site-factory systemd units on a control host.
#
# Idempotent: re-running replaces the unit files and reloads systemd without
# changing which timers are enabled. Enabling is a separate, deliberate step,
# because a timer that starts doing real work must be turned on by a person who
# knows the queue has real input.
set -euo pipefail

SRC="$(cd "$(dirname "$0")/systemd" && pwd)"
DEST=/etc/systemd/system

# Корень того дерева, ИЗ КОТОРОГО ставят. Шаблоны написаны под канонический
# /srv/site-factory/repo, но ставить их могут из review-worktree — и тогда
# WorkingDirectory указывал бы в одно дерево, а ExecStart в другое. Служба при
# этом запускается и молча исполняет чужой код: worktree рядом обычно стоит на
# другой ветке. Подстановка убирает целый класс таких расхождений.
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TEMPLATE_ROOT=/srv/site-factory/repo

[ "$(id -u)" -eq 0 ] || { echo "нужен root: sudo $0" >&2; exit 1; }

echo "устанавливаю unit'ы из $REPO_ROOT"
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

for unit in "$SRC"/*.service "$SRC"/*.timer; do
  name="$(basename "$unit")"
  sed "s#${TEMPLATE_ROOT}#${REPO_ROOT}#g" "$unit" > "$TMP/$name"
  install -m 0644 -o root -g root "$TMP/$name" "$DEST/$name"
  echo "installed $name"
done

# Drop-in'ы: настройки, которые нельзя держать в самом unit-файле, потому что он
# общий шаблон, а значения зависят от того, что мы измерили на этом хосте.
#
# До сих пор они лежали только на диске и в репозитории не значились. Один такой
# файл на диске переживал правку, о которой не знал никто: интервал таймера
# подняли, а сам таймер запустить забыли, и автообновление каталога молча
# перестало происходить. Теперь их источник — репозиторий, а расхождение видно
# сравнением.
DROPIN_SRC="$SRC/dropins"
if [ -d "$DROPIN_SRC" ]; then
  for dir in "$DROPIN_SRC"/*.d; do
    [ -d "$dir" ] || continue
    unit_dir="$(basename "$dir")"
    install -d -m 0755 -o root -g root "$DEST/$unit_dir"
    for conf in "$dir"/*.conf; do
      [ -f "$conf" ] || continue
      name="$(basename "$conf")"
      sed "s#${TEMPLATE_ROOT}#${REPO_ROOT}#g" "$conf" > "$TMP/$name"
      install -m 0644 -o root -g root "$TMP/$name" "$DEST/$unit_dir/$name"
      echo "installed $unit_dir/$name"
    done
  done
fi

systemctl daemon-reload

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
