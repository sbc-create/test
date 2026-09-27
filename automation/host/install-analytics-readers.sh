#!/usr/bin/env bash
# Две службы ЧТЕНИЯ статистики. Одна команда владельца, ничего не меняет наружу.
#
#   sudo bash automation/host/install-analytics-readers.sh [--dry-run]
#
# Что ставится и зачем
# --------------------
#
#   analytics-cabinet.service/.timer   ЧТЕНИЕ статистики Метрики по всем доменам
#   topvisor-check.service             ЧТЕНИЕ: доступ, проекты и план Topvisor
#   analytics-connect@<домен>.service  ЗАПИСЬ: найти или создать счётчик домена
#   topvisor-connect.service           ЗАПИСЬ: создать недостающие проекты
#
# Чтение и запись разведены намеренно. Название «readers» ничего не обещает про
# право создавать счётчики: в Метрике это разные разрешения токена
# (metrika:read и metrika:write), и юнит, делающий и то и другое, скрывал бы,
# какого именно права не хватило. Установка средства чтения готовности
# подключения не доказывает.
#
# Обе службы получают секрет через LoadCredential: значение живёт в
# /run/credentials/<юнит> только на время прогона, а каталог
# /etc/site-factory/secrets остаётся закрытым для учётной записи claude. Это и
# есть безопасный способ подключить доступ: сессии агента секрет не выдаётся
# вовсе, ей достаточно отчёта.
#
# Почему не «добавить claude в группу ubuntu». Членство в группе даёт доступ к
# секрету всему, что работает от этой учётной записи, и навсегда. Здесь доступ
# ограничен одним юнитом и одним прогоном.
#
# Почему не существующий site-factory-analytics-collect. Он читает реестр из
# /srv/site-factory/repo, где объявлено шесть доменов вместо шестнадцати, и он
# не включён: в timers.target.wants его нет, artifacts/analytics не создан —
# сбор не выполнялся ни разу. Его не трогаем: это чужая ветка.
#
# Ни одна мутация Topvisor здесь не выполняется: только check и plan.
set -Eeuo pipefail

dry_run=0
[ "${1:-}" = "--dry-run" ] && dry_run=1

SRC_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
UNIT_DIR=/etc/systemd/system
SECRETS=/etc/site-factory/secrets

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
die() { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }
run() { if [ "$dry_run" = 1 ]; then printf '   [сухой прогон] %s\n' "$*"; else "$@"; fi; }

[ "$dry_run" = 1 ] || [ "$(id -u)" = 0 ] || die "нужен root"

# Секреты обязаны существовать ДО установки: юнит со ссылкой на отсутствующий
# LoadCredential не запустится, и причина будет выглядеть как ошибка юнита.
log "проверка секретов"
# «Нет файла» и «не могу проверить» — разные исходы, и путать их нельзя.
# Каталог /etc/site-factory/secrets закрыт для обычной учётной записи, поэтому
# в сухом прогоне без root проверка честно говорит, что не видит, а не
# объявляет секреты отсутствующими. Первая версия объявляла — и сухой прогон
# останавливался на исправном хосте.
can_see=1
[ "$(id -u)" = 0 ] || can_see=0
for secret in "$SECRETS/yandex_oauth_token" "$SECRETS/topvisor/user-id" "$SECRETS/topvisor/api-key"; do
  if [ -e "$secret" ]; then
    printf '   есть: %s\n' "$secret"
  elif [ "$can_see" = 0 ]; then
    printf '   не могу проверить без root: %s\n' "$secret"
  else
    printf '   \033[31mНЕТ\033[0m: %s\n' "$secret"
    missing=1
  fi
done
if [ "${missing:-0}" = 1 ]; then
  cat >&2 <<'NOSECRET'
[x] не все учётные данные на месте.

    OAuth Метрики:  /etc/site-factory/secrets/yandex_oauth_token
    Topvisor:       /etc/site-factory/secrets/topvisor/{user-id,api-key}
                    ввод скрытый: sudo python3 -m factory.topvisor.enroll

    Установка остановлена: юнит со ссылкой на отсутствующий LoadCredential
    не запускается, и причина выглядела бы как ошибка юнита.
NOSECRET
  exit 3
fi

log "установка юнитов"
for unit in analytics-cabinet.service analytics-cabinet.timer topvisor-check.service \
            'analytics-connect@.service' topvisor-connect.service; do
  run install -m 0644 "$SRC_ROOT/automation/host/$unit" "$UNIT_DIR/$unit"
done

if [ "$dry_run" = 1 ]; then
  echo "   [сухой прогон] systemctl daemon-reload"
  echo "   [сухой прогон] systemctl enable --now analytics-cabinet.timer"
  echo "   [сухой прогон] systemctl start analytics-cabinet.service topvisor-check.service"
  echo
  echo "сухой прогон завершён: ничего не менялось"
  exit 0
fi

systemctl daemon-reload
systemctl enable --now analytics-cabinet.timer
# Первый прогон сразу, а не в следующие 06:10: иначе результат придётся ждать
# сутки, а ради него всё это и ставится.
systemctl start analytics-cabinet.service || log "[!] сбор Метрики завершился с ошибкой — смотри отчёт"
systemctl start topvisor-check.service   || log "[!] проверка Topvisor завершилась с ошибкой — смотри отчёт"

cat <<'TAIL'

   Отчёты появятся здесь (читаются без root):

     var/analytics/cabinet-latest.json    статистика Метрики по домену
     var/topvisor/check-latest.txt        профиль, баланс, проекты Topvisor
     var/topvisor/plan-latest.json        план: чего не хватает проектам

   Мутаций Topvisor при установке не выполнялось: запущены только check и plan.

   Подключение аналитики домена — отдельными вызовами, по одному на домен.
   Список доменов без счётчика печатается ниже из реестра аналитики: прежде
   здесь стоял один пример, и какие ещё домены ждут подключения, приходилось
   выяснять отдельно.

   Первый ищет счётчик по домену и переиспользует найденный; при двух
   счётчиках на домен останавливается со статусом ambiguous. Второй создаёт
   недостающие проекты по манифесту; платные операции не выполняет.

   Отчёты: var/analytics/connect-<домен>.json и var/topvisor/connect-latest.txt
TAIL

python3 - "$SRC_ROOT" <<'LIST'
import json, sys
from pathlib import Path
путь = Path(sys.argv[1]) / "config" / "analytics.json"
записи = json.loads(путь.read_text(encoding="utf-8"))["properties"]
ждут = [з["domain"] for з in записи if not з.get("counter_id")
        and not str(з["domain"]).endswith((".localhost", ".test", ".local"))]
for домен in ждут:
    print(f"     sudo systemctl start 'analytics-connect@{домен}.service'")
print()
print(f"   Домены без счётчика: {len(ждут)}. Это ПЕРЕЧЕНЬ, а не порядок действий:")
print("   счётчик, заведённый до запуска сайта, собирает пустоту, выглядит рабочим")
print("   и мешает заметить настоящий. Запускать по домену, который выпускается")
print("   сейчас. Домен, у которого счётчик уже есть, в перечне не появляется, и")
print("   повторный вызов дубля не создаёт: счётчик ищется по домену.")
print()
print("   Проекты Topvisor — одной командой на все домены манифеста")
print("   (существующие переиспользуются, платные операции не выполняются):")
print()
print("     sudo systemctl start topvisor-connect.service")
LIST
