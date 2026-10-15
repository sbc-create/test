#!/usr/bin/env bash
# B016 для yummyani7.site и yummyani7.info: закрепить УЖЕ СОБРАННЫЙ образ.
#
#   bash automation/host/yummy7-b016-repin.sh yummyani7-info [--dry-run]
#
# Почему без сборки. Обе витрины работают на `yummyani/web:rel-4c5796eae24c` —
# том же образе, что yummyani.biz до выпуска 15.10. Выпуск собрал из этой же
# базы патченный образ `rel-21184803b90f` (B016: SWR v2 + снятие потолка 8000,
# плюс вариант T081 для 4c5796e) и принял его на yummyani.biz. Значит для этих
# двух витрин исправление доставляется закреплением готового образа, а не новой
# сборкой: ни одна строка кода не отличается от уже принятой.
#
# Проверено до запуска: на главных обеих витрин ноль ссылок вида `slug--uuid`
# (48 ссылок на каждой), то есть признак T081, из-за которого откатилась
# yummyani.site, здесь выполнен заранее.
#
# Что делает: копия файла compose рядом, замена строки образа у службы `web`,
# пересоздание ТОЛЬКО `web`, проверка живого сайта. При любой неудаче файл
# возвращается и служба пересоздаётся обратно.
#
# Имена переменных только ASCII: кириллица в именах переменных оболочки падает
# в работе, а `bash -n` её пропускает.
set -Eeuo pipefail

project="${1:?нужен проект: yummyani7-info или yummyani7-site}"
shift || true
dry_run=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry_run=1 ;;
    *) echo "неизвестный аргумент: $arg" >&2; exit 2 ;;
  esac
done

case "$project" in
  yummyani7-info) domain="yummyani7.info"; app_port=3105 ;;
  yummyani7-site) domain="yummyani7.site"; app_port=3104 ;;
  *) echo "неизвестный проект: $project" >&2; exit 2 ;;
esac

repo="${YUMMY7_REPO:-/home/claude/wt-nova-publish-memory-02/var/site-repos/$project}"
compose="$repo/deploy/compose.yaml"
new_image="${YUMMY7_IMAGE:-yummyani/web:rel-21184803b90f}"
# Файл переменных контура. Compose подставляет из него пароль базы и прочее;
# значение секрета сценарий не читает и не печатает — только передаёт файл
# в `docker compose --env-file`, как это делает выпуск трёх арендаторов.
env_file="${YUMMY7_ENV_FILE:-/srv/sites/yummyani-staging/runtime/compose.vars}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$compose.bak.$stamp"

log() { printf '==> %s\n' "$*"; }
die() { printf '[x] %s\n' "$*" >&2; exit 1; }

# --- предусловия ----------------------------------------------------------
[ -f "$compose" ] || die "нет файла compose: $compose"
[ -r "$env_file" ] || die "файл переменных недоступен: $env_file"
docker image inspect "$new_image" >/dev/null 2>&1 || die "образа $new_image нет на узле"
rev="$(docker image inspect "$new_image" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')"
[ -n "$rev" ] || die "у образа $new_image нет метки ревизии"
log "проект $project, домен $domain, образ $new_image (ревизия ${rev:0:12})"

current_image="$(docker inspect "$project-web-1" --format '{{.Config.Image}}' 2>/dev/null || true)"
[ -n "$current_image" ] || die "контейнер $project-web-1 не найден"
log "сейчас работает: $current_image"
if [ "$current_image" = "$new_image" ]; then
  log "образ уже закреплён — делать нечего"
  exit 0
fi

# Жив ли контейнер — по State, а не по строке состояния (урок 15.10).
running="$(docker inspect "$project-web-1" --format '{{.State.Running}}')"
[ "$running" = "true" ] || die "контейнер $project-web-1 не работает (State.Running=$running)"

before_code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "https://$domain/" || true)"
[ "$before_code" = "200" ] || die "до правки сайт отвечает $before_code — не время менять образ"
before_links="$(curl -s --max-time 40 "https://$domain/" | grep -o 'href="/anime/[^"]*"' | sort -u | wc -l)"
log "до правки: сайт 200, ссылок /anime/ $before_links"

