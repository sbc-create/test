# shellcheck shell=bash
# Файл подключается через `.` и собственного shebang не имеет намеренно.
# Запуск systemd-юнита с доказательством, что запуск действительно состоялся.
#
# Дефект LORDS-RELEASE-INVOCATION-REUSE-32. Прежняя редакция release-runner
# читала InvocationID до запуска, запускала юнит и сравнивала значение после.
# У неактивного юнита InvocationID ПУСТ, а `Result=success` и
# `ExecMainStatus=0` — значения по умолчанию, а не следы прогона. При
# `CollectMode=inactive` systemd выгружает юнит сразу после завершения, поэтому
# после успешной трёхчасовой сборки оба значения снова оказывались пустыми,
# сравнение «до и после» давало равенство, и готовый артефакт объявлялся
# несуществующим. Одна выкладка так и погибла: рендер отработал 173 минуты и
# выдал 61 733 страницы, а runner напечатал «юнит сборки не запускался заново».
#
# Отсюда три правила, которые и реализованы ниже:
#   1. InvocationID доказывается ПОКА юнит работает, а не после;
#   2. состояние systemd — свидетельство вспомогательное; окончательное
#      свидетельство даёт артефакт (расписка, ссылка, манифест);
#   3. отсутствие нового процесса обнаруживается за минуту, а не за три часа.
#
# Переменная SYSTEMCTL позволяет прогнать эти же функции на пользовательской
# шине в тесте, не трогая системные юниты.

SYSTEMCTL="${SYSTEMCTL:-systemctl}"

#: Заполняется unit_start_confirmed: InvocationID начатого прогона. Читается
#: вызывающим сценарием, поэтому здесь выглядит неиспользуемой.
# shellcheck disable=SC2034
UNIT_RUN_ID=""
#: Заполняется unit_wait: последние наблюдённые Result и ExecMainStatus.
UNIT_RESULT=""
UNIT_STATUS=""
# shellcheck disable=SC2034  # читается вызывающим сценарием
UNIT_LAST_STATE=""

unit_state() {
  ${SYSTEMCTL} show -p ActiveState --value "$1" 2>/dev/null || true
}

# Остановить уже работающий или зависший юнит и дождаться фактической
# остановки. Без ожидания следующий запуск попадёт в незавершённую транзакцию.
unit_stop_and_reset() {
  local unit="$1" limit="${2:-120}" waited=0 st
  st="$(unit_state "${unit}")"
  if [ -n "${st}" ] && [ "${st}" != inactive ] && [ "${st}" != failed ]; then
    ${SYSTEMCTL} stop "${unit}" >/dev/null 2>&1 || true
    while :; do
      st="$(unit_state "${unit}")"
      case "${st}" in inactive|failed|"") break ;; esac
      if [ "${waited}" -ge "${limit}" ]; then
        echo "юнит ${unit} не остановился за ${limit} с (состояние ${st})" >&2
        return 1
      fi
      sleep 2
      waited=$((waited + 2))
    done
  fi
  ${SYSTEMCTL} reset-failed "${unit}" >/dev/null 2>&1 || true
  return 0
}

# Запустить юнит и доказать появление НОВОГО непустого InvocationID.
#
# Запуск идёт через restart с --no-block: restart гарантирует новый прогон даже
# для уже активного юнита, а --no-block возвращает управление сразу, иначе
# наблюдать за собственным запуском было бы нечем — systemctl start для
# Type=oneshot блокируется до конца работы.
unit_start_confirmed() {
  local unit="$1" limit="${2:-60}" waited=0 id st
  UNIT_RUN_ID=""
  unit_stop_and_reset "${unit}" || return 1
  if ! ${SYSTEMCTL} --no-block restart "${unit}" >/dev/null 2>&1; then
    echo "systemctl restart ${unit} отклонён" >&2
    return 1
  fi
  while [ "${waited}" -lt "${limit}" ]; do
    id="$(${SYSTEMCTL} show -p InvocationID --value "${unit}" 2>/dev/null || true)"
    if [ -n "${id}" ]; then
      # shellcheck disable=SC2034  # читает вызывающий сценарий
      UNIT_RUN_ID="${id}"
      return 0
    fi
    st="$(unit_state "${unit}")"
    if [ "${st}" = failed ]; then
      echo "юнит ${unit} перешёл в failed, не начав работу" >&2
      return 1
    fi
    sleep 2
    waited=$((waited + 2))
  done
  echo "за ${limit} с у ${unit} не появилось непустой InvocationID: новый процесс не начался" >&2
  return 1
}

# Дождаться завершения, снимая Result и ExecMainStatus ПОКА они ещё доступны.
# heartbeat_cmd вызывается не реже раза в heartbeat секунд: без этого журнал
# трёхчасовой сборки молчит, и отличить работу от зависания нечем.
unit_wait() {
  local unit="$1" limit="${2:-25200}" heartbeat="${3:-240}" beat_cmd="${4:-}"
  local elapsed=0 since_beat=0 st
  UNIT_RESULT=""; UNIT_STATUS=""; UNIT_LAST_STATE=""
  while :; do
    st="$(unit_state "${unit}")"
    # shellcheck disable=SC2034  # читает вызывающий сценарий
    UNIT_LAST_STATE="${st}"
    case "${st}" in
      active|activating|deactivating|reloading)
        UNIT_RESULT="$(${SYSTEMCTL} show -p Result --value "${unit}" 2>/dev/null || echo "${UNIT_RESULT}")"
        UNIT_STATUS="$(${SYSTEMCTL} show -p ExecMainStatus --value "${unit}" 2>/dev/null || echo "${UNIT_STATUS}")"
        ;;
      failed)
        UNIT_RESULT="$(${SYSTEMCTL} show -p Result --value "${unit}" 2>/dev/null || echo failed)"
        UNIT_STATUS="$(${SYSTEMCTL} show -p ExecMainStatus --value "${unit}" 2>/dev/null || echo "${UNIT_STATUS}")"
        return 1
        ;;
      inactive|"")
        return 0
        ;;
    esac
    sleep 5
    elapsed=$((elapsed + 5))
    since_beat=$((since_beat + 5))
    if [ -n "${beat_cmd}" ] && [ "${since_beat}" -ge "${heartbeat}" ]; then
      since_beat=0
      ${beat_cmd} "${elapsed}" "${st}" || true
    fi
    if [ "${elapsed}" -ge "${limit}" ]; then
      echo "сторож: ${unit} не завершился за ${limit} с, останавливаю" >&2
      ${SYSTEMCTL} stop "${unit}" >/dev/null 2>&1 || true
      return 1
    fi
  done
}
