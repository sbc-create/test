#!/usr/bin/env bash
#
# Репетиция восстановления (ТЗ §13).
#
# Проверяет ровно то, что нужно проверить: что из бэкапа поднимается РАБОЧЕЕ
# состояние на ЧИСТОМ target, а не что бэкап существует. Результат пишется
# в evidence-файл без секретов.
#
# Всегда работает на отдельном target и никогда не трогает рабочий каталог.
set -euo pipefail

TARGET=""
BACKUP_DIR="${SEO_BACKUP_DIR:-/var/backups/seo-operator}"
EVIDENCE_DIR="${SEO_EVIDENCE_DIR:-/var/log/seo-operator/evidence}"
REPO_ROOT="${SEO_REPO_ROOT:-/opt/seo-operator}"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2;;
    --backup-dir) BACKUP_DIR="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

[[ -n "$TARGET" ]] || { echo "usage: restore-drill.sh --target <dir>" >&2; exit 2; }

# Защита от катастрофической опечатки: репетиция не запускается поверх рабочего state.
if [[ "$TARGET" == "${SEO_PRODUCTION_STATE_DIR:-/var/lib/seo-operator}" ]]; then
  echo "FAIL: target совпадает с рабочим каталогом состояния — репетиция отменена." >&2
  exit 3
fi

fail() {
  local reason="$1"
  mkdir -p "$EVIDENCE_DIR"
  cat > "$EVIDENCE_DIR/restore-drill-$(date -u +%Y%m%d).json" <<JSON
{
  "started_at": "$STARTED_AT",
  "finished_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "result": "fail",
  "reason": "$reason",
  "target": "$TARGET"
}
JSON
  echo "RESTORE_DRILL=fail ($reason)" >&2
  exit 1
}

echo "== 1. Чистый target =="
rm -rf "${TARGET:?}"
mkdir -p "$TARGET"

echo "== 2. Последний бэкап =="
LATEST="$(find "$BACKUP_DIR" -maxdepth 1 -name 'seo-state-*.tar.gz*' -type f 2>/dev/null \
          | sort | tail -1 || true)"
[[ -n "$LATEST" ]] || fail "в $BACKUP_DIR нет ни одного бэкапа"
echo "используем: $(basename "$LATEST")"

echo "== 3. Расшифровка и распаковка =="
if [[ "$LATEST" == *.gpg || "$LATEST" == *.age ]]; then
  # Ключ берётся из Secret Hub, а не из файла рядом с бэкапом.
  "$REPO_ROOT/deploy/decrypt-backup.sh" "$LATEST" "$TARGET" || fail "расшифровка не удалась"
else
  tar -xzf "$LATEST" -C "$TARGET" || fail "распаковка не удалась"
fi

echo "== 4. Целостность =="
if [[ -f "$LATEST.sha256" ]]; then
  (cd "$(dirname "$LATEST")" && sha256sum -c "$(basename "$LATEST").sha256") \
    || fail "контрольная сумма не совпала"
else
  echo "ВНИМАНИЕ: у бэкапа нет .sha256 — целостность не подтверждена"
fi

echo "== 5. Миграции на восстановленном состоянии =="
SEO_STATE_DIR="$TARGET" PYTHONPATH="$REPO_ROOT/src" \
  "$REPO_ROOT/.venv/bin/python" -m seo_operator.cli migrate --check || fail "миграции не применяются"

echo "== 6. Проверка audit-цепочки =="
SEO_STATE_DIR="$TARGET" PYTHONPATH="$REPO_ROOT/src" \
  "$REPO_ROOT/.venv/bin/python" -m seo_operator.cli audit verify --json \
  || fail "audit-цепочка нарушена в восстановленном состоянии"

echo "== 7. Read-only сверка: данные на месте =="
ROWS="$(SEO_STATE_DIR="$TARGET" PYTHONPATH="$REPO_ROOT/src" \
        "$REPO_ROOT/.venv/bin/python" -m seo_operator.cli state count --json \
        | python3 -c 'import json,sys; print(json.load(sys.stdin)["observations"])')"
[[ "${ROWS:-0}" -gt 0 ]] || fail "в восстановленном состоянии нет наблюдений"
echo "наблюдений восстановлено: $ROWS"

echo "== 8. Dry-run на восстановленном состоянии =="
SEO_STATE_DIR="$TARGET" PYTHONPATH="$REPO_ROOT/src" \
  "$REPO_ROOT/.venv/bin/python" -m seo_operator.cli daily-run --json > /dev/null \
  || fail "dry-run на восстановленном состоянии не прошёл"

FINISHED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
RTO_SECONDS=$(( $(date -u -d "$FINISHED_AT" +%s) - $(date -u -d "$STARTED_AT" +%s) ))
BACKUP_AGE_HOURS=$(( ( $(date -u +%s) - $(stat -c %Y "$LATEST") ) / 3600 ))

mkdir -p "$EVIDENCE_DIR"
cat > "$EVIDENCE_DIR/restore-drill-$(date -u +%Y%m%d).json" <<JSON
{
  "started_at": "$STARTED_AT",
  "finished_at": "$FINISHED_AT",
  "result": "pass",
  "target": "$TARGET",
  "backup_file": "$(basename "$LATEST")",
  "backup_age_hours": $BACKUP_AGE_HOURS,
  "observations_restored": $ROWS,
  "rto_seconds": $RTO_SECONDS,
  "rpo_hours": $BACKUP_AGE_HOURS,
  "note": "Секреты в evidence не входят по построению: файл содержит только метрики восстановления."
}
JSON

echo "RESTORE_DRILL=pass RTO=${RTO_SECONDS}s RPO=${BACKUP_AGE_HOURS}h"