if [ "$dry_run" = 1 ]; then
  log "сухой прогон: предусловия выполнены, образ не менялся"
  exit 0
fi

# --- замена образа с копией ------------------------------------------------
cp -p "$compose" "$backup"
log "копия файла: $backup"
python3 - "$compose" "$current_image" "$new_image" <<'PY'
import re
import sys

путь, старый, новый = sys.argv[1], sys.argv[2], sys.argv[3]
текст = open(путь, encoding="utf-8").read()
# Меняется ТОЛЬКО строка образа службы web: другие службы (pg, redis, mailpit)
# не трогаются, и комментарий рядом сохраняется как есть.
образец = re.compile(r"(?m)^(\s*)image:\s*" + re.escape(старый) + r"(\s*(#.*)?)$")
совпадений = len(образец.findall(текст))
if совпадений != 1:
    sys.exit(f"ожидалась одна строка образа {старый}, найдено {совпадений}")
текст = образец.sub(lambda м: f"{м.group(1)}image: {новый}{м.group(2)}", текст, count=1)
open(путь, "w", encoding="utf-8").write(текст)
print(f"строка образа заменена: {старый} → {новый}")
PY

restore() {
  printf '[!] возвращаю прежний образ\n' >&2
  cp -p "$backup" "$compose"
  docker compose -p "$project" -f "$compose" --env-file "$env_file" up -d --no-deps web >/dev/null 2>&1 || true
  sleep 10
  printf '[!] после возврата: сайт отвечает %s, образ %s\n' \
    "$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "https://$domain/" || true)" \
    "$(docker inspect "$project-web-1" --format '{{.Config.Image}}' 2>/dev/null || true)" >&2
}

log "пересоздаю службу web"
if ! docker compose -p "$project" -f "$compose" --env-file "$env_file" up -d --no-deps web; then
  restore
  die "пересоздание не удалось"
fi

# --- проверка --------------------------------------------------------------
ok=1
for i in $(seq 1 30); do
  state="$(docker inspect "$project-web-1" --format '{{.State.Running}}/{{if .State.Health}}{{.State.Health.Status}}{{else}}нет{{end}}' 2>/dev/null || true)"
  case "$state" in
    true/healthy) log "контейнер healthy за ${i}0 с"; ok=0; break ;;
    true/нет) log "контейнер работает (проверки здоровья нет)"; ok=0; break ;;
  esac
  sleep 10
done
[ "$ok" = 0 ] || { restore; die "контейнер не стал healthy"; }

code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 40 "https://$domain/" || true)"
[ "$code" = "200" ] || { restore; die "сайт отвечает $code"; }

links="$(curl -s --max-time 40 "https://$domain/" | grep -o 'href="/anime/[^"]*"' | sort -u | wc -l)"
uuid_links="$(curl -s --max-time 40 "https://$domain/" | grep -o 'href="/anime/[^"]*--[0-9a-f]\{8\}-[^"]*"' | sort -u | wc -l)"
log "после правки: сайт 200, ссылок /anime/ $links, из них составных $uuid_links"
[ "$uuid_links" = "0" ] || { restore; die "появились составные ссылки: $uuid_links"; }

inv="$(curl -s -o /dev/null -D - --max-time 90 -H "Host: $domain" \
        "http://127.0.0.1:$app_port/sitemap/titles.xml" | grep -i '^x-sitemap-inventory' | tr -d '\r' || true)"
[ -n "$inv" ] || { restore; die "нет заголовка x-sitemap-inventory — не новый код"; }
log "инвентарь карты: $inv"

urls="$(curl -s --max-time 120 "https://$domain/sitemap/titles.xml" | grep -c '<loc>' || true)"
log "адресов в titles.xml: $urls (до правки было ровно 8000)"
[ "$urls" -gt 8000 ] || { restore; die "потолок 8000 не снят: $urls"; }

log "готово: $project на $new_image, карта без потолка, сайт отвечает"
log "копия прежнего файла оставлена: $backup"
