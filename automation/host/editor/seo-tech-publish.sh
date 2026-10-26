#!/usr/bin/env bash
# Выпуск проверенных веток технического SEO штатным путём (seo_operator/tech_publish.py).
# Модель не участвует. Подготовка (seo-tech-run) и выпуск — разные службы: у подготовки
# нет учётных данных git, у выпуска нет модели.
#
# Коды: 0 — проход выполнен (итоги — в var/seo-tech/publish.jsonl); 70 — предполётная
# проверка не прошла; 73 — состояние или файл блокировки недоступны; 75 — идёт другой выпуск.
set -uo pipefail

# Корни (MOD-198): код — SEO_CODE_ROOT (каталог выпуска; задание модели читается
# оттуда же — после cd), состояние и живые реестры — рабочая копия, пока юнит не
# задал иное. Python получает те же корни через окружение (seo_operator.paths):
# без этого в выпуске код и состояние разошлись бы по разным корням.
WORKTREE=/home/claude/wt-portable-site-cell-01
REPO="${SEO_CODE_ROOT:-$WORKTREE}"
export SEO_STATE_ROOT="${SEO_STATE_ROOT:-$WORKTREE}"
export SEO_REGISTRY_ROOT="${SEO_REGISTRY_ROOT:-$WORKTREE}"
STATE="${SEO_TECH_STATE:-${SEO_STATE_ROOT:-$REPO}/var/seo-tech}"  # корень состояния — как у seo_operator.paths (MOD-198)
export SEO_TECH_STATE="$STATE"

cd "$REPO" || { echo "seo-tech-publish: нет каталога $REPO" >&2; exit 70; }
if ! mkdir -p "$STATE" 2>/dev/null || ! ( : >>"$STATE/.writable" ) 2>/dev/null; then
  echo "seo-tech-publish: каталог состояния $STATE недоступен для записи" >&2
  exit 73
fi
if ! exec 8>>"$STATE/publish.lock"; then
  echo "seo-tech-publish: не открыть файл блокировки $STATE/publish.lock" >&2
  exit 73
fi
if ! flock -n 8; then
  echo "seo-tech-publish: идёт другой выпуск" >&2
  exit 75
fi

fail() { echo "seo-tech-publish: предполётная проверка: $*" >&2; exit 70; }
command -v git >/dev/null || fail "нет git"
command -v gh >/dev/null || fail "нет gh"
gh auth status >/dev/null 2>&1 || fail "gh не авторизован — выпуск невозможен"
python3 -c "import seo_operator.tech_publish" 2>/dev/null || fail "не импортируется seo_operator.tech_publish"

# Есть ли что выпускать — без сети и без заявок.
N="$(python3 -c "from seo_operator import tech_publish as p; print(len(p.кандидаты(p.tech_run.STATE)))" 2>/dev/null || echo err)"
case "$N" in
  0) exit 0 ;;
  err) fail "не прочитан список кандидатов" ;;
esac

timeout -k 60 7200 python3 -m seo_operator.cli seo-tech-publish --limit 3 >>"$STATE/publish.log" 2>&1
exit 0
