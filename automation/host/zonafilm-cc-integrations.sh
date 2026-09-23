#!/usr/bin/env bash
# Подключение Метрики и Topvisor для zonafilm.cc. Запускается под учётной
# записью, которой владелец выдал доступ к секретам.
#
# Почему отдельно от активации витрины. Выкат сайта и заведение внешних
# объектов — разные решения с разными последствиями: витрину можно откатить
# за секунды, а созданный в чужом сервисе проект откатывается только руками
# владельца. Смешивать их в одной команде значит делать второе побочным
# эффектом первого.
#
# Платные операции здесь не выполняются ни при каком флаге. Topvisor только
# планируется: создание проекта расходует баланс, а съём позиций и
# технический аудит — тем более. План печатается, решение принимает владелец.
#
# Дублей не будет. Метрика: провайдер сначала ищет счётчик этого домена и
# переиспользует найденный, а при двух счётчиках на домен останавливается
# вместо выбора. Topvisor: планировщик сверяет список проектов аккаунта по
# домену и, если хоть одну запись не удалось прочитать, отключает создание
# целиком — «не знаю, что это за проект» не то же самое, что «такого нет».
#
# Использование:
#     sudo -u <учётная-запись> bash zonafilm-cc-integrations.sh --preflight
#     sudo -u <учётная-запись> bash zonafilm-cc-integrations.sh --metrika-apply

set -euo pipefail

DOMAIN="zonafilm.cc"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="${PY:-/srv/site-factory/repo/.venv/bin/python3}"
MODE="${1:---preflight}"

# Без выравнивания по ширине: printf считает БАЙТЫ, а не символы, и
# кириллические подписи разъезжаются тем сильнее, чем они длиннее.
say()  { printf '  %s: %s\n' "$1" "${2:-}"; }
fail() { echo "ОТКАЗ: $*" >&2; exit 1; }

[ -x "$PY" ] || fail "нет интерпретатора $PY"
cd "$REPO_ROOT"

echo "== Доступ =="
if "$PY" -m factory analytics probe >/dev/null 2>&1; then
  say "токен Яндекса" "читается"
  METRIKA_OK=1
else
  say "токен Яндекса" "НЕ читается — запустите от учётной записи с доступом"
  METRIKA_OK=0
fi

if "$PY" -c 'import sys; sys.path.insert(0, "."); from factory.topvisor.credentials import load; load()' >/dev/null 2>&1; then
  say "учётные данные Topvisor" "читаются"
  TOPVISOR_OK=1
else
  say "учётные данные Topvisor" "НЕ читаются — нужна группа каталога секретов"
  TOPVISOR_OK=0
fi

echo
echo "== Метрика: что уже есть =="
if [ "$METRIKA_OK" = 1 ]; then
  # План ничего не пишет. Он и показывает, будет ли счётчик создан или
  # переиспользован — то самое, ради чего сначала смотрят, а потом делают.
  "$PY" -m factory analytics plan --domain "$DOMAIN"
else
  say "план" "пропущен: нет доступа к токену"
fi

echo
echo "== Topvisor: что уже есть =="
if [ "$TOPVISOR_OK" = 1 ]; then
  "$PY" -m factory.topvisor.cli check || true
  echo
  "$PY" -m factory.topvisor.cli plan || true
else
  say "проверка и план" "пропущены: нет доступа к учётным данным"
fi

if [ "$MODE" = "--preflight" ]; then
  echo
  echo "Проверка завершена. Ничего не создано."
  echo "Создать счётчик Метрики: $0 --metrika-apply"
  echo "Проект Topvisor создаётся отдельно и вручную: операция платная."
  exit 0
fi

[ "$MODE" = "--metrika-apply" ] || fail "неизвестный режим $MODE"
[ "$METRIKA_OK" = 1 ] || fail "нет доступа к токену Метрики: создавать нечем"

echo
echo "== Метрика: создание или переиспользование счётчика =="
"$PY" -m factory analytics apply --domain "$DOMAIN" --confirm-writes
echo
"$PY" -m factory analytics status --domain "$DOMAIN"

echo
echo "Счётчик записан в config/analytics.json. Чтобы витрина начала его"
echo "отдавать, впишите номер в config/runtime.json проекта сайта"
echo "(поле metrika_counter), выпустите релиз и поставьте его:"
echo
echo "  cd <проект сайта> && python3 build/build.py --output var/release"
echo "  SITE_ROOT=/srv/lords/.frontend/sites/zona-02 ./deploy/install.sh var/release/*.tar.gz"
echo "  systemctl restart nova-zona-02.service"
echo
echo "Пока номер не вписан, витрина не отдаёт тег вовсе — ни скрипта, ни"
echo "noscript-пикселя. Это намеренно: молчащий тег неотличим от рабочего."
