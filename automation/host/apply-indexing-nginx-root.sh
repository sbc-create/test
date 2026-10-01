#!/usr/bin/env bash
#
# Слой nginx в режиме индексации одного сайта. Запускает ВЛАДЕЛЕЦ.
#
# Почему отдельный запуск от root
# -------------------------------
#
# Режим индексации собирается из четырёх слоёв. Три из них управляет штатная
# операция `python3 -m factory.qwen indexing-set` без root: разрешение
# владельца в реестре ячеек, разрешение выпуска в config/site.json и файл
# состояния в /srv/sites/indexing. Четвёртый слой — строка
#
#     add_header X-Robots-Tag "noindex, nofollow" always;
#
# в серверном блоке сайта. Конфигурация nginx принадлежит root, перезагрузка
# тоже, и ни то ни другое учётной записи claude недоступно. Пока эта строка
# отдаёт noindex, сайт закрыт независимо от режима рантайма — операция это
# измеряет и открытым сайт не называет.
#
# Почему точечная правка, а не перегенерация
# ------------------------------------------
#
# Живые конфигурации разошлись с генератором. В /etc/nginx/lords/
# animedia-02.conf лежат ограничение соединений на адрес, отдельный формат
# журнала со временем ответа, исключение /poster/ из предела и include маркера
# Яндекс.Вебмастера — всё это появилось после генерации и в заготовке
# отсутствует. Полная перегенерация потеряла бы их молча. Поэтому скрипт
# меняет РОВНО одну строку и отказывается работать, если не находит её
# однозначно.
#
# Что происходит в открытом режиме со служебными путями
# -----------------------------------------------------
#
# Они остаются закрытыми. Вместо снятия заголовка его значение переводится на
# переменную `map $uri`, и в открытом режиме пустое значение (nginx тогда
# заголовка не добавляет) выдаётся всем путям, КРОМЕ служебных: маркер
# Яндекс.Вебмастера, /.well-known/, /poster/, /api/, /healthz и /__*. Для них
# остаётся noindex. Снятие заголовка целиком открыло бы и их — в том числе
# маркер подтверждения прав, про который в snippet прямо сказано, что его
# отдача разрешением индексировать сайт не является.
#
# Содержимое включаемого файла пишет ЭТОТ скрипт, а не операция: файл лежит в
# /etc/nginx/cells рядом с .upstream, и каталог принадлежит root. Так же
# устроено переключение маршрута при выкладке.
#
# Что скрипт делает
# -----------------
#
#   1. проверяет сайт по реестру ячеек и находит его конфигурацию;
#   2. сохраняет резервную копию конфигурации с отметкой времени;
#   3. один раз переводит фиксированную строку заголовка на переменную map;
#   4. пишет включаемый файл со значениями для требуемого режима;
#   5. `nginx -t`; при отказе возвращает конфигурацию и НЕ перезагружает;
#   6. перезагружает nginx и проверяет публичные заголовки домена.
#
# Повторный запуск в том же режиме не меняет ни байта конфигурации. Чужих
# сайтов скрипт не касается: правится файл только этого сайта.
#
# Запуск:
#   sudo bash automation/host/apply-indexing-nginx-root.sh --site <site_id> --mode open|closed
#
set -euo pipefail

SITE=""
MODE=""
NGINX_DIR=/etc/nginx
CELLS_DIR="${NGINX_DIR}/cells"
BACKUP_DIR="${NGINX_DIR}/backups"
REGISTRY=""

while [ $# -gt 0 ]; do
  case "$1" in
    --site) SITE="${2:-}"; shift 2 ;;
    --mode) MODE="${2:-}"; shift 2 ;;
    --registry) REGISTRY="${2:-}"; shift 2 ;;
    *) echo "неизвестный аргумент: $1" >&2; exit 2 ;;
  esac
done

if [ "$(id -u)" != "0" ]; then
  echo "нужен root: sudo bash $0 --site <site_id> --mode open|closed" >&2
  exit 1
fi
if [ -z "${SITE}" ] || [ -z "${MODE}" ]; then
  echo "нужны --site <site_id> и --mode open|closed" >&2
  exit 2
fi
case "${MODE}" in
  open|closed) ;;
  *) echo "режим должен быть open или closed, получено: ${MODE}" >&2; exit 2 ;;
esac

REGISTRY="${REGISTRY:-/home/claude/wt-portable-site-cell-01/config/site-cells.json}"
if [ ! -f "${REGISTRY}" ]; then
  echo "ОТКАЗ: реестра ячеек нет: ${REGISTRY}" >&2
  exit 2
