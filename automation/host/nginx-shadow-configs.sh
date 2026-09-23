#!/usr/bin/env bash
# Резервные копии конфигураций, которые nginx ЗАГРУЖАЕТ.
#
#   bash automation/host/nginx-shadow-configs.sh            # только показать
#   sudo bash automation/host/nginx-shadow-configs.sh --fix  # убрать из загрузки
#
# Откуда берётся дубль
# --------------------
#
# В nginx.conf стоит `include /etc/nginx/sites-enabled/*` — БЕЗ фильтра по
# расширению. Рядом с рабочей конфигурацией кто-то оставил её копию с меткой
# времени, и эта копия тоже загружается: те же server_name на тех же портах
# объявлены дважды. nginx пишет `conflicting server name` и берёт ПЕРВЫЙ
# подходящий блок в порядке разворачивания шаблона.
#
# Сейчас порядок спасает: «yummyani.biz.conf» сортируется раньше, чем
# «yummyani.biz.conf.bak.…», и выигрывает рабочий файл. Но копия содержит
# ПРЕЖНИЙ маршрут (прямо в контейнер), и любое имя, которое отсортируется
# раньше рабочего, молча вернёт трафик на старый адрес. Это не косметика:
# предупреждение в журнале и подмена маршрута — одно и то же событие.
#
# Почему перенос, а не удаление
# -----------------------------
#
# Копию делал не этот контур, и что в ней ценного — решать её автору. Файлы
# переносятся в /var/backups с сохранением исходного пути; загрузку они
# покидают, содержимое остаётся. `nginx -t` выполняется ДО reload; не прошёл —
# файлы возвращаются на место.
#
# Чего сценарий не делает: не трогает рабочие конфигурации, сертификаты,
# маршруты в контейнеры и `include` в nginx.conf. Менять `*` на `*.conf` было
# бы худшим из решений: в sites-enabled лежит `000-default-deny` без
# расширения, и такая «починка» выключила бы запрет по умолчанию.
set -Eeuo pipefail

fix=0
[ "${1:-}" = "--fix" ] && fix=1

NGINX_CONF=/etc/nginx/nginx.conf
STORE=/var/backups/nginx-shadowed
stamp="$(date -u +%Y%m%dT%H%M%SZ)"

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
die() { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$fix" = 0 ] || [ "$(id -u)" = 0 ] || die "для --fix нужен root"
[ -r "$NGINX_CONF" ] || die "не читается $NGINX_CONF"

# Шаблоны include собираются ПО ВСЕЙ загруженной конфигурации, а не только из
# nginx.conf: `conf.d/lords.conf` сам включает целый каталог, и остановиться на
# первом файле значило бы проверить одну ветку из двух. Файл, который не
# читается, честно называется — молча пропустить его нельзя.
collect_patterns() {
  local queue=("$NGINX_CONF") seen=() conf pattern path
  while [ "${#queue[@]}" -gt 0 ]; do
    conf="${queue[0]}"; queue=("${queue[@]:1}")
    case " ${seen[*]-} " in *" $conf "*) continue ;; esac
    seen+=("$conf")
    if [ ! -r "$conf" ]; then
      printf '\033[33m[!]\033[0m не читается, ветка не проверена: %s\n' "$conf" >&2
      continue
    fi
    while read -r pattern; do
      [ -n "$pattern" ] || continue
      printf '%s\n' "$pattern"
      case "$pattern" in
        */mime.types|*/modules-enabled/*) continue ;;
      esac
      for path in $pattern; do
        [ -f "$path" ] && queue+=("$path")
      done
    done < <(grep -hoE '^[[:space:]]*include[[:space:]]+[^;]+;' "$conf" \
             | sed -E 's/^[[:space:]]*include[[:space:]]+//; s/;$//')
  done
}

mapfile -t patterns < <(collect_patterns | grep -F '*' | sort -u || true)

shadowed=()
for pattern in "${patterns[@]}"; do
  case "$pattern" in
    *'*.conf') continue ;;   # копии с меткой времени сюда не попадают
  esac
  log "шаблон без фильтра: $pattern"
  for path in $pattern; do
    [ -f "$path" ] || continue
    case "$(basename "$path")" in
      *.bak|*.bak.*|*.before*|*.orig|*.save|*~|*.dpkg-*|*.rpmsave)
        shadowed+=("$path") ;;
    esac
  done
done

if [ "${#shadowed[@]}" -eq 0 ]; then
  log "теневых копий в загрузке нет"
  exit 0
fi

log "загружаются как конфигурация, хотя это копии:"
for path in "${shadowed[@]}"; do
  names="$(grep -hoE 'server_name[^;]+' "$path" 2>/dev/null | sed 's/server_name[[:space:]]*//' \
           | tr '\n' ' ' | tr -s ' ')"
  printf '   %s\n      имена: %s\n' "$path" "${names:-нет}"
done

if [ "$fix" = 0 ]; then
  echo
  echo "показ завершён: ничего не менялось. Убрать из загрузки: sudo bash $0 --fix"
  exit 0
fi

log "перенос в $STORE/$stamp"
moved=()
for path in "${shadowed[@]}"; do
  target="$STORE/$stamp${path}"
  install -d -m 0700 "$(dirname "$target")"
  mv "$path" "$target"
  moved+=("$path")
  printf '   %s -> %s\n' "$path" "$target"
done

restore() {
  printf '\033[33m[!]\033[0m возврат копий на место\n' >&2
  for path in "${moved[@]}"; do
    mv "$STORE/$stamp${path}" "$path" || true
  done
}

log "проверка конфигурации"
if ! nginx -t; then
  restore
  die "nginx -t не прошёл; копии возвращены, reload не делался"
fi
nginx -s reload
log "готово: убрано из загрузки ${#moved[@]}; содержимое сохранено в $STORE/$stamp"
