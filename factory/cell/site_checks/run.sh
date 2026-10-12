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
# Проверка может исполниться и НЕ ИЗМЕРИТЬ ничего: стенд не поднялся по правам,
# чужой каталог данных не найден, сеть недоступна. Такая проверка выходит с
# нулём и в выводе выглядит как PASS. Цена измерена 12.10: `config/player.json`
# у двух ячеек AnimeGo принадлежит root (0600), стенд `data_chain` не
# поднимался, проверка уходила в пропуск — и регрессия таблицы характеристик
# прошла run.sh и вышла на живой сайт. Пропуски считаются отдельно.
skipped=0
say() { printf '%-30s %s\n' "$1" "$2"; }
# Вывод упавшей проверки печатается. Молчащий FAIL приходится воспроизводить
# вручную, а воспроизводится он не всегда: проверка падала на раннере и
# проходила в чистом клоне на той же машине — искать было нечего.
check() {
  local name="$1"; shift
  local out
  ran=$((ran + 1))
  if out="$("$@" 2>&1)"; then
    # Пропуск распознаётся по словам самой проверки. Прогон им не валится:
    # предел окружения бывает законным, а превращать его в отказ — решение о
    # выпусках, и принимать его не этому сценарию. Но тихим он быть перестаёт.
    if printf '%s' "$out" | grep -qE 'ПРОПУЩЕНО|ограничение окружения|НЕ ИЗМЕРЕНО|не измерено'; then
      say "$name" "ПРОПУЩЕНО"
      printf '%s\n' "$out" | grep -E 'ПРОПУЩЕНО|ограничение окружения|НЕ ИЗМЕРЕНО|не измерено' | head -2 | sed 's/^/    | /'
      skipped=$((skipped + 1))
    else
      say "$name" "PASS"
    fi
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

if [ "$skipped" -gt 0 ]; then
  say "checks-measured" "ПРОПУЩЕНО $skipped из $ran"
  printf '    | эти проверки исполнились, но измерить не смогли — итог прогона\n'
  printf '    | о них не говорит ничего. Причина у каждой напечатана выше.\n'
else
  say "checks-measured" "PASS"
fi

exit "$fail"
