#!/usr/bin/env bash
# Холостой прогон релиза B16 под профилем animedia-space на отдельном порту.
#
# Перезапуск боевой витрины — необратимое действие: если релиз не поднимется,
# домен ляжет, и узнаем мы об этом уже после. Тот же код с тем же окружением,
# запущенный рядом, отвечает на вопрос «поднимется ли» заранее и ничего не
# трогает: живая служба продолжает работать на своём процессе.
#
# Окружение взято из `systemctl show nova-animedia-02.service -p Environment`,
# а не составлено по памяти. Отличается ровно порт.
set -Eeuo pipefail

PORT="${1:-9500}"
RELEASE=/srv/lords/.frontend/releases/20260921T153817Z-c8c4587-animedia-b16/lords-frontend.py

export LORDS_TEMPLATE_MANIFEST=/srv/lords/.frontend/template-manifest-animedia-02.json
export LORDS_CATALOG=/srv/lords/.frontend/animedia-02-catalog.json
export LORDS_LEGACY_ROOT=/srv/lords/animedia-02/current/site
export LORDS_SITE_NAME=Animedia
export PYTHONDONTWRITEBYTECODE=1

exec /usr/bin/python3 "$RELEASE" --port "$PORT"
