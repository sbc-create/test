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

echo "==> запускаю lords-canary@${SITE}.service"
# Без --wait команда вернулась бы сразу, и отказ ворот выглядел бы как успех.
systemctl start --wait "lords-canary@${SITE}.service" || {
  echo "операция завершилась с ошибкой; журнал:" >&2
  journalctl -u "lords-canary@${SITE}.service" -n 40 --no-pager >&2 || true
  exit 1
}

echo "==> журнал операции"
journalctl -u "lords-canary@${SITE}.service" -n 40 --no-pager || true
