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
# Ход операции пишется в файл, а не только на экран.
#
# Причина: 2026-09-06 команда была выполнена и не оставила следа — ни записи в
# журнале операции, ни переустановленных юнитов. Установить, на каком шаге она
# завершилась, оказалось нечем: весь вывод ушёл в терминал владельца и пропал
# вместе с сеансом. Операция, о которой нельзя узнать постфактум, что она
# делала, не диагностируется.
WRAPPER_LOG="/var/log/site-factory/lords-canary-switch-now.log"
mkdir -p "$(dirname "${WRAPPER_LOG}")" 2>/dev/null || true
exec > >(tee -a "${WRAPPER_LOG}") 2>&1
echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) запуск lords-canary-switch-now.sh, uid $(id -u) ==="
SRC="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "${SRC}/../.." && pwd)"
RECEIPT="${REPO}/var/canary-staging/${SITE}.render.json"
# Отпечаток НЕ дублируется здесь. Первая редакция держала собственную копию
# константы, копия осталась от версии 2, и холостой прогон немедленно поймал
# расхождение с распиской версии 3. Две копии одного значения расходятся —
# значение берётся оттуда, где оно закреплено воротами.
EXPECT_DIGEST="$(grep -oP 'readonly EXPECT_DIGEST="\K[0-9a-f]{64}' "${SRC}/lords-canary-apply.sh")"
[ -n "${EXPECT_DIGEST}" ] || { echo "ОТКАЗ: закреплённый отпечаток не прочитан" >&2; exit 5; }

# Предусловия проверяются ДО требования прав и ДО установки юнитов.
#
# Порядок выбран так намеренно. Во-первых, ставить оснастку ради операции,
# которая заведомо откажет, значит менять систему впустую. Во-вторых, сценарий
# становится проверяемым вхолостую: обычная учётная запись может запустить его
# и убедиться, что расписка на месте и отпечаток совпадает, — все проверки до
# требования прав только читают.
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
# Расписка обещает страницы — проверяем, что они есть. Эта проверка написана
# после случая, когда запуск переключения через зависимость юнита поднял фазу
# сборки, та сделала `rm -rf` каталога staging, и расписка осталась описывать
# витрину из 61 609 страниц, которых на диске было ноль.
RECEIPT_PAGES="$(python3 -c '
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["pages"])' "${RECEIPT}")"
ACTUAL_PAGES="$(find "${REPO}/var/canary-staging/${SITE}" -name index.html 2>/dev/null | wc -l)"
[ "${ACTUAL_PAGES}" -gt 0 ] || {
  echo "ОТКАЗ: расписка обещает ${RECEIPT_PAGES} страниц, на диске ноль." >&2
  echo "       Каталог сборки пуст — вероятно, идёт или прошла новая фаза render," >&2
  echo "       которая стирает staging перед началом. Дождитесь её завершения." >&2
  exit 6
}
# Допуск на расхождение не нужен: сборка либо та самая, либо другая.
if [ "${ACTUAL_PAGES}" != "${RECEIPT_PAGES}" ]; then
  echo "ОТКАЗ: расписка обещает ${RECEIPT_PAGES} страниц, на диске ${ACTUAL_PAGES}." >&2
  echo "       Каталог сборки не соответствует расписке." >&2
  exit 7
fi
echo "==> расписка о сборке принята: отпечаток ${RECEIPT_DIGEST:0:16}, страниц ${ACTUAL_PAGES}"

[ "$(id -u)" = "0" ] || {
  echo
  echo "предусловия сошлись; для самого переключения нужны права root:"
  echo "  sudo bash ${SRC}/lords-canary-switch-now.sh"
  exit 2
}

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
