#!/usr/bin/env bash
# Единственное привилегированное действие для canary одной витрины Lords.
#
# Ставит oneshot-юнит с той же привязкой учётных данных, что у штатного
# обновления содержимого, и запускает его один раз для названной витрины.
# Постоянной службы с правами на выкладку после этого не остаётся: юнит
# oneshot, RemainAfterExit=no.
#
# Запуск:
#   sudo bash automation/host/lords-canary-install-and-run.sh lords-02
#
# Что изменится:
#   * появится /etc/systemd/system/lords-canary@.service;
#   * витрина lords-02 получит релиз, собранный на живом каталоге и
#     закреплённом артефакте TEMPLATE_TO_CORE-008;
#   * таймер lords-content-refresh.timer будет остановлен на время наблюдения.
#
# Что НЕ изменится: nginx, TLS, соседние витрины, Yummy, провайдер плеера,
# robots и индексируемость, наблюдатель.
#
# Откат печатается сценарием и записывается в журнал операции.
set -Eeuo pipefail

SITE="${1:-lords-02}"
SRC="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
UNIT="lords-canary@.service"

[ "$(id -u)" = "0" ] || { echo "нужны права root: запустите через sudo" >&2; exit 2; }

echo "==> ставлю ${UNIT}"
install -m 0644 "${SRC}/systemd/${UNIT}" "/etc/systemd/system/${UNIT}"
systemctl daemon-reload

STEPS="/var/log/site-factory/lords-canary-${SITE}.steps.log"

echo "==> запускаю lords-canary@${SITE}.service"
# Без --wait намеренно. Полная пересборка витрины — это рендер пятидесяти трёх
# тысяч страниц; держать сессию всё это время незачем, а оборванная сессия
# убила бы операцию. Ход виден в пошаговом журнале, итог — в журнале операции.
systemctl start --no-block "lords-canary@${SITE}.service"

echo
echo "Операция запущена в фоне. Следить за ходом:"
echo "    tail -f ${STEPS}"
echo
echo "Итог появится здесь (журнал операции с отпечатками и командой отката):"
echo "    /var/log/site-factory/lords-canary-${SITE}-<release>.json"
echo
echo "Остановить и вернуть всё как было:"
echo "    systemctl stop lords-canary@${SITE}.service"
echo "    systemctl start lords-content-refresh.timer"
echo
sleep 5
echo "==> первые шаги"
tail -n 12 "${STEPS}" 2>/dev/null || echo "(журнал ещё не создан)"
