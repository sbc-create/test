#!/usr/bin/env bash
# Приёмка индексации yummyani.site — read-only, без единой мутации.
#
# Проверяет ровно те требования владельца, которые перечислены в задании, и
# печатает по строке на каждое: PASS или FAIL с фактом, а не с пересказом.
#
# Сценарий один и тот же до и после выкладки: прогон до правки фиксирует
# baseline, прогон после — доказательство. Отдельная «проверялка результата»
# рядом с «проверялкой baseline» разошлась бы с ней молча.
#
# Запуск (root не нужен):
#   bash automation/host/yummy-indexing-verify.sh
#
# Код возврата: 0 — все требования выполнены; 1 — есть FAIL.
#
# Проверяется то, что увидит краулер: живые ответы через nginx и через витрину,
# а не содержимое конфигурации.

set -uo pipefail

readonly HOST_SITE=yummyani.site
readonly PORT_SITE=9132
readonly PORT_ORG=9131
readonly PORT_BIZ=9130

PASS_COUNT=0
FAIL_COUNT=0

ok()   { printf '  \033[32mPASS\033[0m  %s\n' "$*"; PASS_COUNT=$((PASS_COUNT + 1)); }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$*"; FAIL_COUNT=$((FAIL_COUNT + 1)); }
head_() { printf '\n\033[1m%s\033[0m\n' "$*"; }

# Ответ витрины по пути. Host задаётся явно: витрина строит canonical,
# Open Graph и sitemap из переданного Host.
fetch() {
  local path="$1" port="${2:-${PORT_SITE}}" host="${3:-${HOST_SITE}}"
  curl -sS --max-time 30 -H "Host: ${host}" \
       "http://127.0.0.1:${port}${path}" 2>/dev/null || true
}

fetch_head() {
  local path="$1" port="${2:-${PORT_SITE}}" host="${3:-${HOST_SITE}}"
  curl -sS -D - -o /dev/null --max-time 30 -H "Host: ${host}" \
       "http://127.0.0.1:${port}${path}" 2>/dev/null || true
}

status_of() {
  local path="$1" port="${2:-${PORT_SITE}}" host="${3:-${HOST_SITE}}"
  curl -sS -o /dev/null -w '%{http_code}' --max-time 30 -H "Host: ${host}" \
       "http://127.0.0.1:${port}${path}" 2>/dev/null || echo 000
}

# ------------------------------------------------- 1. транспорт и доступ ---
head_ "1. Транспорт"

redirect="$(curl -sS -D - -o /dev/null --max-time 20 -H "Host: ${HOST_SITE}" \
            http://127.0.0.1:80/ 2>/dev/null || true)"
if grep -qiE '^HTTP/[0-9.]+ 30[18]' <<<"${redirect}" \
   && grep -qi "^location: https://${HOST_SITE}/" <<<"${redirect}"; then
  ok "HTTP перенаправляется на HTTPS ($(grep -ioE 'HTTP/[0-9.]+ [0-9]{3}' <<<"${redirect}" | head -1))"
else
  bad "HTTP не перенаправляется на HTTPS корректно"
fi

https_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 30 -k \
              -H "Host: ${HOST_SITE}" https://127.0.0.1:443/ 2>/dev/null || echo 000)"
if [ "${https_code}" = "200" ]; then
  ok "HTTPS отдаёт финальный 200"
else
  bad "HTTPS отдаёт ${https_code}, ожидался 200"
fi

if grep -qi '^www-authenticate:' <<<"$(fetch_head /)"; then
  bad "включён Basic Auth — краулер не пройдёт"
else
  ok "Basic Auth отсутствует"
fi

# ------------------------------------------------------- 2. индексация ---
head_ "2. Индексация ${HOST_SITE}"

home_head="$(fetch_head /)"
if grep -qi '^X-Robots-Tag:.*noindex' <<<"${home_head}"; then
  bad "X-Robots-Tag содержит глобальный noindex: $(grep -i '^X-Robots-Tag:' <<<"${home_head}" | head -1 | tr -d '\r')"
else
  ok "X-Robots-Tag не содержит глобального noindex"
fi

home_body="$(fetch /)"
if grep -qiE '<meta[^>]+name="robots"[^>]+content="[^"]*noindex' <<<"${home_body}"; then
  bad "HTML главной содержит глобальный meta robots noindex"
else
  ok "HTML главной без глобального meta robots noindex"
fi

robots="$(fetch /robots.txt)"
if grep -qE '^[[:space:]]*Disallow:[[:space:]]*/[[:space:]]*$' <<<"${robots}"; then
  bad "robots.txt содержит Disallow: / — сайт закрыт целиком"
else
  ok "robots.txt не содержит Disallow: /"
fi

