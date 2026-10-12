#!/usr/bin/env bash
# Проверки проекта сайта. Падение любой — причина не выпускать релиз.
# Имена переменных только ASCII: bash считает именем лишь [A-Za-z_][A-Za-z0-9_]*,
# и строка вида `СУХОЙ=0` для него не присваивание, а вызов команды. `bash -n`
# такую строку пропускает.
set -uo pipefail
cd "$(dirname "$0")/.."

fail=0
# Сколько проверок ОБЪЯВЛЕНО в этом файле и сколько их реально исполнилось.
# Число не вписывается руками: оно считается из самого файла, поэтому новая
# строка `check` поднимает ожидание сама, а устаревшее число не может соврать.
#
# Зачем это вообще. Строка проверки, скопированная между семействами витрин,
# молча не исполняется: у части ячеек обёртка называется `step`, а не `check`,
# и bash на незнакомую команду отвечает «command not found» с кодом 127, НЕ
# меняя код прогона. Так проверка видимых крошек молчала на трёх витринах
# AnimeGo, и отсутствие крошек выглядело как исправность. Счёт исполненного
# ловит это независимо от причины: опечатки, чужого имени обёртки, раннего
# выхода.
# Считаются ОБА имени обёртки. Если считать только `check`, то переименование
# строки в `step` снижало бы и ожидание, и исполненное — сторож промолчал бы
# ровно о той подмене, ради которой написан.
expected="$(grep -cE '^(check|step) ' "$0")"
ran=0
say() { printf '%-30s %s\n' "$1" "$2"; }
# Вывод упавшей проверки печатается. Молчащий FAIL приходится воспроизводить
# вручную, а воспроизводится он не всегда: проверка падала на раннере и
# проходила в чистом клоне на той же машине — искать было нечего.
check() {
  local name="$1"; shift
  local out
  ran=$((ran + 1))
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
# Публичная почта обратной связи: есть, та самая и проведена в рантайм.
# Отдельной проверкой, потому что цепочка значение -> SITE_CONTACT_EMAIL ->
# строка подвала рвалась дважды, и оба раза при зелёных проверках: один раз
# значением, один раз проводкой (run.py переменную не выставлял, и подвал вышел
# бы пустым на каждой странице).
check "contact-email"      python3 checks/contact_email.py

if [ "$ran" -ne "$expected" ]; then
  say "checks-all-ran" "FAIL"
  printf '    | объявлено проверок: %s, исполнилось: %s\n' "$expected" "$ran"
  printf '    | проверка, которая не исполнилась, выглядит как пройденная.\n'
  printf '    | частая причина: обёртка в этой ячейке называется иначе\n'
  printf '    | (`step` вместо `check`) — bash отвечает кодом 127 и прогон\n'
  printf '    | этого не замечает.\n'
  fail=1
else
  say "checks-all-ran" "PASS"
fi

exit "$fail"
