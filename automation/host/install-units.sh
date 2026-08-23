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

[ "$(id -u)" -eq 0 ] || { echo "нужен root: sudo $0" >&2; exit 1; }

for unit in "$SRC"/*.service "$SRC"/*.timer; do
  install -m 0644 -o root -g root "$unit" "$DEST/$(basename "$unit")"
  echo "installed $(basename "$unit")"
done

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
systemctl list-timers 'site-factory*' --no-pager