if grep -qi '^sitemap:' <<<"${robots}"; then
  ok "robots.txt объявляет Sitemap"
else
  bad "robots.txt не объявляет Sitemap"
fi

# ----------------------------------------------------------- 3. sitemap ---
head_ "3. Карта сайта"

sitemap="$(fetch /sitemap.xml)"
# `grep -c` при нуле совпадений печатает 0 и выходит с единицей. Поэтому
# `|| echo 0` дописал бы второй ноль и сломал арифметику: гасится `|| true`.
loc_total="$(grep -c '<loc>' <<<"${sitemap}" || true)"
loc_site="$(grep -o "<loc>https://${HOST_SITE}[^<]*</loc>" <<<"${sitemap}" | wc -l || true)"
loc_total="${loc_total:-0}"
loc_site="${loc_site:-0}"
loc_alien="$((loc_total - loc_site))"

if [ "${loc_total}" -gt 0 ]; then
  ok "sitemap доступен и не пуст (URL: ${loc_total})"
else
  bad "sitemap пуст: ни одного <loc>"
fi

if [ "${loc_site}" -gt 0 ]; then
  ok "sitemap содержит URL ${HOST_SITE} (${loc_site})"
else
  bad "в sitemap нет ни одного URL ${HOST_SITE}"
fi

if [ "${loc_alien}" -gt 0 ]; then
  bad "в sitemap ${loc_alien} URL чужого домена"
elif [ "${loc_total}" -gt 0 ]; then
  ok "sitemap не подменён другим доменом"
else
  # Молчать здесь нельзя: пропуск проверки выглядел бы как пройденная проверка.
  bad "подмену домена в sitemap проверить не на чем — карта пуста"
fi

# --------------------------------------------------------- 4. canonical ---
head_ "4. Canonical и доступность разделов"

canonical_of() { grep -oE '<link rel="canonical" href="[^"]+"' <<<"$1" | head -1 | sed 's/.*href="//;s/"$//'; }

home_canonical="$(canonical_of "${home_body}")"
if [[ "${home_canonical}" == "https://${HOST_SITE}"* ]]; then
  ok "canonical главной указывает на ${HOST_SITE}: ${home_canonical}"
else
  bad "canonical главной указывает не туда: ${home_canonical:-отсутствует}"
fi

# Маршруты взяты из живого кода витрины, а не придуманы.
for route in / /catalog /catalog/top /catalog/anime-updates /catalog/ongoing /posts; do
  code="$(status_of "${route}")"
  if [ "${code}" = "200" ]; then
    ok "${route} → 200"
  else
    bad "${route} → ${code}"
  fi
done

# Карточка тайтла: адрес берётся из живого DOM каталога, не выдумывается.
slug="$(grep -oE 'href="/anime/[a-z0-9-]+"' <<<"$(fetch /catalog/top)" \
        | head -1 | sed 's|href="||;s|"$||')"
if [ -n "${slug}" ]; then
  code="$(status_of "${slug}")"
  body="$(fetch "${slug}")"
  canon="$(canonical_of "${body}")"
  if [ "${code}" = "200" ]; then
    ok "карточка ${slug} → 200"
  else
    bad "карточка ${slug} → ${code}"
  fi
  if [ "${canon}" = "https://${HOST_SITE}${slug}" ]; then
    ok "canonical карточки указывает на свою сущность"
  else
    bad "canonical карточки: ${canon:-отсутствует}, ожидался https://${HOST_SITE}${slug}"
  fi
else
  bad "не удалось получить ни одной карточки из /catalog/top"
fi

# Несуществующий адрес обязан быть честным 404, а не soft-404.
code="$(status_of /anime/zzz-definitely-not-a-real-title-9999)"
if [ "${code}" = "404" ]; then
  ok "несуществующая карточка → честный 404"
else
  bad "несуществующая карточка → ${code} (soft-404)"
fi

# -------------------------------------------- 5. соседние площадки ---
head_ "5. Соседние площадки не затронуты"

for pair in "yummyani.org:${PORT_ORG}" "yummyani.biz:${PORT_BIZ}"; do
  host="${pair%%:*}"
  port="${pair##*:}"
  h="$(fetch_head / "${port}" "${host}")"
  if [ -z "${h}" ]; then
    bad "${host} не ответил"
  elif grep -qi '^X-Robots-Tag:.*noindex' <<<"${h}"; then
    ok "${host} закрыт, как и был"
  else
    bad "${host} ПЕРЕСТАЛ быть закрытым — политика соседней площадки изменена"
  fi
done

# ------------------------------------------------------------- итог ---
printf '\n\033[1mИтог: PASS %d, FAIL %d\033[0m\n' "${PASS_COUNT}" "${FAIL_COUNT}"
[ "${FAIL_COUNT}" -eq 0 ]
