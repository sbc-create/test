#!/usr/bin/env bash
# Запуск контентного скрипта YummyAnime внутри боевого образа.
#
# Зачем. Контентные юниты исполняли скрипты прямо из рабочего дерева git:
# `ExecStart=/usr/bin/node /srv/sites/yummyani-staging/repo/scripts/…`. Значит
# `git checkout` в этом каталоге молча менял поведение боевого контента — без
# выкатки, без отката и без записи о том, какая версия работает. Измерено
# 2026-09-03: три таких юнита исполнялись с ветки, отличной от той, из которой
# собран боевой образ, и с незакоммиченной правкой в дереве.
#
# Здесь код берётся из образа: `docker compose run` поднимает тот же образ, что
# обслуживает витрину, поэтому «что работает в контенте» и «что работает на
# сайте» перестают расходиться молча. Приём не выдуман — так уже устроен
# `yummy-catalog-index-sync`, и этот скрипт лишь распространяет его на остальные.
#
# Что остаётся зависимым от дерева: сам `compose.staging.yaml`, потому что он
# описывает сервисы. Это меньшая зависимость — описание服务, а не исполняемый
# код, — но называть её надо честно.
#
# Использование:
#   yummy-content-run.sh scripts/episode-watcher.mjs
#   YUMMY_CONTENT_SERVICE=web-org yummy-content-run.sh scripts/watchdog-run.mjs
set -Eeuo pipefail

PROJECT="${YUMMY_CONTENT_PROJECT:-yummyani-staging}"
REPO="${YUMMY_CONTENT_REPO:-/srv/sites/yummyani-staging/repo}"
COMPOSE_FILE="${YUMMY_CONTENT_COMPOSE:-${REPO}/compose.staging.yaml}"
ENV_FILE="${YUMMY_CONTENT_ENV:-/srv/sites/yummyani-staging/runtime/compose.vars}"
# Наблюдатель и сторож общие на парк: снимок один и лежит в общем томе, поэтому
# запускать их достаточно в одной витрине. Выбор витрины вынесен в переменную,
# чтобы не прятать его в коде.
SERVICE="${YUMMY_CONTENT_SERVICE:-web-site}"

[ "$#" -ge 1 ] || { echo "нужен путь скрипта внутри образа, например scripts/episode-watcher.mjs" >&2; exit 2; }

case "$1" in
  /*)
    # Абсолютный путь означал бы возврат к исполнению из дерева хоста — ровно
    # то, ради устранения чего написан этот скрипт.
    echo "путь скрипта обязан быть относительным (внутри образа), получено: $1" >&2
    exit 2
    ;;
esac

exec docker compose -p "$PROJECT" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" \
  run --rm --no-deps -T "$SERVICE" node "$@"