fi

# Домен берётся из реестра, а не из аргумента: проверять публичный ответ надо
# у того домена, который этому site_id принадлежит, иначе проверка подтвердит
# чужой сайт.
DOMAIN="$(python3 - "${REGISTRY}" "${SITE}" <<'PY'
import json, sys
путь, site_id = sys.argv[1], sys.argv[2]
данные = json.load(open(путь, encoding="utf-8"))
ячейки = данные.get("cells") or данные.get("sites") or []
ячейки = ячейки if isinstance(ячейки, list) else list(ячейки.values())
for я in ячейки:
    if я.get("site_id") == site_id:
        print(я.get("domain") or "")
        break
PY
)"
if [ -z "${DOMAIN}" ]; then
  echo "ОТКАЗ: ${SITE} нет в реестре ячеек ${REGISTRY}" >&2
  exit 2
fi

CONF=""
for candidate in "${NGINX_DIR}/lords/${SITE}.conf" \
                 "${NGINX_DIR}/sites-available/${DOMAIN}.conf" \
                 "${NGINX_DIR}/sites-enabled/${DOMAIN}.conf"; do
  if [ -f "${candidate}" ]; then CONF="${candidate}"; break; fi
done
if [ -z "${CONF}" ]; then
  echo "ОТКАЗ: конфигурации сайта ${SITE} (${DOMAIN}) не найдено" >&2
  exit 2
fi

# Имя переменной map выводится из site_id: дефис в имени переменной nginx
# недопустим, поэтому он заменяется подчёркиванием.
VAR="cell_robots_$(printf '%s' "${SITE}" | tr '-' '_')"
INCLUDE_FILE="${CELLS_DIR}/${SITE}.robots"
FIXED_LINE='add_header X-Robots-Tag "noindex, nofollow" always;'
VAR_LINE="add_header X-Robots-Tag \$${VAR} always;"

echo "== сайт =="
echo "  site_id:   ${SITE}"
echo "  домен:     ${DOMAIN}"
echo "  конфиг:    ${CONF}"
echo "  включаемый: ${INCLUDE_FILE}"
echo "  режим:     ${MODE}"

mkdir -p "${CELLS_DIR}" "${BACKUP_DIR}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="${BACKUP_DIR}/$(basename "${CONF}").bak.indexing.${STAMP}"
cp -p "${CONF}" "${BACKUP}"
echo "резервная копия: ${BACKUP}"

# --- шаг 1: один раз перевести заголовок на переменную ---------------------
if grep -qF "${VAR_LINE}" "${CONF}"; then
  echo "заголовок уже на переменной — конфигурацию не правлю"
else
  COUNT="$(grep -cF "${FIXED_LINE}" "${CONF}" || true)"
  if [ "${COUNT}" != "1" ]; then
    echo "ОТКАЗ: ожидалась РОВНО одна строка" >&2
    echo "  ${FIXED_LINE}" >&2
    echo "а найдено: ${COUNT}. Править наугад нельзя: в этом файле живут" >&2
    echo "настройки, которых нет в заготовке, и перегенерация их потеряет." >&2
    rm -f "${BACKUP}"
    exit 3
  fi
  # map объявляется в контексте http — то есть на верхнем уровне этого файла,
  # рядом с limit_conn_zone и log_format, которые уже там стоят.
  python3 - "${CONF}" "${VAR}" "${INCLUDE_FILE}" "${FIXED_LINE}" "${VAR_LINE}" <<'PY'
import sys
путь, var, include, фикс, перем = sys.argv[1:6]
текст = open(путь, encoding="utf-8").read()
assert текст.count(фикс) == 1, текст.count(фикс)
блок = (
    "# Значение X-Robots-Tag для этого сайта. Объявлено переменной, а не\n"
    "# строкой: режим индексации меняется операцией, а операция не вправе\n"
    "# править конфигурацию nginx. Содержимое include пишет\n"
    "# automation/host/apply-indexing-nginx-root.sh; здесь только объявление,\n"
    "# как у upstream в site-cells-upstreams.conf.\n"
    "#\n"
    "# Пустое значение nginx не отправляет вовсе — так выглядит открытый\n"
    "# режим. Служебные пути остаются закрытыми перечислением внутри include.\n"
    f"map $uri ${var} {{\n"
    f"    include {include};\n"
    "}\n\n"
)
# Блок ставится перед первым server-блоком файла: до него уже объявлены
# limit_conn_zone и log_format, и порядок директив http-контекста сохранится.
место = текст.index("\nserver {")
текст = текст[:место + 1] + блок + текст[место + 1:]
текст = текст.replace(фикс, перем, 1)
open(путь, "w", encoding="utf-8").write(текст)
print("  конфигурация переведена на переменную map")
PY
fi

