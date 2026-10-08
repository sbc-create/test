#!/usr/bin/env bash
# Один запуск фонового редактора: Claude Code без интерфейса + независимая проверка.
#
#   editor-run.sh            — штатно (из editor-run.service)
#   CLAUDE_BIN=/path editor-run.sh  — подмена исполнителя для проверки обёртки
#
# Порядок: блокировка → запуск модели с заданием docs/editor/EDITOR_RUN_PROMPT.md
# → проверка ПО СЛЕДАМ (seo_operator.editor_run: очередь, история публикаций,
# публичная страница) → запись run.json. Код выхода — по проверке, а не по
# самоотчёту модели: 0 — полный запуск или честное «задач нет», 2 — неполный,
# 75 — занято другим запуском.
set -uo pipefail

REPO=/home/claude/wt-portable-site-cell-01
STATE="$REPO/var/editor-runs"
CLAUDE_BIN="${CLAUDE_BIN:-/home/claude/.local/bin/claude}"
TRIGGER="${EDITOR_RUN_TRIGGER:-manual}"
LIMIT_S="${EDITOR_RUN_TIMEOUT:-1500}"

mkdir -p "$STATE"
cd "$REPO" || exit 1

exec 9>"$STATE/run.lock"
if ! flock -n 9; then
  echo "editor-run: идёт другой запуск" >&2
  exit 75
fi

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
STARTED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
PROMPT="$(sed "s/{{RUN_ID}}/$RUN_ID/g" docs/editor/EDITOR_RUN_PROMPT.md)"

timeout "$LIMIT_S" "$CLAUDE_BIN" -p "$PROMPT" --output-format json --max-turns 80 \
  > "$STATE/$RUN_ID.claude.json" 2> "$STATE/$RUN_ID.stderr"
MODEL_RC=$?
FINISHED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

python3 -m seo_operator.cli editor-run-verify --run-id "$RUN_ID" \
  --started-at "$STARTED" --finished-at "$FINISHED" --out "$STATE/$RUN_ID.verify.json" > /dev/null
VERIFY_RC=$?

# Самоотчёт модели — только последняя строка JSON; хранится рядом, решает проверка.
SELF="$(python3 - "$STATE/$RUN_ID.claude.json" <<'PY'
import json, sys
try:
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    text = data.get("result") or ""
    line = [l for l in text.strip().splitlines() if l.strip().startswith("{")][-1]
    print(json.dumps(json.loads(line), ensure_ascii=False))
except Exception as exc:  # noqa: BLE001
    print(json.dumps({"outcome": "UNPARSED", "note": f"{type(exc).__name__}"}))
PY
)"

python3 - "$STATE" "$RUN_ID" "$TRIGGER" "$STARTED" "$FINISHED" "$MODEL_RC" "$VERIFY_RC" "$SELF" <<'PY'
import json, sys, pathlib
state, run_id, trigger, started, finished, model_rc, verify_rc, self_report = sys.argv[1:]
verify = json.loads(pathlib.Path(state, f"{run_id}.verify.json").read_text(encoding="utf-8"))
self_report = json.loads(self_report)
no_task = self_report.get("outcome") in ("NO_TASK", "SOURCES_MISSING") and not verify["steps"]["published"]
record = {"run_id": run_id, "trigger": trigger, "started_at": started, "finished_at": finished,
          "model_exit": int(model_rc), "verified_complete": verify["complete"], "steps": verify["steps"],
          "self_report": self_report, "honest_no_publication": no_task,
          "verdict": "COMPLETE" if verify["complete"] else ("NO_PUBLICATION" if no_task else "INCOMPLETE")}
pathlib.Path(state, f"{run_id}.run.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
with open(pathlib.Path(state, "runs.jsonl"), "a", encoding="utf-8") as fh:
    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
print(json.dumps(record, ensure_ascii=False))
PY

if [ "$VERIFY_RC" -eq 0 ]; then exit 0; fi
case "$SELF" in *NO_TASK*|*SOURCES_MISSING*) exit 0 ;; esac
exit 2
