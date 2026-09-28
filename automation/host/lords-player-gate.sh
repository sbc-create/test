#!/usr/bin/env bash
# PLAYER_FREEZE_GATE на живых витринах: плеер обязан быть там, где есть поток.
#
# Первая редакция брала случайные карточки и считала отсутствие плеера отказом.
# Это неверный критерий: у 672 записей из 53 116 (1,3 %) потока нет вовсе, и
# честная страница говорит «недоступно» вместо пустого плеера. Проверка дала
# 29/30 и указала на тайтл «Кошмарган», у которого `playback: null` — то есть
# нашла не поломку сайта, а собственную неточность.
#
# Проверяется обещание «есть поток — есть плеер». Обратное — «нет потока, нет
# плеера» — тоже правильное поведение, и отказом не считается.
set -uo pipefail

REPO="${LORDS_REPO:-/home/claude/work-test}"
CACHE="${LORDS_CACHE_DIR:-/srv/site-factory/repo/var/lords/lords/catalog-cache}"
PER_SITE="${LORDS_GATE_PER_SITE:-10}"

hosts=(lordfilm47.space lordserial33.biz 1lordserials1.online)
sites=(lords-01 lords-02 lords-03)

total_ok=0
total_bad=0
for i in 0 1 2; do
  mapfile -t slugs < <(sudo -n "$REPO/.venv/bin/python" -c "
import json, sys
sys.path.insert(0, '$REPO')
from factory.lords import live_catalog
items = json.load(open('$CACHE/${sites[$i]}.json'))['items']
catalog = live_catalog.catalog_from_live(items)
print('\\n'.join(t.slug for t in catalog.titles if t.playback), end='')
" 2>/dev/null | shuf -n "$PER_SITE")

  if [ "${#slugs[@]}" -eq 0 ]; then
    echo "  ${sites[$i]}: не удалось отобрать тайтлы с потоком — проверка НЕ выполнена"
    exit 2
  fi

  hit=0
  miss=0
  for s in "${slugs[@]}"; do
    if curl -sS --max-time 25 "https://${hosts[$i]}/title/$s/" | grep -q "<video-player"; then
      hit=$((hit + 1))
    else
      miss=$((miss + 1))
      echo "      БЕЗ ПЛЕЕРА при наличии потока: ${hosts[$i]}/title/$s/"
    fi
  done
  total_ok=$((total_ok + hit))
  total_bad=$((total_bad + miss))
  printf '  %-9s плеер найден %s из %s\n' "${sites[$i]}" "$hit" "${#slugs[@]}"
done

echo "  ИТОГО: ${total_ok}/$((total_ok + total_bad))"
[ "$total_bad" -eq 0 ]
