#!/usr/bin/env bash
# REQ-QA-LEVELS: полный прогон всех уровней проверок с чистого состояния.
#
# Каждый шаг печатает фактическую команду и её exit code; итог собирается в
# artifacts/qa/run-all.json. Шаг, который нельзя выполнить в этой среде, помечается
# SKIPPED с причиной — «пройденным» он от этого не становится.
set -uo pipefail
cd "$(dirname "$0")/.."

# Интеграционные тесты и пилот меняют общую одноразовую цель, поэтому полный прогон
# сериализуется: два одновременных прогона перетирали бы артефакты друг друга.
mkdir -p var/locks
if [ "${FACTORY_RUN_ALL_LOCKED:-0}" != "1" ]; then
  export FACTORY_RUN_ALL_LOCKED=1
  exec flock -w "${FACTORY_RUN_ALL_WAIT:-1800}" var/locks/run-all.lock "$0" "$@"
fi

REPORT="artifacts/qa/run-all.json"
mkdir -p artifacts/qa
ROWS="$(mktemp)"
export FACTORY_ROWS="$ROWS" FACTORY_REPORT="$REPORT"
trap 'rm -f "$ROWS"' EXIT
: "${FACTORY_SKIP_BROWSER:=0}"

record() {
  FACTORY_ROW_CHECK="$1" FACTORY_ROW_CMD="$2" FACTORY_ROW_CODE="$3" \
  FACTORY_ROW_STATUS="$4" FACTORY_ROW_NOTE="$5" \
  python3 -c 'import json,os;print(json.dumps({"check":os.environ["FACTORY_ROW_CHECK"],"command":os.environ["FACTORY_ROW_CMD"],"exit_code":os.environ["FACTORY_ROW_CODE"],"status":os.environ["FACTORY_ROW_STATUS"],"note":os.environ["FACTORY_ROW_NOTE"]},ensure_ascii=False))' >> "$ROWS"
}

run() {
  local name="$1"; shift
  local cmd="$*"
  echo ""
  echo "-- $name"
  echo "   \$ $cmd"
  local start=$SECONDS
  eval "$cmd"
  local code=$?
  local took=$((SECONDS - start))
  local status="FAIL"; [ $code -eq 0 ] && status="PASS"
  record "$name" "$cmd" "$code" "$status" "${took}s"
  echo "   -> exit=$code (${took}s)"
}

skip() {
  echo ""
  echo "-- $1"
  echo "   SKIPPED: $2"
  record "$1" "-" "-" "SKIPPED" "$2"
}

echo "=== DLE Site Factory: полный прогон ==="
echo "commit: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

run "knowledge-freeze"   "python3 -m factory knowledge verify"
run "claude-config"      "python3 -m factory selfcheck"
run "static-python"      "python3 -m compileall -q factory tools .claude/hooks tests > /dev/null"
run "static-php"         "find automation themes -name '*.php' -print0 | xargs -0 -r -n1 php -l > /dev/null"
run "static-js"          "for f in tools/*.js themes/*/assets/*.js tests/e2e/*.js tests/e2e-multisite/*.js playwright.config.js playwright.multisite.config.js; do node --check \"\$f\" || exit 1; done"
run "static-yaml"        "python3 tests/tools/check_yaml.py"
run "unit-tests"         "python3 -m pytest tests/unit tests/test_traceability.py -q -m 'not slow'"
run "validate-pilot"     "python3 -m factory validate --site pilot-local > /dev/null"
run "plan-no-mutations"  "python3 -m factory plan --site pilot-local > /dev/null"
run "build-pilot"        "python3 -m factory build --site pilot-local --force > /dev/null"
run "integration-fast"   "python3 -m pytest tests/integration -q -m 'not slow'"
run "integration-slow"   "python3 -m pytest tests/integration -q -m slow"
run "seo-lint"           "python3 -m factory seo-lint --site pilot-local > /dev/null"

# Профиль путей DLE намеренно не заполнен: официальная документация недоступна.
# Ожидаемое поведение — BLOCKED_INPUT (exit 2), и это фиксируется как PASS-ожидание.
echo ""
echo "-- blueprint-profile-gate"
python3 -m factory blueprint check > /dev/null 2>&1
BP=$?
if [ $BP -eq 2 ]; then
  echo "   -> exit=2 (ожидаемый BLOCKED_INPUT: профиль DLE не заполнен)"
  record "blueprint-profile-gate" "python3 -m factory blueprint check" "2" "PASS" "ожидаемый BLOCKED_INPUT"
else
  echo "   -> exit=$BP (ожидался 2)"
  record "blueprint-profile-gate" "python3 -m factory blueprint check" "$BP" "FAIL" "ожидался BLOCKED_INPUT"
fi

if [ "$FACTORY_SKIP_BROWSER" = "1" ]; then
  skip "seo-crawl"     "FACTORY_SKIP_BROWSER=1"
  skip "browser-audit" "FACTORY_SKIP_BROWSER=1"
  skip "e2e-playwright" "FACTORY_SKIP_BROWSER=1"
