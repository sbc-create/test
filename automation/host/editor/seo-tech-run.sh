#!/usr/bin/env bash
# Один прогон технического SEO: задача → Claude Code без интерфейса готовит ветку в
# отдельной рабочей копии → вердикт ПО СЛЕДАМ (seo-tech-verify) → запись.
#
#   seo-tech-run.sh                  — штатно (из seo-tech-run.service; таймер перезапускает
#                                      его через минуту после завершения, пока есть задачи)
#   CLAUDE_BIN=/path seo-tech-run.sh — подмена исполнителя для проверки обёртки
#   SEO_TECH_STATE=/dir              — отдельное состояние (приёмка, не трогает настоящее)
#
# Push, PR и выпуск прогону не принадлежат: учётные данные git закрыты юнитом
# (InaccessiblePaths), вердикт требует, чтобы у ветки не было удалённого двойника.
# Выпуск проверенных веток — отдельная служба seo-tech-publish.
#
# Коды: 0 — VERIFIED или честное «задач нет»; 2 — неполный вердикт (записан, очередь идёт
# дальше); 70 — неисправна предполётная проверка или шаг захвата; 73 — состояние или файл
# блокировки недоступны для записи (НЕ «занято»); 75 — занято другим прогоном.
set -uo pipefail

REPO=/home/claude/wt-portable-site-cell-01
STATE="${SEO_TECH_STATE:-$REPO/var/seo-tech}"
CLAUDE_BIN="${CLAUDE_BIN:-/home/claude/.local/bin/claude}"
TRIGGER="${SEO_TECH_TRIGGER:-manual}"
LIMIT_S="${SEO_TECH_TIMEOUT:-1500}"          # модель
GRACE_S="${SEO_TECH_GRACE:-60}"              # после SIGTERM — SIGKILL
UNIT_BUDGET_S="${SEO_TECH_UNIT_BUDGET:-4500}"  # = TimeoutStartSec юнита: после него systemd убьёт всё
BACKLOG_EVERY_S="${SEO_TECH_BACKLOG_EVERY:-3600}"
export SEO_TECH_STATE="$STATE"
export SEO_TECH_OWNER_PID=$$                 # захват живёт ровно столько, сколько этот процесс

cd "$REPO" || { echo "seo-tech-run: нет каталога $REPO" >&2; exit 70; }

# 1. Состояние доступно для записи — ДО блокировки и захвата.
if ! mkdir -p "$STATE" 2>/dev/null || ! ( : >>"$STATE/.writable" ) 2>/dev/null; then
  echo "seo-tech-run: каталог состояния $STATE недоступен для записи" >&2
  exit 73
fi

# 2. Файл блокировки: ошибка ОТКРЫТИЯ — это неисправность, а не «занято».
if ! exec 9>>"$STATE/run.lock"; then
  echo "seo-tech-run: не открыть файл блокировки $STATE/run.lock" >&2
  exit 73
fi
if ! flock -n 9; then
  echo "seo-tech-run: идёт другой прогон" >&2
  exit 75
fi

# 3. Предполётная проверка — до захвата: без неё прогон съел бы попытку исправной задачи.
fail() { echo "seo-tech-run: предполётная проверка: $*" >&2; exit 70; }
test -s docs/seo-tech/SEO_TECH_RUN_PROMPT.md || fail "нет файла задания docs/seo-tech/SEO_TECH_RUN_PROMPT.md"
test -x "$CLAUDE_BIN" || fail "исполнитель $CLAUDE_BIN не найден или не исполняемый"
command -v git >/dev/null || fail "нет git"
command -v timeout >/dev/null || fail "нет timeout"
python3 -c "import seo_operator.tech_run" 2>/dev/null || fail "не импортируется seo_operator.tech_run"

# 4. Есть ли готовая задача — без захвата и без модели. Нет — пополнение очереди
#    (не чаще BACKLOG_EVERY_S) и ещё одна дешёвая проверка.
python3 -m seo_operator.cli seo-tech-next --peek >/dev/null
PEEK_RC=$?
if [ "$PEEK_RC" -eq 0 ] && [ "${SEO_TECH_BACKLOG:-1}" = 1 ]; then
  python3 -m seo_operator.cli seo-tech-backlog --if-older "$BACKLOG_EVERY_S" >>"$STATE/backlog.log" 2>&1
  python3 -m seo_operator.cli seo-tech-next --peek >/dev/null
  PEEK_RC=$?
fi
case "$PEEK_RC" in
  10) ;;
  0) exit 0 ;;
  *) fail "очередь не читается (код $PEEK_RC)" ;;
esac

# Секунды плюс PID: два прогона в одну секунду не делят один идентификатор.
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
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
# timeout -k: после LIMIT_S — SIGTERM, ещё через GRACE_S — SIGKILL. 124 — тайм-аут, 137 — добит.
timeout -k "$GRACE_S" "$LIMIT_S" "$CLAUDE_BIN" -p "$PROMPT" --output-format json \
  --max-turns "${SEO_TECH_MAX_TURNS:-150}" \
  > "$STATE/$RUN_ID.claude.json" 2> "$STATE/$RUN_ID.stderr"
MODEL_RC=$?
FINISHED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Доводка: штамп манифеста и замок штатными инструментами витрины — механически, не моделью.
timeout -k 30 600 python3 -m seo_operator.cli seo-tech-finalize --run-id "$RUN_ID" \
  > "$STATE/$RUN_ID.finalize.json" 2>&1

EXTRA="$(printf '{"trigger": "%s", "started_at": "%s", "finished_at": "%s", "model_exit": %s}' \
  "$TRIGGER" "$STARTED" "$FINISHED" "$MODEL_RC")"
# Вердикт тоже под пределом: зависшая проверка не держит исполнителя. Предел — всё, что
# осталось от бюджета юнита (минус запас), а не фиксированные 40 мин: полный run.sh Lords
# под CPUQuota юнита идёт дольше (T092, 14.10). Явный SEO_TECH_VERIFY_TIMEOUT — сверху.
VERIFY_LIMIT_S=$(( UNIT_BUDGET_S - SECONDS - 180 ))
if [ -n "${SEO_TECH_VERIFY_TIMEOUT:-}" ] && [ "$SEO_TECH_VERIFY_TIMEOUT" -lt "$VERIFY_LIMIT_S" ]; then
  VERIFY_LIMIT_S="$SEO_TECH_VERIFY_TIMEOUT"
fi
[ "$VERIFY_LIMIT_S" -lt 300 ] && VERIFY_LIMIT_S=300
# Если вердикт добьют, итога не будет — следующий прогон закроет захват как INTERRUPTED.
timeout -k 60 "$VERIFY_LIMIT_S" python3 -m seo_operator.cli seo-tech-verify --run-id "$RUN_ID" --record --extra "$EXTRA" \
  > "$STATE/$RUN_ID.verify.json"
VERIFY_RC=$?
case "$VERIFY_RC" in
  0) exit 0 ;;
  124|137) echo "seo-tech-run: вердикт не уложился в ${VERIFY_LIMIT_S} с" >&2; exit 2 ;;
  *) exit 2 ;;
esac
