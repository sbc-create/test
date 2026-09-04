#!/usr/bin/env bash
# Функциональная проверка витрин: код ответа успехом не считается.
#
# 2026-09-04 после перезагрузки под новый тариф Redis циклически падал с
# повреждённым AOF. Все три витрины при этом отдавали HTTP 200 — и пустой
# каталог: ноль карточек на главной. Проверки по коду ответа отказ не увидели,
# и он держался, пока его не заметили глазами.
#
# Поэтому здесь считается содержимое, а не статус. Пустой каталог при 200 —
# авария, а не успех.
set -uo pipefail

HOSTS="${CATALOG_CHECK_HOSTS:-yummyani.site yummyani.org yummyani.biz}"
MIN_TITLES="${CATALOG_CHECK_MIN_TITLES:-20}"
TIMEOUT="${CATALOG_CHECK_TIMEOUT:-25}"
REPORT="${CATALOG_CHECK_REPORT:-}"

problems=0
lines=""

for host in $HOSTS; do
  body="$(curl -sSL -m "$TIMEOUT" "https://${host}/" 2>/dev/null)"
  code="$(curl -sS -o /dev/null -w '%{http_code}' -m "$TIMEOUT" "https://${host}/" 2>/dev/null)"
  titles="$(printf '%s' "$body" | grep -oE '/anime/[a-z0-9-]+' | sort -u | wc -l | tr -d ' ')"

  if [ "$code" != "200" ]; then
    lines="${lines}ТРЕВОГА ${host}: код ${code}"$'\n'
    problems=$((problems + 1))
    continue
  fi

  # Здесь и лежит смысл проверки: 200 получен, но каталога нет.
  if [ "${titles:-0}" -lt "$MIN_TITLES" ]; then
    lines="${lines}ТРЕВОГА ${host}: код 200, но тайтлов ${titles} при пороге ${MIN_TITLES} — пустой каталог"$'\n'
    problems=$((problems + 1))
  else
    lines="${lines}ок ${host}: код 200, тайтлов ${titles}"$'\n'
  fi
done

printf '%s' "$lines"

if [ -n "$REPORT" ]; then
  status=$([ "$problems" -eq 0 ] && echo ok || echo alert)
  printf '{"checkedAt":"%s","status":"%s","problems":%d}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status" "$problems" > "$REPORT" 2>/dev/null
fi

if [ "$problems" -gt 0 ]; then
  printf 'витрин с отказом: %d\n' "$problems" >&2
  exit 1
fi
exit 0
