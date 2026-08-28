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
# Сколько записей дополняется из detail за прогон. Полный каталог за раз —
# это тысячи запросов подряд; покрытие набирается прогонами и кэшируется.
ENRICH_BUDGET="${LORDS_ENRICH_BUDGET:-300}"
# Проверяются самые свежие поступления: там сосредоточены записи без потока.
PLAY_BUDGET="${LORDS_PLAYABILITY_BUDGET:-400}"

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
  if ! "$PYTHON" - "$site" "$staging" "$ENRICH_BUDGET" "$PLAY_BUDGET" <<'PYEOF'
import os
import sys
from pathlib import Path

from factory.lords import live_site

site_id, out, budget = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])
play_budget = int(sys.argv[4]) if len(sys.argv) > 4 else 0

# Токен берётся из systemd credential — тем же путём, что и Publisher ID, и
# наружу не печатается. Без него обогащение просто не выполняется: страницы
# останутся беднее, но сайт соберётся и останется рабочим.
token = None
directory = os.environ.get("CREDENTIALS_DIRECTORY", "").strip()
if directory:
    name = os.environ.get("CDNVIDEOHUB_API_TOKEN_CREDENTIAL", "cdnvideohub_api_token")
    try:
        token = (Path(directory) / name).read_text(encoding="utf-8").strip() or None
    except OSError:
        token = None

result = live_site.build_live_site(
    site_id, output=out, enrich_budget=budget, credentials_token=token,
    playability_budget=play_budget)
report = result.report
coverage = report.get("coverage") or {}
# Первая строка — число записей, её читает вызывающий сценарий.
print(report["catalog"]["titles"])
# Остальное идёт в журнал: молчаливое обогащение уже один раз выглядело как
# работающее, хотя не выполнялось вовсе. Отчёт обязан быть виден.
play = report.get("playability")
if play is None:
    print("[поток] проверка не выполнялась: бюджет %s" % play_budget, file=sys.stderr)
elif isinstance(play, dict) and play.get("error"):
    print("[поток] ОШИБКА: %s" % play["error"], file=sys.stderr)
else:
    print("[поток] проверено %s, из кэша %s, играет %s, молчит %s, неизвестно %s" % (
        play.get("checked"), play.get("cached"), play.get("playable"),
        play.get("silent"), play.get("unknown")), file=sys.stderr)
    print("[витрина] подтверждённо играющих %s, молчащих %s" % (
        coverage.get("confirmed_playable"), coverage.get("confirmed_silent")),
        file=sys.stderr)
enrichment = report.get("enrichment")
if enrichment is None:
    print("[enrich] не выполнялось: бюджет %s, токен %s" % (
        budget, "есть" if token else "НЕТ"), file=sys.stderr)
elif isinstance(enrichment, dict) and enrichment.get("error"):
    print("[enrich] ОШИБКА: %s" % enrichment["error"], file=sys.stderr)
else:
    print("[enrich] запрошено %s, получено %s, из кэша %s, отказов %s" % (
        enrichment.get("requested"), enrichment.get("fetched"),
        enrichment.get("from_cache"), enrichment.get("failed")), file=sys.stderr)
print("[покрытие] описаний %s, стран %s, состава %s из %s" % (
    coverage.get("with_description"), coverage.get("with_country"),
    coverage.get("with_actors"), report["catalog"]["titles"]), file=sys.stderr)
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

  # --- PLAYER_FREEZE_GATE -------------------------------------------------
  # Плеер обязан пережить обновление каталога. Однажды он его не пережил:
  # Publisher ID перестал находиться, и КАЖДАЯ страница тайтла тихо заменила
  # плеер нейтральной фразой. Сайт при этом отвечал двумястами, карточки были
  # на месте, приёмка по содержимому проходила — а видео не было ни на одном
  # из трёх доменов. Проверка по числу карточек такую регрессию не видит.
  new_players="$(grep -rl "<video-player" "${staging}/title" 2>/dev/null | wc -l)"
  old_players=0
  [ -n "$current" ] && old_players="$(grep -rl "<video-player" "${current}/site/title" 2>/dev/null | wc -l)"
  # Источник вправе убрать видео у части тайтлов, поэтому сравнение с допуском;
  # обвал в разы или в ноль допуском не объясняется.
  floor=$(( old_players * 90 / 100 ))
  if [ "$old_players" -gt 0 ] && [ "$new_players" -lt "$floor" ]; then
    rm -rf "$staging"; trap - EXIT
    fail "${site}: плееров было ${old_players}, стало ${new_players} — обновление отклонено, витрина остаётся на прежнем релизе"
  fi
  log "${site}: плееров ${new_players} (было ${old_players})"

  if [ ! -d "$target" ]; then
    log "${site}: раскладываю релиз ${release}"
    mkdir -p "${target}"
    cp -a "${staging}" "${target}/site"
    # Рантайм берётся из репозитория, а не у предыдущего релиза. Копирование
    # у соседа означало, что исправление рантайма не доезжало до сайта
    # никогда: каждый новый релиз наследовал serve.py от старого.
    if ! "$PYTHON" - "${target}/serve.py" <<'RUNTIMEEOF'
