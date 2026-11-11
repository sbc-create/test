#!/usr/bin/env bash
# Доставка свежего каталога витрины на узел K2 — с управляющего узла.
#
# Цепочка целиком: совместимый издатель собирает снимок в изолированный
# каталог → комплект подписывается суммами → уезжает во ВХОДЯЩИЙ каталог
# k2deploy → сверяется на узле → корневой таймер K2 ставит его в данные
# витрины с её правами. Ни один шаг не требует ослаблять права каталога
# данных и ни один не делается руками.
#
# Почему издатель именно «совместимый»: в этой ветви нет модулей factory.lords,
# а живой издатель не знает новых витрин. Копия собирается из ЖИВОГО файла
# вставкой восьми записей (`automation/local/make-k2-publisher.py`), сам живой
# издатель не меняется.
#
# Имена переменных только ASCII.
#
# Запуск:  k2-deliver-catalog.sh <site_id> [ещё site_id ...]
set -uo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
host_ref="k2-zomro-01"
inventory="$repo_root/var/ansible/hosts.yml"
snapshot="${K2_SNAPSHOT:-/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json}"
work="$repo_root/var/k2-data/deliver"
publisher="$repo_root/var/k2-data/publisher/automation/host/nova-catalog-publish.py"

# Исполняемый ansible ищется ЯВНО, а не через PATH оболочки.
#
# Измерено 24.10: суточный запуск из таймера пользователя падал на шаге
# копирования с «k2-deliver-catalog.sh: line 115: ansible: command not found»,
# хотя ansible установлен — /home/claude/.local/bin/ansible. systemd даёт юниту
# минимальный PATH (/usr/local/bin:/usr/bin:/bin), и этого каталога в нём нет.
# В интерактивной оболочке тот же скрипт работает: профиль добавляет PATH сам.
# Отсюда и четыре суточных отказа подряд 19–22.10 — причина была та же, но её
# вывод уничтожался `>/dev/null`.
#
# Отсутствие ansible теперь называется ОТДЕЛЬНОЙ ошибкой до первой витрины:
# внутри шага оно выглядело как «доставка не удалась», то есть как отказ узла.
# Порядок поиска важен. PATH спрашивается ПЕРВЫМ: если ansible в нём есть, то
# именно он и имелся в виду — так работает любая оболочка, и на этом стоят
# проверки доставки, подкладывающие свой ansible в PATH. Известные каталоги —
# запасной путь ровно для случая юнита, которому systemd урезал PATH.
ansible_bin="${ANSIBLE_BIN:-}"
if [ -z "$ansible_bin" ]; then ansible_bin="$(type -P ansible || true)"; fi
if [ -z "$ansible_bin" ] && [ -x "$HOME/.local/bin/ansible" ]; then ansible_bin="$HOME/.local/bin/ansible"; fi
if [ -z "$ansible_bin" ] && [ -x /usr/local/bin/ansible ]; then ansible_bin=/usr/local/bin/ansible; fi
if [ -z "$ansible_bin" ] && [ -x /usr/bin/ansible ]; then ansible_bin=/usr/bin/ansible; fi
if [ -z "$ansible_bin" ]; then
  echo "[x] ansible не найден: ни ANSIBLE_BIN, ни ~/.local/bin, ни /usr/local/bin," >&2
  echo "    ни /usr/bin, ни PATH=$PATH. Доставка не начата." >&2
  exit 2
fi
# Каталог ansible — в PATH: сам ansible зовёт соседние ansible-* утилиты.
PATH="$(dirname -- "$ansible_bin"):$PATH"
export PATH

# `--from-staging <каталог>` берёт уже собранный издателем комплект вместо
# нового прогона: когда восемь витрин собраны одним прогоном, повторять его по
# разу на витрину — это 20 минут и лишний износ диска.
#
# `--node <ref>` берёт состав витрин ИЗ РЕЕСТРА (`deploy_target.ref`) вместо
# перечисления в команде. Так сделано 2026-10-25: суточные юниты доставки
# перечисляли восемь витрин строкой, и пять новых ячеек того же узла не
# получали бы обновлений каталога вовсе — отсутствие строки в юните выглядит
# точно так же, как «доставка настроена». Выведенные из работы ячейки
# исключаются по признаку паспорта, а не по отсутствию имени.
from_staging=""
sites=""
node=""
while [ $# -gt 0 ]; do
  case "$1" in
    --from-staging) from_staging="${2:?нужен каталог}"; shift ;;
    --node) node="${2:?нужен ref узла}"; shift ;;
    *) sites="$sites $1" ;;
  esac
  shift
done
sites="$(printf '%s' "$sites" | sed 's/^ *//')"
if [ -n "$node" ]; then
  from_registry="$(python3 automation/local/node-cell-list.py "$node")" \
    || { echo "состав узла $node не прочитан из реестра" >&2; exit 2; }
  [ -n "$from_registry" ] || { echo "в реестре нет витрин узла $node" >&2; exit 2; }
  sites="$(printf '%s %s' "$sites" "$from_registry" | sed 's/^ *//')"
  echo "==> состав узла $node из реестра: $from_registry"
fi
[ -n "$sites" ] || { echo "нужен хотя бы один site_id или --node <ref>" >&2; exit 2; }
cd "$repo_root" || exit 1

if [ -z "$from_staging" ] && [ ! -f "$publisher" ]; then
  echo "==> собираю совместимого издателя"
  python3 automation/local/make-k2-publisher.py || exit 1
fi