else
  # Проверки по HTTP требуют поднятого стенда: прогон обязан быть самодостаточным,
  # а не полагаться на сервер, случайно оставшийся от прошлого запуска.
  run "deploy-pilot"     "python3 -m factory deploy --site pilot-local > /dev/null"
  FACTORY_BASE_URL="$(python3 tests/tools/base_url.py)"
  export FACTORY_BASE_URL
  FACTORY_STAGING_AUTH="$(cat var/targets/local-disposable/pilot-local/staging-auth 2>/dev/null || true)"
  export FACTORY_STAGING_AUTH
  run "seo-crawl"      "python3 -m factory seo-crawl --site pilot-local > /dev/null"
  # Браузерная проверка уже выполнена внутри деплоя: здесь доказывается, что её
  # артефакт существует и не содержит критических находок.
  run "browser-audit"  "python3 tests/tools/check_browser_audit.py"
  if [ -d node_modules/@playwright/test ]; then
    PW_REPORT="artifacts/qa/pilot-local/playwright-report.json"
    rm -f "$PW_REPORT"
    run "e2e-playwright" "npx playwright test && test -s \"$PW_REPORT\""
    if [ ! -s "$PW_REPORT" ]; then
      echo "   ВНИМАНИЕ: отчёт $PW_REPORT не создан — шаг не может считаться доказанным"
    fi
  else
    skip "e2e-playwright" "@playwright/test не установлен"
  fi
fi

if [ "${FACTORY_ALL_BROWSERS:-0}" = "1" ]; then
  run "cross-browser"  "npx playwright test --project=firefox --project=webkit --reporter=list"
else
  skip "cross-browser" "в образе только Chromium: firefox и webkit в /opt/pw-browsers отсутствуют"
fi

if command -v ansible-playbook > /dev/null 2>&1; then
  run "ansible-syntax" "ansible-playbook --syntax-check automation/ansible/deploy-site.yml"
else
  skip "ansible-syntax" "ansible-playbook не установлен на управляющем хосте"
fi

if command -v nginx > /dev/null 2>&1; then
  run "nginx-config-test" "nginx -t"
else
  skip "nginx-config-test" "nginx не установлен на управляющем хосте"
fi

# ---------------------------------------------------------------------------
# Blueprint payload-next-multisite: три сайта на общей CMS.
# Каждый шаг — фактический запуск. Недоступный компонент даёт skip с причиной,
# а не молчаливый пропуск и не PASS.
# ---------------------------------------------------------------------------
TSX="blueprints/payload-next-multisite/app/node_modules/.bin/tsx"
APP_TESTS="blueprints/payload-next-multisite/app/tests"

if [ ! -x "$TSX" ]; then
  skip "payload-blueprint" "зависимости приложения не установлены (npm ci в blueprints/payload-next-multisite/app)"
elif ! pg_isready -q 2>/dev/null && ! python3 -c "from factory import database; raise SystemExit(0 if database.start_cluster() else 1)"; then
  skip "payload-blueprint" "кластер PostgreSQL недоступен"
else
  # Подоболочка обязательна: `run` выполняет команду в текущем shell, и `cd`
  # без скобок утащил бы за собой все последующие шаги.
  run "payload-secret-scan" "python3 tests/tools/secret_scan.py"
  run "payload-typecheck"   "(cd blueprints/payload-next-multisite/app && npx tsc --noEmit -p tsconfig.json)"
  run "payload-seo-matrix"  "$TSX $APP_TESTS/seo-matrix.ts"
  run "payload-player"      "$TSX $APP_TESTS/player-contract.ts"
  run "payload-comments"    "$TSX $APP_TESTS/comments-policy.ts"
  run "payload-isolation"   "python3 tests/tools/with_app_env.py --scope anime -- $TSX $APP_TESTS/tenant-isolation.ts"
  run "payload-content-api" "python3 tests/tools/with_app_env.py --scope anime -- $TSX $APP_TESTS/content-api.ts"
  run "payload-mutation"    "python3 tests/tools/mutation_isolation.py"
  run "payload-admin-smoke" "python3 tests/tools/admin_smoke.py"
  run "payload-frontend"    "python3 tests/tools/frontend_http.py"
  run "payload-cross-site"  "python3 tests/tools/cross_site_uniqueness.py"
  run "payload-restore"     "python3 tests/tools/restore_proof.py"

  if [ -x /opt/pw-browsers/chromium-1194/chrome-linux/chrome ]; then
    run "payload-browser"   "python3 tests/tools/browser_multisite.py"
  else
    skip "payload-browser" "Chromium не найден в /opt/pw-browsers"
  fi

  REFERENCE_STATUS=$(python3 -m factory reference-audit --ref amd-online --json 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo unknown)
  if [ "$REFERENCE_STATUS" = "measured" ]; then
    run "reference-audit" "python3 -m factory reference-audit --ref amd-online > /dev/null"
  else
    skip "reference-audit" "измерение amd.online недоступно из этой среды (статус: $REFERENCE_STATUS)"
  fi
fi

# Доказательства последнего прогона фиксируются в artifacts/evidence/.
python3 tests/tools/collect_evidence.py > /dev/null || true

# Код возврата прогона — это код сводки: она возвращает ненулевой при провалах.
# Раньше он терялся, и прогон с десятью провалами завершался нулём.
python3 tests/tools/summarize_run.py
exit $?
