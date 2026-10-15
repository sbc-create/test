#!/usr/bin/env bash
# Приёмка витрины НА УЗЛЕ: поверхности, ошибки, канонический адрес, плеер.
#
# Зачем на узле. Пока записи DNS указывают на прежний сервер, снаружи витрину
# проверить нечем: имя ведёт не сюда. Но сама витрина уже работает, и всё,
# кроме внешнего имени и сертификата, проверяется здесь — запросами к nginx с
# нужным `Host`.
#
# Что проверяется:
#   * поверхности: главная, каталог, поиск, карточка — код и размер;
#   * честные ошибки: несуществующий путь обязан отвечать 404, а не 200;
#   * канонический адрес главной и `X-Robots-Tag` (режим индексации);
#   * `robots.txt` и `sitemap.xml`: код и первая строка;
#   * номер издателя в разметке карточки — сверяется с установленным
#     `config/player.json`, а не печатается;
#   * ЗАПРОС К ПОСТАВЩИКУ: плейлист по тому же номеру и внешнему
#     идентификатору из установленных данных — ответ 200 с нулём элементов за
#     успех не считается.
#
# Чего здесь нет: браузера, а значит и воспроизведения. Воспроизведение
# проверяется там, где есть браузер (`automation/local/stand-player-check.py`
# на стенде, `publisher-id-check.py` на публичном адресе после перевода DNS).
#
# Имена переменных только ASCII: кириллица в именах переменных оболочки падает
# в работе, а `bash -n` её пропускает.
#
# Запуск на узле:  k2-accept-site.sh <site_id>
set -uo pipefail

site="${1:?нужен site_id}"
manifest="/home/k2deploy/stage/MANIFEST.json"
[ -f "$manifest" ] || { echo "error=нет $manifest"; exit 2; }

read -r account domain <<EOF
$(python3 - "$manifest" "$site" <<'PY'
import json, sys
опись = json.load(open(sys.argv[1], encoding="utf-8"))
ячейка = (опись.get("cells") or {}).get(sys.argv[2])
if not ячейка:
    raise SystemExit(f"в описи нет {sys.argv[2]}")
print(ячейка["account"], ячейка["domain"])
PY
)
EOF
[ -n "${domain:-}" ] || { echo "error=в описи нет домена для $site"; exit 2; }
echo "site=$site"
echo "domain=$domain"

ask() {  # путь -> код и размер
  local path="$1"
  local code size
  code=$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $domain" --max-time 30 "http://127.0.0.1$path")
  size=$(curl -s -o /dev/null -w '%{size_download}' -H "Host: $domain" --max-time 30 "http://127.0.0.1$path")
  echo "$code $size"
}

body() {
  curl -s -H "Host: $domain" --max-time 30 "http://127.0.0.1$1"
}

home_html="$(body /)"
echo "route_home=$(ask /)"
echo "route_catalog=$(ask /catalog/)"
echo "route_search=$(ask '/search/?q=%D0%B2%D0%B5%D1%82%D0%B5%D1%80')"
echo "route_missing=$(ask /takogo-tochno-net-12345/)"
echo "route_robots=$(ask /robots.txt)"
echo "route_sitemap=$(ask /sitemap.xml)"

canonical=$(printf '%s' "$home_html" | grep -o '<link[^>]*rel="canonical"[^>]*>' | head -1 \
            | grep -o 'href="[^"]*"' | cut -d'"' -f2)
echo "canonical_home=${canonical:-нет}"
echo "robots_header=$(curl -s -D - -o /dev/null -H "Host: $domain" --max-time 20 http://127.0.0.1/ \
                      | grep -i '^x-robots-tag' | tr -d '\r' | head -1)"
echo "robots_txt_first=$(body /robots.txt | head -1 | tr -d '\r')"

# Карточка: первый слуг из установленного каталога витрины.
catalog="/srv/$account/data/$site-catalog.json"
slug=""
if [ -r "$catalog" ]; then
  slug=$(python3 - "$catalog" <<'PY'
import json, sys
данные = json.load(open(sys.argv[1], encoding="utf-8"))
первый = (данные.get("items") or [{}])[0]
print(первый.get("slug") or "")
PY
)
fi
echo "catalog_readable=$([ -r "$catalog" ] && echo да || echo нет)"
if [ -n "$slug" ]; then
  echo "route_title=$(ask "/title/$slug/")"
  title_html="$(body "/title/$slug/")"
  assigned=""
  player="/srv/$account/current/config/player.json"
  [ -r "$player" ] || player="/srv/$account/releases/current/config/player.json"
  if [ -r "$player" ]; then
    assigned=$(python3 -c "
import json,sys
print(json.load(open('$player',encoding='utf-8')).get('publisher_id',''))
" 2>/dev/null)
  fi
  echo "player_config_readable=$([ -n "$assigned" ] && echo да || echo нет)"
  if [ -n "$assigned" ]; then
    echo "publisher_in_markup_matches=$(printf '%s' "$title_html" | grep -c "data-publisher-id=\"$assigned\"")"
  else
    # Конфигурация витрины принадлежит ей и может быть недоступна для чтения —
    # тогда сверяем разметку с учётом партии, который лежит в описи витрины.
    expected=$(python3 - "/srv/$account/current/config/site.json" <<'PY'
import json, sys
try:
    print(json.load(open(sys.argv[1], encoding="utf-8")).get("publisher_id_expected") or "")
except Exception:
    print("")
PY
)
    echo "publisher_expected_readable=$([ -n "$expected" ] && echo да || echo нет)"
    [ -n "$expected" ] && echo "publisher_in_markup_matches=$(printf '%s' "$title_html" | grep -c "data-publisher-id=\"$expected\"")"
    assigned="$expected"
  fi
  # Запрос к поставщику: тем же номером и внешним идентификатором карточки.
  if [ -n "$assigned" ] && [ -r "/srv/$account/data/$site-details.json" ]; then
    read -r aggr extid <<EOF
$(python3 - "/srv/$account/data/$site-details.json" "$slug" <<'PY'
import json, sys
детали = json.load(open(sys.argv[1], encoding="utf-8")).get("details") or {}
запись = детали.get(sys.argv[2]) or {}
внешние = запись.get("external_ids") or {}
for агрегатор in ("kp", "imdb", "mdl", "mali"):
    значение = str(внешние.get(агрегатор) or "").strip()
    if значение:
        print(агрегатор, значение)
        break
else:
    print("нет нет")
PY
)
EOF
    if [ "$aggr" != "нет" ]; then
      items=$(curl -s --max-time 30 \
        -H "Origin: https://$domain" -H "Referer: https://$domain/" \
        "https://plapi.cdnvideohub.com/api/v1/player/sv/playlist?pub=$assigned&id=$extid&aggr=$aggr" \
        | python3 -c "
import json,sys
try:
    loaded=json.load(sys.stdin)
except Exception:
    print('parse_error'); raise SystemExit
items_list=loaded.get('items') or []
has_stream=bool(items_list and (items_list[0].get('cvhId') or items_list[0].get('vkId')))
print(f\"{len(items_list)} {'stream' if has_stream else 'no_stream'}\")
")
      echo "provider_playlist=$items (aggr=$aggr)"
    else
      echo "provider_playlist=нет внешнего идентификатора у первой карточки"
    fi
  fi
else
  echo "route_title=каталог недоступен для чтения — слуг не взят"
fi

echo "service=$(systemctl is-active "nova-${account}.service" 2>&1)"
echo "mem_available_mib=$(awk '/^MemAvailable:/{print int($2/1024)}' /proc/meminfo)"
