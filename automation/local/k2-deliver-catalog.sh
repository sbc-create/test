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

# `--from-staging <каталог>` берёт уже собранный издателем комплект вместо
# нового прогона: когда восемь витрин собраны одним прогоном, повторять его по
# разу на витрину — это 20 минут и лишний износ диска.
from_staging=""
sites=""
while [ $# -gt 0 ]; do
  case "$1" in
    --from-staging) from_staging="${2:?нужен каталог}"; shift ;;
    *) sites="$sites $1" ;;
  esac
  shift
done
sites="$(printf '%s' "$sites" | sed 's/^ *//')"
[ -n "$sites" ] || { echo "нужен хотя бы один site_id" >&2; exit 2; }
cd "$repo_root" || exit 1

if [ -z "$from_staging" ] && [ ! -f "$publisher" ]; then
  echo "==> собираю совместимого издателя"
  python3 automation/local/make-k2-publisher.py || exit 1
fi

list="$(printf '%s' "$sites" | tr ' ' ',')"
rm -rf "$work"; mkdir -p "$work"

if [ -n "$from_staging" ]; then
  echo "==> беру готовый комплект из $from_staging"
  for site in $sites; do
    for kind in catalog details; do
      src="$from_staging/$site-$kind.json"
      [ -f "$src" ] || { echo "[x] нет $src"; exit 1; }
      cp "$src" "$work/$site-$kind.json"
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

for site in $sites; do
  box="$work/$site"
  mkdir -p "$box"
  for kind in catalog details; do
    f="$work/$site-$kind.json"
    [ -f "$f" ] || { echo "[x] издатель не дал $f"; exit 1; }
    mv "$f" "$box/"
  done
  ( cd "$box" && sha256sum ./*.json > SHA256SUMS )
  echo "==> $site: комплект $(du -sm "$box" | cut -f1) МиБ, файлов $(ls -1 "$box" | wc -l)"

  # Вывод ansible СОХРАНЯЕТСЯ, а не выбрасывается. Измерено 22.10: прежняя
  # редакция писала `>/dev/null`, и четыре суточных отказа подряд (19–22.10)
  # не оставили ни одной строки о причине — в журнале юнита есть только «==>
  # lords-10: комплект 111 МиБ» и «[x] доставка не удалась». Шаг, на котором
  # стоит вся цепочка, был единственным, чей вывод уничтожался.
  copy_log="$work/$site-copy.log"
  if ! ansible -i "$inventory" "$host_ref" -m copy \
      -a "src=$box/ dest=/home/k2deploy/stage/incoming/$site/ mode=0644 directory_mode=0755" \
      > "$copy_log" 2>&1; then
    echo "[x] доставка не удалась; причина из ansible:"
    tail -25 "$copy_log" | sed 's/^/   /'
    # Журнал НЕ удаляется вместе с ящиком: он и есть то, зачем сюда придут.
    cp "$copy_log" "$work/../last-copy-failure.log" 2>/dev/null
    echo "   полный вывод: $copy_log (копия: $work/../last-copy-failure.log)"
    exit 1
  fi

  out="$(ansible -i "$inventory" "$host_ref" -m raw \
         -a "cd /home/k2deploy/stage/incoming/$site; sha256sum -c SHA256SUMS --quiet; echo rc=\$?" 2>&1)"
  printf '%s\n' "$out" | grep -E "rc=|FAILED" | sed 's/^/   /'
  printf '%s\n' "$out" | grep -q "rc=0" || { echo "[x] суммы на узле не сошлись"; exit 1; }

  rm -rf "$box"
  echo "   $site: доставлено и сверено; установку сделает таймер узла"
done

rm -rf "$work"
df -Pm / | awk 'NR==2{print "свободно на управляющем узле: " $4 " МиБ"}'
