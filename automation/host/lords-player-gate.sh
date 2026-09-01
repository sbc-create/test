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
total_absent=0
total_broken=0
total_flaky=0
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
  absent=0
  broken=0
  flaky=0
  for s in "${slugs[@]}"; do
    # Ответ и тело берутся одним запросом: два запроса подряд к одному адресу
    # могут застать разные релизы, и тогда код относится к одной странице, а
    # разметка — к другой.
    body=$(curl -sS --max-time 25 -w '\n%{http_code}' "https://${hosts[$i]}/title/$s/" 2>/dev/null)
    curl_rc=$?
    code=${body##*$'\n'}
    if [ "$curl_rc" -ne 0 ]; then
      # Обрыв на середине тела даёт код 200 при усечённом HTML: заголовки уже
      # пришли, а разметка — нет, и страница выглядит как «без плеера».
      # Проверено: страница, однажды объявленная отказом, отдала плеер 12 раз из
      # 12 при повторе. Отказ связи — это невыполненная проверка, а не отказ
      # витрины, и складывать их в один счётчик нельзя.
      broken=$((broken + 1))
      echo "      ПРОВЕРКА НЕ ВЫПОЛНЕНА (curl код $curl_rc): ${hosts[$i]}/title/$s/"
    elif [ "$code" != "200" ]; then
      # Страницы нет в опубликованном релизе. Это отставание релиза от каталога,
      # а не отказ плеера, и смешивать их нельзя: гейт берёт произведения из
      # НЫНЕШНЕГО каталога и ищет их в УЖЕ опубликованном релизе, который всегда
      # старше. Раньше такой случай печатался как «БЕЗ ПЛЕЕРА при наличии
      # потока» и выглядел поломкой витрины.
      absent=$((absent + 1))
      echo "      НЕТ СТРАНИЦЫ (HTTP $code, релиз старше каталога): ${hosts[$i]}/title/$s/"
    elif printf '%s' "$body" | grep -q "<video-player"; then
      hit=$((hit + 1))
    else
      # Перепроверка перед объявлением отказа. Две страницы, объявленные
      # отказом одиночным запросом, отдали плеер 12 раз из 12 при повторе —
      # то есть одиночный запрос по живой витрине даёт ложные срабатывания.
      # Гейт, который так делает, обесценивает себя: на исправной витрине он
      # показывает 28-29 из 30, и на настоящую поломку никто не посмотрит.
      sleep 2
      retry=$(curl -sS --max-time 25 -w '\n%{http_code}' "https://${hosts[$i]}/title/$s/" 2>/dev/null)
      retry_rc=$?
      retry_code=${retry##*$'\n'}
      if [ "$retry_rc" -eq 0 ] && [ "$retry_code" = "200" ] \
         && printf '%s' "$retry" | grep -q "<video-player"; then
        hit=$((hit + 1))
        flaky=$((flaky + 1))
      else
        miss=$((miss + 1))
        echo "      БЕЗ ПЛЕЕРА при наличии потока (подтверждено повтором): ${hosts[$i]}/title/$s/"
      fi
    fi
  done
  total_ok=$((total_ok + hit))
  total_bad=$((total_bad + miss))
  total_absent=$((total_absent + absent))
  total_broken=$((total_broken + broken))
  total_flaky=$((total_flaky + flaky))
  printf '  %-9s плеер найден %s из %s (страниц нет: %s)\n' \
    "${sites[$i]}" "$hit" "$((hit + miss))" "$absent"
done

echo "  ИТОГО: ${total_ok}/$((total_ok + total_bad)) страниц с потоком"
if [ "$total_flaky" -gt 0 ]; then
  echo "  ПОДТВЕРЖДЕНО ПОВТОРОМ: ${total_flaky} страниц отдали плеер со второго запроса"
fi
if [ "$total_broken" -gt 0 ]; then
  echo "  НЕ ВЫПОЛНЕНО ПРОВЕРОК: ${total_broken} — связь оборвалась, витрина ни при чём"
fi
if [ "$total_absent" -gt 0 ]; then
  echo "  ОТСТАВАНИЕ РЕЛИЗА: ${total_absent} произведений из выборки ещё не отрисованы"
  echo "  Это не отказ плеера. Отдельный счётчик заведён потому, что раньше такие"
  echo "  случаи попадали в отказы и давали 28-29 из 30 на исправной витрине."
fi
[ "$total_bad" -eq 0 ]
