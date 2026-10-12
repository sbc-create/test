#!/usr/bin/env bash
# Один прогон технического SEO: захват задачи → Claude Code без интерфейса готовит
# ветку в отдельной рабочей копии → вердикт ПО СЛЕДАМ (seo-tech-verify) → запись.
#
#   seo-tech-run.sh                 — штатно (из seo-tech-run.service)
#   CLAUDE_BIN=/path seo-tech-run.sh — подмена исполнителя для проверки обёртки
#
# Push, PR и выпуск прогону не принадлежат: учётные данные git закрыты юнитом
# (InaccessiblePaths), а вердикт требует, чтобы у ветки не было удалённого двойника.
# Коды: 0 — VERIFIED или честное «задач нет»; 2 — неполный (юнит падает — это
# уведомление); 75 — занято другим прогоном; 70 — шаг захвата неисправен.
set -uo pipefail

REPO=/home/claude/wt-portable-site-cell-01
STATE="$REPO/var/seo-tech"
CLAUDE_BIN="${CLAUDE_BIN:-/home/claude/.local/bin/claude}"
TRIGGER="${SEO_TECH_TRIGGER:-manual}"
LIMIT_S="${SEO_TECH_TIMEOUT:-1500}"

mkdir -p "$STATE"
cd "$REPO" || exit 1

exec 9>"$STATE/run.lock"
if ! flock -n 9; then
  echo "seo-tech-run: идёт другой прогон" >&2
  exit 75
fi

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
STARTED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

NEXT="$(python3 -m seo_operator.cli seo-tech-next --run-id "$RUN_ID")"
NEXT_RC=$?
printf '{"at": "%s", "trigger": "%s", "run_id": "%s", "next_rc": %s}\n' "$STARTED" "$TRIGGER" "$RUN_ID" "$NEXT_RC" >> "$STATE/gate.jsonl"
case "$NEXT_RC" in
  10) ;;
  0) exit 0 ;;
  *) echo "seo-tech-run: захват неисправен (код $NEXT_RC): $NEXT" >&2; exit 70 ;;
esac

PROMPT="$(sed "s/{{RUN_ID}}/$RUN_ID/g" docs/seo-tech/SEO_TECH_RUN_PROMPT.md)"
timeout "$LIMIT_S" "$CLAUDE_BIN" -p "$PROMPT" --output-format json \
  --max-turns "${SEO_TECH_MAX_TURNS:-150}" \
  > "$STATE/$RUN_ID.claude.json" 2> "$STATE/$RUN_ID.stderr"
MODEL_RC=$?
FINISHED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

EXTRA="$(printf '{"trigger": "%s", "started_at": "%s", "finished_at": "%s", "model_exit": %s}' \
  "$TRIGGER" "$STARTED" "$FINISHED" "$MODEL_RC")"
python3 -m seo_operator.cli seo-tech-verify --run-id "$RUN_ID" --record --extra "$EXTRA" \
  > "$STATE/$RUN_ID.verify.json"
exit $(( $? == 0 ? 0 : 2 ))
