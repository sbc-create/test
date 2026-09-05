#!/usr/bin/env bash
# Единственное привилегированное действие: переключить ОДНУ витрину lords-02.
#
# Рендер уже выполнен непривилегированно и оставил расписку. Этот сценарий
# ставит два oneshot-юнита из ТЕКУЩЕГО рабочего дерева и запускает фазу
# переключения. Постоянной службы с правами на выкладку не остаётся.
#
#   sudo bash /home/claude/wt-release-03/automation/host/lords-canary-switch-now.sh
#
# ## Что изменится
#
#   * витрина lords-02 (lordserial33.biz) получит релиз, собранный на живом
#     каталоге и закреплённом артефакте версии 2;
#   * на время переключения и наблюдения остановится
#     lords-content-refresh.timer — он общий для трёх витрин и возвращается
#     обработчиком выхода на ЛЮБОМ пути завершения.
#
# ## Что НЕ изменится
#
#   nginx, TLS, соседние витрины lords-01 и lords-03, Yummy, провайдер плеера,
#   robots и индексируемость, наблюдатель, DNS.
#
# ## Откат
#
#   Печатается в конце и записывается в журнал операции. Каталог предыдущего
#   релиза не удаляется.
set -Eeuo pipefail

SITE="lords-02"
SRC="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "${SRC}/../.." && pwd)"
RECEIPT="${REPO}/var/canary-staging/${SITE}.render.json"
EXPECT_DIGEST="7b38ca10685a75c3d52527746208539cc30015fc1bfb3fce010a9491616ed965"

[ "$(id -u)" = "0" ] || { echo "нужны права root: запустите через sudo" >&2; exit 2; }

# Предусловия проверяются ДО установки юнитов: ставить оснастку ради операции,
# которая заведомо откажет, значит менять систему впустую.
[ -f "${RECEIPT}" ] || {
  echo "ОТКАЗ: нет расписки о сборке ${RECEIPT}" >&2
  echo "       фаза render не завершена — переключать нечего" >&2
  exit 3
}
RECEIPT_DIGEST="$(python3 -c '
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["template_digest"])' "${RECEIPT}")"
[ "${RECEIPT_DIGEST}" = "${EXPECT_DIGEST}" ] || {
  echo "ОТКАЗ: расписка собрана на отпечатке ${RECEIPT_DIGEST:0:16}," >&2
  echo "       а сценарий закрепляет ${EXPECT_DIGEST:0:16}" >&2
  exit 4
}
echo "==> расписка о сборке принята: отпечаток ${RECEIPT_DIGEST:0:16}"

echo "==> ставлю юниты из ${SRC}/systemd"
for unit in lords-canary-render@.service lords-canary-switch@.service; do
  install -m 0644 "${SRC}/systemd/${unit}" "/etc/systemd/system/${unit}"
  echo "    ${unit}"
done
systemctl daemon-reload

echo "==> переключаю ${SITE}"
# --wait намеренно: фаза короткая, и владелец должен увидеть исход, а не
# получить приглашение оболочки раньше результата.
systemctl start --wait "lords-canary-switch@${SITE}.service" || true

echo
echo "==> исход"
systemctl show -p Result --value "lords-canary-switch@${SITE}.service" || true
echo "журнал операции: /var/log/site-factory/lords-canary-${SITE}.steps.log"
tail -n 12 "/var/log/site-factory/lords-canary-${SITE}.steps.log" 2>/dev/null || true
echo
echo "состояние таймера обновления:"
systemctl is-active lords-content-refresh.timer || true
