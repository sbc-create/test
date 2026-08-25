#!/usr/bin/env bash
#
# Установка SEO-оператора на чистый хост (ТЗ §13).
#
# Процедура documented restore: новый хост -> checkout утверждённого commit ->
# зависимости -> миграции -> Secret Hub -> восстановление данных -> dry-run ->
# read-only сверка -> включение расписания.
#
# Скрипт НЕ включает расписание автоматически: последний шаг делает человек
# после прочтения evidence. Автоматически включённый планировщик на непроверенном
# хосте начнёт писать в production раньше, чем кто-то посмотрит на результат.
set -euo pipefail

REPO_URL="${SEO_REPO_URL:-}"
COMMIT="${SEO_COMMIT:-}"
PREFIX="${SEO_PREFIX:-/opt/seo-operator}"
STATE_DIR="${SEO_STATE_DIR:-/var/lib/seo-operator}"
LOG_DIR="${SEO_LOG_DIR:-/var/log/seo-operator}"
RUN_USER="${SEO_USER:-seo-operator}"

usage() {
  cat >&2 <<'USAGE'
usage: install.sh --repo <git-url> --commit <sha> [--prefix /opt/seo-operator]

Обязателен ТОЧНЫЙ commit: разворачивать «последний main» на чистом хосте значит
получить состояние, которое никто не проверял.
USAGE
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO_URL="$2"; shift 2;;
    --commit) COMMIT="$2"; shift 2;;
    --prefix) PREFIX="$2"; shift 2;;
    *) usage;;
  esac
done
[[ -n "$REPO_URL" && -n "$COMMIT" ]] || usage

echo "== 1. Пользователь и каталоги =="
if ! id -u "$RUN_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$PREFIX" --shell /usr/sbin/nologin "$RUN_USER"
fi
install -d -o "$RUN_USER" -g "$RUN_USER" -m 0750 "$PREFIX" "$STATE_DIR" "$LOG_DIR"

echo "== 2. Checkout утверждённого commit =="
if [[ -d "$PREFIX/.git" ]]; then
  git -C "$PREFIX" fetch --all --prune
else
  git clone "$REPO_URL" "$PREFIX"
fi
git -C "$PREFIX" checkout --detach "$COMMIT"
echo "развёрнут commit: $(git -C "$PREFIX" rev-parse HEAD)"

echo "== 3. Зависимости =="
python3 -m venv "$PREFIX/.venv"
"$PREFIX/.venv/bin/pip" install --quiet --upgrade pip
"$PREFIX/.venv/bin/pip" install --quiet -e "$PREFIX"

echo "== 4. Миграции =="
SEO_STATE_DIR="$STATE_DIR" PYTHONPATH="$PREFIX/src" \
  "$PREFIX/.venv/bin/python" -m seo_operator.cli migrate --apply

echo "== 5. Secret Hub =="
if [[ -z "${SEO_SECRET_HUB_URL:-}" ]]; then
  cat >&2 <<'WARN'
SEO_SECRET_HUB_URL не задан. Оператор будет работать в режиме BLOCKED_SECRET:
сбор из Метрики и Вебмастера недоступен, read-only функции работают.
Это ОЖИДАЕМОЕ состояние до подключения хранилища — не обходите его
переменными окружения с токенами (ТЗ §12).
WARN
else
  SEO_STATE_DIR="$STATE_DIR" PYTHONPATH="$PREFIX/src" \
    "$PREFIX/.venv/bin/python" -m seo_operator.cli secrets check --json
fi

echo "== 6. Восстановление данных (если есть бэкап) =="
if [[ -n "${SEO_BACKUP_DIR:-}" ]]; then
  "$PREFIX/deploy/restore-drill.sh" --target "$STATE_DIR" --backup-dir "$SEO_BACKUP_DIR" \
    || echo "ВНИМАНИЕ: восстановление не удалось, состояние пустое"
else
  echo "бэкап не указан — стартуем с пустого состояния"
fi

echo "== 7. Фиксация защищённого ядра и dry-run =="
SEO_STATE_DIR="$STATE_DIR" PYTHONPATH="$PREFIX/src" \
  "$PREFIX/.venv/bin/python" -m seo_operator.cli guardrails baseline --json
SEO_STATE_DIR="$STATE_DIR" PYTHONPATH="$PREFIX/src" \
  "$PREFIX/.venv/bin/python" -m seo_operator.cli daily-run --json > "$LOG_DIR/first-dry-run.json"

echo "== 8. Read-only сверка =="
SEO_STATE_DIR="$STATE_DIR" PYTHONPATH="$PREFIX/src" \
  "$PREFIX/.venv/bin/python" -m seo_operator.cli portfolio validate --json
SEO_STATE_DIR="$STATE_DIR" PYTHONPATH="$PREFIX/src" \
  "$PREFIX/.venv/bin/python" -m seo_operator.cli permissions test --json

echo "== 9. Units (устанавливаются, НЕ включаются) =="
install -m 0644 "$PREFIX"/deploy/systemd/*.service /etc/systemd/system/
install -m 0644 "$PREFIX"/deploy/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload

chown -R "$RUN_USER:$RUN_USER" "$PREFIX" "$STATE_DIR" "$LOG_DIR"

cat <<NEXT

Установка завершена. Расписание НЕ включено намеренно.

Прочитайте $LOG_DIR/first-dry-run.json, затем включите вручную:

  systemctl enable --now seo-collect.timer
  systemctl enable --now seo-daily-report.timer
  systemctl enable --now seo-restore-drill.timer

Индексация, DNS, покупка доменов и публикация новых production-сайтов
включаются отдельными решениями владельца, а не этим скриптом.
NEXT
