#!/usr/bin/env bash
# Активация витрины zona-02 (zonafilm.cc). Единственная команда владельца.
#
# Всё, что требует root, собрано здесь и выполняется по порядку с проверкой
# после каждого шага. Список шагов из пяти команд заменён одной не ради
# удобства: пять команд, введённых вручную, расходятся с проверенной
# последовательностью на первом же отклонении, и разошедшееся состояние потом
# некому описать.
#
# Свойства, за которые этот скрипт отвечает:
#
#   * --preflight ничего не меняет и проверяет всё, что можно проверить без
#     изменений. «Команда не запустилась» обязано выясняться до того, как
#     что-то тронуто;
#   * каждый шаг проверяется по наблюдаемому признаку, а не по коду возврата:
#     `systemctl enable` возвращает 0 и при витрине, которая не поднялась;
#   * неудача откатывает ровно то, что этот запуск успел сделать, и не трогает
#     того, чего не делал;
#   * соседние витрины не перезапускаются ни при каком исходе.
#
# Чего скрипт НЕ делает намеренно:
#
#   * не создаёт записи DNS — зоны нет в inventory/dns-zones.yaml, учётных
#     данных Cloudflare у стенда нет; запись создаёт владелец в панели;
#   * не открывает индексацию — она закрыта на двух уровнях, и открытие
#     отдельное решение после визуальной приёмки;
#   * не трогает счётчики, проекты Topvisor и общие службы комментариев.
#
# Использование:
#     sudo bash automation/host/zonafilm-cc-activate.sh --preflight
#     sudo bash automation/host/zonafilm-cc-activate.sh --apply

set -euo pipefail

SITE_ID="zona-02"
DOMAIN="zonafilm.cc"
WWW="www.zonafilm.cc"
PORT=9123
UNIT="nova-zona-02.service"
SITE_ROOT="/srv/lords/.frontend/sites/zona-02"
ORIGIN_IPV4="45.131.182.225"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
UNIT_SRC="$SITE_ROOT/current/deploy/systemd/$UNIT"
VHOST_SRC="$SITE_ROOT/current/deploy/nginx/$SITE_ID.conf"
UNIT_DST="/etc/systemd/system/$UNIT"
VHOST_DST="/etc/nginx/lords/$SITE_ID.conf"
# Максимум ожидания старта. Витрина читает снимок каталога 16 МиБ и боковой
# файл подробностей 73 МиБ; измерено на этом стенде — от 105 до 290 с.
START_TIMEOUT="${START_TIMEOUT:-420}"

MODE="${1:---preflight}"
DID_INSTALL_UNIT=0
DID_ENABLE_UNIT=0
DID_INSTALL_VHOST=0

say()  { printf '%-40s %s\n' "$1" "${2:-}"; }
fail() { echo "ОТКАЗ: $*" >&2; exit 1; }

rollback() {
  local code=$?
  [ "$code" -eq 0 ] && return 0
  # Откатывать нечего — и говорить об откате нечего. Сообщение об откате там,
  # где ничего не менялось, читается как «что-то произошло», и в следующий раз
  # его ищут в системе.
  if [ "$DID_INSTALL_UNIT" = 0 ] && [ "$DID_ENABLE_UNIT" = 0 ] \
     && [ "$DID_INSTALL_VHOST" = 0 ]; then
    exit "$code"
  fi
  echo >&2
  echo "Шаг не прошёл (код $code). Откат того, что успел сделать этот запуск." >&2
  if [ "$DID_INSTALL_VHOST" = 1 ]; then
    rm -f "$VHOST_DST"
    nginx -t >/dev/null 2>&1 && systemctl reload nginx || true
    echo "  снят vhost $VHOST_DST" >&2
  fi
  if [ "$DID_ENABLE_UNIT" = 1 ]; then
    systemctl stop "$UNIT" || true
    systemctl disable "$UNIT" || true
    echo "  остановлен и выключен $UNIT" >&2
  fi
  if [ "$DID_INSTALL_UNIT" = 1 ]; then
    rm -f "$UNIT_DST"
    systemctl daemon-reload || true
    echo "  снят юнит $UNIT_DST" >&2
  fi
  echo >&2
  echo "Остановка службы и снятие vhost — обязательная часть отката, а не" >&2
  echo "рекомендация: на освободившемся порту общий загрузчик уходит в" >&2
  echo "releases/legacy/current, и домен отдавал бы чужую легаси-витрину." >&2
  exit "$code"
}
trap rollback EXIT