# --- шаг 2: содержимое включаемого файла ----------------------------------
NEW_INCLUDE="$(mktemp)"
if [ "${MODE}" = "closed" ]; then
  cat > "${NEW_INCLUDE}" <<'EOF'
# Закрытый режим: запрет на всё. Значение по умолчанию и единственное.
default "noindex, nofollow";
EOF
else
  cat > "${NEW_INCLUDE}" <<'EOF'
# Открытый режим. Пустое значение по умолчанию: nginx заголовка не добавляет,
# и о режиме страницы отвечает приложение.
default "";

# Служебные пути остаются закрытыми. Это НАМЕРЕННЫЕ ограничения, и открытие
# сайта их не затрагивает. Маркер Яндекс.Вебмастера в их числе: в snippet
# webmaster-verification.conf прямо сказано, что его отдача разрешением
# индексировать сайт не является.
"~^/yandex_[0-9a-f]{8,64}\.html$"   "noindex, nofollow";
"~^/\.well-known/"                  "noindex, nofollow";
"~^/poster/"                        "noindex, nofollow";
"~^/api/"                           "noindex, nofollow";
"~^/healthz$"                       "noindex, nofollow";
"~^/__"                             "noindex, nofollow";
EOF
fi

if [ -f "${INCLUDE_FILE}" ] && cmp -s "${NEW_INCLUDE}" "${INCLUDE_FILE}"; then
  echo "включаемый файл уже в режиме ${MODE} — не меняю"
  rm -f "${NEW_INCLUDE}"
else
  PREV=""
  if [ -f "${INCLUDE_FILE}" ]; then
    PREV="${BACKUP_DIR}/${SITE}.robots.bak.${STAMP}"
    cp -p "${INCLUDE_FILE}" "${PREV}"
    echo "прежний включаемый файл: ${PREV}"
  fi
  install -m 0644 -o root -g root "${NEW_INCLUDE}" "${INCLUDE_FILE}"
  rm -f "${NEW_INCLUDE}"
  echo "включаемый файл записан: ${INCLUDE_FILE}"
fi

# --- шаг 3: проверка и перезагрузка ---------------------------------------
if ! nginx -t 2>/tmp/nginx-indexing-test.$$; then
  echo "ОТКАЗ: nginx -t не прошёл — возвращаю конфигурацию и НЕ перезагружаю" >&2
  sed -n '1,20p' /tmp/nginx-indexing-test.$$ >&2
  cp -p "${BACKUP}" "${CONF}"
  rm -f /tmp/nginx-indexing-test.$$
  exit 4
fi
rm -f /tmp/nginx-indexing-test.$$
nginx -s reload
echo "nginx перезагружен"

# --- шаг 4: публичная проверка -------------------------------------------
echo "== публичные заголовки ${DOMAIN} =="
sleep 2
HEADERS="$(curl -s -D - -o /dev/null --max-time 20 "https://${DOMAIN}/" || true)"
printf '%s\n' "${HEADERS}" | grep -i "x-robots-tag" || echo "  X-Robots-Tag: заголовка нет"
COUNT_DENY="$(printf '%s\n' "${HEADERS}" | grep -ci "x-robots-tag: *noindex" || true)"
if [ "${MODE}" = "open" ] && [ "${COUNT_DENY}" != "0" ]; then
  echo "ВНИМАНИЕ: домен всё ещё отдаёт noindex в ${COUNT_DENY} заголовке(ах)." >&2
  echo "Слой nginx снят, но запрет может приходить от приложения: проверьте" >&2
  echo "  python3 -m factory.qwen indexing-state --site ${DOMAIN}" >&2
fi

cat <<NEXT

Готово для слоя nginx. Итог режима считает штатная операция по публичному
ответу, а не этот скрипт:

  cd /home/claude/wt-portable-site-cell-01
  python3 -m factory.qwen indexing-state --site ${DOMAIN}

Возврат к закрытому режиму — тот же скрипт с --mode closed. Резервные копии
остаются в ${BACKUP_DIR}.
NEXT
