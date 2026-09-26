#!/usr/bin/env bash
# Проверки проекта сайта. Падение любой — причина не выпускать релиз.
# Имена переменных только ASCII: bash считает именем лишь [A-Za-z_][A-Za-z0-9_]*,
# и строка вида `СУХОЙ=0` для него не присваивание, а вызов команды. `bash -n`
# такую строку пропускает.
set -uo pipefail
cd "$(dirname "$0")/.."

fail=0
say() { printf '%-30s %s\n' "$1" "$2"; }
# Вывод упавшей проверки печатается. Молчащий FAIL приходится воспроизводить
# вручную, а воспроизводится он не всегда: проверка падала на раннере и
# проходила в чистом клоне на той же машине — искать было нечего.
check() {
  local name="$1"; shift
  local out
  if out="$("$@" 2>&1)"; then
    say "$name" "PASS"
  else
    say "$name" "FAIL"
    printf '%s\n' "$out" | sed 's/^/    | /'
    fail=1
  fi
}

check "site-config-json"   python3 -c "import json;json.load(open('config/site.json'))"
check "pins-json"          python3 -c "import json;json.load(open('pins.lock.json'))"
check "entrypoint-present" python3 checks/entrypoint_present.py
check "runtime-compiles"   python3 checks/compiles.py
check "pins-match-sources" python3 checks/verify_pins.py
check "no-secrets-in-git"  python3 checks/no_secrets.py
check "shell-ascii-names"  python3 checks/ascii_shell_identifiers.py
check "launcher-refuses"   python3 checks/fails_closed.py
check "shell-syntax"       bash -c 'bash -n deploy/activate.sh && bash -n deploy/rollback.sh'
check "manifest-stamp"     python3 checks/manifest_stamp.py
check "artifact-contents"  python3 checks/artifact_contents.py
# Сценарии именно выполняются: `bash -n` пропустил ошибку, валившую скрипт на
# третьей строке, и обнаружилась она только на боевой активации.
check "activate-scenarios" python3 checks/activate_scenarios.py

exit "$fail"