[ "$(id -u)" -eq 0 ] || fail "нужен root: скрипт ставит юнит и vhost"

echo "== Проверки до изменений =="

[ -L "$SITE_ROOT/current" ] || fail "$SITE_ROOT/current не ссылка на релиз: выкладка не выполнена"
RELEASE="$(readlink -f "$SITE_ROOT/current")"
say "релиз" "$RELEASE"

[ -f "$UNIT_SRC" ]  || fail "в релизе нет юнита: $UNIT_SRC"
[ -f "$VHOST_SRC" ] || fail "в релизе нет vhost: $VHOST_SRC"
say "юнит и vhost в релизе" "есть"

# Порт обязан принадлежать этой витрине и никому больше.
REG=/srv/lords/.frontend/lords-runtime-registry.json
REG_PORT=$(python3 -c "import json;print((json.load(open('$REG'))['sites'].get('$SITE_ID') or {}).get('port'))")
[ "$REG_PORT" = "$PORT" ] || fail "реестр рантайма называет порт $REG_PORT, а скрипт $PORT"
CLASH=$(python3 -c "
import json
d=json.load(open('$REG'))['sites']
print(','.join(k for k,v in d.items() if k!='$SITE_ID' and v.get('port')==$PORT))")
[ -z "$CLASH" ] || fail "порт $PORT закреплён также за: $CLASH"
say "порт $PORT в реестре" "принадлежит $SITE_ID"

# Данные обязаны быть на месте: без снимка витрина поднимется пустой.
for f in "$SITE_ROOT/data/$SITE_ID-catalog.json" "$SITE_ROOT/data/player-$SITE_ID.json"; do
  [ -f "$f" ] || fail "нет обязательного файла данных: $f"
done
say "данные витрины" "на месте"

# Запись DNS. Её отсутствие не мешает поднять службу, но мешает выпустить
# сертификат по HTTP-01 и сделать публичную приёмку — поэтому названо явно.
DNS_OK=0
if RESOLVED=$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk '{print $1}' | sort -u | tr '\n' ' '); then
  if [ -n "$RESOLVED" ]; then
    case " $RESOLVED " in
      *" $ORIGIN_IPV4 "*) DNS_OK=1; say "DNS $DOMAIN" "$RESOLVED (совпадает с origin)" ;;
      *) say "DNS $DOMAIN" "$RESOLVED — НЕ origin $ORIGIN_IPV4" ;;
    esac
  fi
fi
[ "$DNS_OK" = 1 ] || say "DNS $DOMAIN" "записи A нет — создайте её в панели Cloudflare (DNS only)"

CERT="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
[ -f "$CERT" ] && say "сертификат" "есть" || say "сертификат" "нет"

if [ "$MODE" = "--preflight" ]; then
  echo
  echo "Проверка завершена. Ничего не изменено."
  echo "Запуск: sudo bash ${BASH_SOURCE[0]} --apply"
  trap - EXIT
  exit 0
fi

[ "$MODE" = "--apply" ] || fail "неизвестный режим $MODE (ожидается --preflight или --apply)"

echo
echo "== Шаг 1. Юнит витрины =="

# Собственный проверочный процесс сессии, если он ещё жив, обязан уйти:
# иначе юнит не получит порт. Ищется ровно процесс этой витрины.
PIDS=$(pgrep -f "sites/$SITE_ID/releases/.*lords-frontend.py --port $PORT" || true)
if [ -n "$PIDS" ]; then
  say "проверочный процесс сессии" "останавливается: $PIDS"
  kill $PIDS || true
  for _ in $(seq 1 40); do sleep 0.5; pgrep -f "sites/$SITE_ID/releases/.*--port $PORT" >/dev/null || break; done
