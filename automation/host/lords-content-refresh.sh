#!/usr/bin/env bash
# Автоматическое обновление каталога Lords без пересборки образа и без человека.
#
# Зачем. Сайты Lords статические: их документы собираются заранее и раскладываются
# релизом. Живой каталог при этом кэшировался вручную, а пересобирал сайт человек.
# В итоге на трёх публичных доменах месяцами стоял каталог тридцатипятичасовой
# давности: провайдер добавлял фильмы, а витрина о них не знала. HTTP 200 при
# этом отвечал исправно — именно поэтому проблему было легко не заметить.
#
# Что делает этот сценарий: обновляет кэш живого каталога, пересобирает сайт
# ТОЛЬКО если каталог действительно изменился, раскладывает новый релиз рядом со
# старым и переключает на него трафик. Прежний релиз остаётся на месте — откат
# это переключение символической ссылки обратно.
#
# Чего он не делает: не собирает образ, не трогает nginx, не выпускает
# сертификаты, не удаляет предыдущие релизы и не публикует пустой каталог.
set -Eeuo pipefail

REPO="${FACTORY_REPO:-/srv/site-factory/repo}"
PYTHON="${FACTORY_PYTHON:-${REPO}/.venv/bin/python}"
SITES=(lords-01 lords-02 lords-03)
STATE_DIR="${LORDS_REFRESH_STATE:-/var/lib/lords-content-refresh}"
KEEP_RELEASES="${LORDS_KEEP_RELEASES:-4}"

log()  { printf '[lords-refresh] %s\n' "$*"; }
fail() { printf '[lords-refresh] ОТКАЗ: %s\n' "$*" >&2; exit 1; }

mkdir -p "$STATE_DIR"

# ---------------------------------------------------------------- 1. каталог
# Значения credentials читает сам factory через $CREDENTIALS_DIRECTORY и наружу
# не отдаёт. Здесь их не видно и не должно быть видно.
log "обновляю живой каталог"
# Диагностика factory уходит в stdout, а не в stderr: перехватываем оба потока,
# иначе файл с причиной отказа останется пустым ровно тогда, когда он нужен.
if ! "$PYTHON" -m factory lords-live >"${STATE_DIR}/last-fetch.log" 2>&1; then
  tail -5 "${STATE_DIR}/last-fetch.log" >&2 || true
  # Отказ источника не повод портить витрину: прежний релиз остаётся на месте
  # и продолжает отвечать. Это и есть last-known-good.
  date -u +%Y-%m-%dT%H:%M:%SZ > "${STATE_DIR}/last_failure"
  fail "обновление каталога не выполнено; витрина оставлена на прежнем релизе. Причина в ${STATE_DIR}/last-fetch.log — источник мог ответить, а отказать могла запись"
fi

CHANGED=0

for site in "${SITES[@]}"; do
  runtime="/srv/lords/${site}"
  current="$(readlink -f "${runtime}/current" 2>/dev/null || true)"
  staging="$(mktemp -d)"
  # shellcheck disable=SC2064
  trap "rm -rf '${staging}'" EXIT

  # Сборка в сторону. Пустой каталог останавливает сборку внутри build_live_site,
  # поэтому пустая витрина сюда не доедет.
  if ! "$PYTHON" - "$site" "$staging" <<'PYEOF'
import sys
from pathlib import Path
from factory.lords import live_site
site_id, out = sys.argv[1], Path(sys.argv[2])
result = live_site.build_live_site(site_id, output=out)
print(result.report["catalog"]["titles"])
PYEOF
  then
    fail "${site}: сборка не выполнена"
  fi

  # Идентификатор релиза — от содержимого. Одинаковая сборка даёт один и тот же
  # релиз, поэтому неизменившийся каталог не плодит каталоги и не рестартует юнит.
  release="$(find "$staging" -type f -print0 | sort -z \
             | xargs -0 sha256sum | sha256sum | cut -c1-12)"
  target="${runtime}/releases/${release}"

  if [ "$current" = "$target" ]; then
    log "${site}: каталог не изменился, релиз ${release} уже работает"
    rm -rf "$staging"; trap - EXIT
    continue
  fi

  if [ ! -d "$target" ]; then
    log "${site}: раскладываю релиз ${release}"
    mkdir -p "${target}"
    cp -a "${staging}" "${target}/site"
    # Рантайм не меняется этой выкладкой: serve.py берётся у текущего релиза.
    [ -n "$current" ] && cp -a "${current}/serve.py" "${target}/serve.py"
    for extra in bundle-manifest.json rollback.json README.md Dockerfile; do
      [ -f "${current}/${extra}" ] && cp -a "${current}/${extra}" "${target}/${extra}"
    done
    chown -R lords:lords "${target}"
  fi

  ln -sfn "${target}" "${runtime}/current"
  systemctl restart "${site}.service"
  CHANGED=1

  # Приёмка сразу после переключения. Плохой релиз не остаётся в работе.
  port="$(grep -oP 'LORDS_PORT=\K[0-9]+' "/etc/systemd/system/${site}.service" | head -1)"
  ok=0
  for _ in $(seq 1 10); do
    sleep 2
    body="$(curl -sS --max-time 10 "http://127.0.0.1:${port}/" 2>/dev/null || true)"
    if [ "${#body}" -gt 4000 ] && printf '%s' "$body" | grep -q 'class="card'; then
      ok=1; break
    fi
  done
  if [ "$ok" != "1" ]; then
    log "${site}: новый релиз не отвечает содержимым — возвращаю ${current##*/}"
    ln -sfn "${current}" "${runtime}/current"
    systemctl restart "${site}.service"
    fail "${site}: откат выполнен, витрина на прежнем релизе"
  fi
  log "${site}: релиз ${release} принят"

  # Хранение: удаляются только наши же прежние релизы и никогда текущий.
  mapfile -t old < <(ls -1dt "${runtime}/releases/"*/ 2>/dev/null | tail -n +$((KEEP_RELEASES + 1)))
  for dir in ${old[@]+"${old[@]}"}; do
    [ "$(readlink -f "$dir")" = "$(readlink -f "${runtime}/current")" ] && continue
    rm -rf "$dir"
  done

  rm -rf "$staging"; trap - EXIT
done

date -u +%Y-%m-%dT%H:%M:%SZ > "${STATE_DIR}/last_success"
rm -f "${STATE_DIR}/last_failure"
log "готово; сайтов обновлено: ${CHANGED}"