list="$(printf '%s' "$sites" | tr ' ' ',')"
rm -rf "$work"; mkdir -p "$work"

if [ -n "$from_staging" ]; then
  echo "==> беру готовый комплект из $from_staging"
  # Недостающий файл у ОДНОЙ витрины не отменяет остальных: прежняя редакция
  # выходила кодом 1 на первом же `[x] нет …`, то есть одна неполная папка
  # лишала каталога все восемь. Витрины независимы, и неполная просто не
  # доставляется — её имя попадёт в итог.
  for site in $sites; do
    for kind in catalog details; do
      src="$from_staging/$site-$kind.json"
      if [ -f "$src" ]; then
        cp "$src" "$work/$site-$kind.json"
      else
        echo "[x] нет $src"
      fi
    done
  done
else
  echo "==> издатель собирает каталог для: $list"
  python3 automation/local/run-k2-publisher.py -- \
      --sites "$list" --snapshot "$snapshot" \
      --staging-out "$work" \
      --report-dir "$repo_root/var/k2-data/publish-reports" \
      > "$work/publish.log" 2>&1
  rc=$?
  tail -3 "$work/publish.log" | sed 's/^/   /'
  [ "$rc" = 0 ] || { echo "издатель завершился кодом $rc — доставка не начиналась"; exit 1; }
fi

# Отказ на ОДНОЙ витрине не лишает каталога остальные, и это исправление
# измеренного вреда. Прежняя редакция выходила кодом 1 на первой же неудаче:
# 22.10 отказ пришёл на `lords-10`, и остальные СЕМЬ витрин не обрабатывались
# вовсе, хотя комплекты для них были собраны и лежали рядом. Витрины
# независимы — у каждой свой входящий каталог на узле и свои суммы, — поэтому
# продолжать безопасно. Итоговый код по-прежнему ненулевой, если отказала
# хотя бы одна: «частично доставлено» успехом не считается.
failed=""
delivered=""

for site in $sites; do
  box="$work/$site"
  mkdir -p "$box"
  missing=""
  for kind in catalog details; do
    f="$work/$site-$kind.json"
    if [ -f "$f" ]; then
      mv "$f" "$box/"
    else
      echo "[x] $site: издатель не дал $f"
      missing=1
    fi
  done
  if [ -n "$missing" ]; then
    failed="$failed $site"
    continue
  fi
  if [ "$site" = lords-19 ]; then
    if ! python3 automation/local/k2-catalog-provenance.py --box "$box" --snapshot "$snapshot" --reports "${K2_PROVENANCE_REPORT_DIR:-$repo_root/var/k2-data/publish-reports}"; then
      echo "[x] lords-19: provenance verification failed; not delivered"
      failed="$failed $site"
      continue
    fi
  fi
  ( cd "$box" && sha256sum ./*.json > SHA256SUMS )
  echo "==> $site: комплект $(du -sm "$box" | cut -f1) МиБ, файлов $(ls -1 "$box" | wc -l)"

  # Вывод ansible СОХРАНЯЕТСЯ, а не выбрасывается. Измерено 22.10: прежняя
  # редакция писала `>/dev/null`, и четыре суточных отказа подряд (19–22.10)
  # не оставили ни одной строки о причине — в журнале юнита есть только «==>
  # lords-10: комплект 111 МиБ» и «[x] доставка не удалась». Шаг, на котором
  # стоит вся цепочка, был единственным, чей вывод уничтожался.
  copy_log="$work/$site-copy.log"
  if ! "$ansible_bin" -i "$inventory" "$host_ref" -m copy \
      -a "src=$box/ dest=/home/k2deploy/stage/incoming/$site/ mode=0644 directory_mode=0755" \
      > "$copy_log" 2>&1; then
    echo "[x] доставка не удалась; причина из ansible:"
    tail -25 "$copy_log" | sed 's/^/   /'
    # Журнал НЕ удаляется вместе с ящиком: он и есть то, зачем сюда придут.
    cp "$copy_log" "$work/../last-copy-failure.log" 2>/dev/null
    echo "   полный вывод: $copy_log (копия: $work/../last-copy-failure.log)"
    failed="$failed $site"
    continue
  fi

  out="$("$ansible_bin" -i "$inventory" "$host_ref" -m raw \
         -a "cd /home/k2deploy/stage/incoming/$site; sha256sum -c SHA256SUMS --quiet; echo rc=\$?" 2>&1)"
  printf '%s\n' "$out" | grep -E "rc=|FAILED" | sed 's/^/   /'
  if ! printf '%s\n' "$out" | grep -q "rc=0"; then
    echo "[x] $site: суммы на узле не сошлись — ящик НЕ убран, он нужен разбору"
    failed="$failed $site"
    continue
  fi

  rm -rf "$box"
  delivered="$delivered $site"
  echo "   $site: доставлено и сверено; установку сделает таймер узла"
done

# Итог по витринам печатается ВСЕГДА: «доставка не удалась» без имён витрин
# четыре суток не давала понять, отказала одна или все восемь.
echo "==> итог: доставлено [${delivered# }], отказ [${failed# }]"

if [ -n "$failed" ]; then
  echo "рабочий каталог НЕ убран: в нём ящики и журналы отказавших витрин —"
  echo "   $work"
  df -Pm / | awk 'NR==2{print "свободно на управляющем узле: " $4 " МиБ"}'
  exit 1
fi

rm -rf "$work"
df -Pm / | awk 'NR==2{print "свободно на управляющем узле: " $4 " МиБ"}'