fi

install -m 0644 -o root -g root "$UNIT_SRC" "$UNIT_DST"
DID_INSTALL_UNIT=1
systemctl daemon-reload
systemctl enable --now "$UNIT"
DID_ENABLE_UNIT=1
say "юнит" "установлен и запущен"

echo "Ожидание готовности (до ${START_TIMEOUT} с; старт читает 89 МиБ данных)…"
READY=0
for _ in $(seq 1 "$START_TIMEOUT"); do
  if [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:$PORT/healthz" || true)" = "200" ]; then
    READY=1; break
  fi
  sleep 1
done
[ "$READY" = 1 ] || fail "витрина не ответила 200 на /healthz за ${START_TIMEOUT} с"
say "healthz" "200"

# Код возврата systemctl не говорит, КАКОЙ релиз поднялся. Говорит заголовок.
BUILD=$(curl -s -D- -o /dev/null --max-time 10 "http://127.0.0.1:$PORT/" | awk -F': ' '/X-Site-Factory-Build-Id/{print $2}' | tr -d '\r')
EXPECT=$(python3 -c "import json;print(json.load(open('$RELEASE/template-manifest.json'))['build_id'])")
[ "$BUILD" = "$EXPECT" ] || fail "витрина отдаёт build-id '$BUILD', а релиз объявляет '$EXPECT'"
say "X-Site-Factory-Build-Id" "$BUILD"

echo
echo "== Шаг 2. Сертификат =="
if [ -f "$CERT" ]; then
  say "сертификат" "уже есть, выпуск пропущен"
elif [ "$DNS_OK" = 1 ]; then
  certbot certonly --webroot -w /var/www/certbot -d "$DOMAIN" -d "$WWW" --non-interactive --agree-tos --register-unsafely-without-email
  [ -f "$CERT" ] || fail "certbot отработал, но $CERT не появился"
  say "сертификат" "выпущен"
else
  fail "записи A нет: HTTP-01 не пройдёт. Создайте A для $DOMAIN и $WWW на $ORIGIN_IPV4 (DNS only) и запустите снова — юнит уже поднят и повторный запуск его не тронет"
fi

echo
echo "== Шаг 3. vhost =="
install -m 0644 -o root -g root "$VHOST_SRC" "$VHOST_DST"
DID_INSTALL_VHOST=1
nginx -t
systemctl reload nginx
say "nginx" "конфигурация принята, перечитана"

echo
echo "== Шаг 4. Публичная приёмка =="
PUB=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://$DOMAIN/" || true)
[ "$PUB" = "200" ] || fail "https://$DOMAIN/ отдал $PUB"
PUB_BUILD=$(curl -s -D- -o /dev/null --max-time 20 "https://$DOMAIN/" | awk -F': ' '/X-Site-Factory-Build-Id/{print $2}' | tr -d '\r')
[ "$PUB_BUILD" = "$EXPECT" ] || fail "публичный адрес отдаёт build-id '$PUB_BUILD', ожидался '$EXPECT' — имя мог поймать сосед"
ROBOTS=$(curl -s -D- -o /dev/null --max-time 20 "https://$DOMAIN/" | awk -F': ' '/X-Robots-Tag/{print $2}' | tr -d '\r')
say "публичный HTTPS" "200, build-id совпал, X-Robots-Tag: $ROBOTS"

echo
echo "Активация выполнена. Полная приёмка по публичному адресу:"
echo "  cd $REPO_ROOT && /srv/site-factory/repo/.venv/bin/python3 \\"
echo "    automation/host/zonafilm-cc-acceptance.py --origin https://$DOMAIN --host $DOMAIN \\"
echo "    --out artifacts/evidence/zona-02-launch-01/03-public/acceptance-public.json"
echo
echo "Откат: sudo bash $REPO_ROOT/automation/host/zonafilm-cc-deactivate.sh"
trap - EXIT
