#!/usr/bin/env bash
# Единственное привилегированное действие для canary одной витрины Lords.
#
# Ставит два oneshot-юнита и запускает первый. Постоянной службы с правами на
# выкладку не остаётся: оба oneshot, RemainAfterExit=no.
#
#   render — ограниченная учётная запись, учётные данные, часы работы,
#            никакого доступа на запись в /srv/lords;
#   switch — root, БЕЗ учётных данных, минуты работы.
#
# Секрет и полные права никогда не встречаются в одном процессе.
#
# Запуск:
#   sudo bash automation/host/lords-canary-install-and-run.sh lords-02
#
# Что изменится: появятся два юнита; витрина lords-02 получит релиз, собранный
# на живом каталоге и закреплённом артефакте; на время переключения и
# наблюдения будет остановлен lords-content-refresh.timer.
#
# Что НЕ изменится: nginx, TLS, соседние витрины, Yummy, провайдер плеера,
# robots и индексируемость, наблюдатель.
set -Eeuo pipefail

SITE="${1:-lords-02}"
SRC="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
STEPS="/var/log/site-factory/lords-canary-${SITE}.steps.log"

[ "$(id -u)" = "0" ] || { echo "нужны права root: запустите через sudo" >&2; exit 2; }

echo "==> ставлю юниты"
for unit in lords-canary-render@.service lords-canary-switch@.service; do
  install -m 0644 "${SRC}/systemd/${unit}" "/etc/systemd/system/${unit}"
  echo "    ${unit}"
done
# Прежний одноблочный юнит больше не используется: он делал всё от root.
rm -f /etc/systemd/system/lords-canary@.service
systemctl daemon-reload

echo "==> запускаю сборку lords-canary-render@${SITE}.service"
# Без --wait намеренно: полный рендер идёт часами, а обрыв сессии убил бы
# операцию. Переключение запускается отдельно, после проверки результата.
systemctl start --no-block "lords-canary-render@${SITE}.service"

cat <<TXT

Сборка запущена в фоне и идёт от ограниченной учётной записи.

Следить за ходом:
    tail -f ${STEPS}

Когда в журнале появится «готово к переключению», выполнить переключение:
    sudo systemctl start --wait lords-canary-switch@${SITE}.service

Итог с отпечатками и командой отката появится здесь:
    /var/log/site-factory/lords-canary-${SITE}-<release>.json

Остановить и вернуть всё как было:
    systemctl stop lords-canary-render@${SITE}.service
    systemctl start lords-content-refresh.timer

TXT
sleep 5
echo "==> первые шаги"
tail -n 12 "${STEPS}" 2>/dev/null || echo "(журнал ещё не создан)"