import sys
from pathlib import Path

from factory.lords.bundle import RUNTIME

Path(sys.argv[1]).write_text(RUNTIME, encoding="utf-8")
RUNTIMEEOF
    then
      # Без рантайма релиз бесполезен; берём прежний, чтобы не остаться ни с чем.
      [ -n "$current" ] && cp -a "${current}/serve.py" "${target}/serve.py"
      log "${site}: рантайм из репозитория не собрался — оставлен прежний"
    fi
    for extra in bundle-manifest.json rollback.json README.md Dockerfile; do
      [ -f "${current}/${extra}" ] && cp -a "${current}/${extra}" "${target}/${extra}"
    done
    chown -R lords:lords "${target}"
  fi

  # Переключение релиза само по себе перезапуска не требует: рантайм читает
  # ссылку `current` на каждом запросе. Перезапуск нужен только когда меняется
  # сам рантайм — иначе в работе остался бы прежний serve.py.
  #
  # Прежде здесь стоял безусловный `systemctl restart`. Он давал 243
  # перезапуска в сутки, и в секундное окно между «остановлен» и «запущен»
  # nginx отвечал 502 — один такой ответ достался живому посетителю.
  need_restart=0
  if [ -z "$current" ] || ! systemctl is-active --quiet "${site}.service"; then
    need_restart=1
  elif ! cmp -s "${current}/serve.py" "${target}/serve.py"; then
    log "${site}: рантайм изменился — перезапуск нужен"
    need_restart=1
  fi

  ln -sfn "${target}" "${runtime}/current"
  if [ "$need_restart" = "1" ]; then
    systemctl restart "${site}.service"
  fi
  CHANGED=1

  # Приёмка сразу после переключения. Плохой релиз не остаётся в работе.
  port="$(grep -oP 'LORDS_PORT=\K[0-9]+' "/etc/systemd/system/${site}.service" | head -1)"
  ok=0
  for _ in $(seq 1 10); do
    sleep 2
    body="$(curl -sS --max-time 10 "http://127.0.0.1:${port}/" 2>/dev/null || true)"
    if [ "${#body}" -gt 4000 ] && printf '%s' "$body" | grep -q 'class="card'; then
      # Главная карточками отвечает — проверяем ещё и страницу тайтла: именно
      # там живёт плеер, и именно его теряли прошлые обновления.
      slug="$(printf '%s' "$body" | grep -o 'href="/title/[^"]*"' | head -1 | sed 's|href="||;s|"||')"
      if [ -n "$slug" ] && [ "$new_players" -gt 0 ]; then
        tp="$(curl -sS --max-time 10 "http://127.0.0.1:${port}${slug}" 2>/dev/null || true)"
        printf '%s' "$tp" | grep -q "<video-player" || continue
      fi
      ok=1; break
    fi
  done
  if [ "$ok" != "1" ]; then
    log "${site}: новый релиз не отвечает содержимым — возвращаю ${current##*/}"
    ln -sfn "${current}" "${runtime}/current"
    # Откат тоже переключением ссылки: перезапуск здесь добавил бы к неудачному
    # обновлению ещё и недоступность.
    if [ "$need_restart" = "1" ]; then
      systemctl restart "${site}.service"
    fi
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
