#!/usr/bin/env bash
# Health of the control host itself: disk, inodes, memory, load, TLS expiry,
# backup freshness, and the services the factory depends on.
#
# Two rules from the factory carry over here:
#   * a metric that cannot be measured is reported as unmeasured with a reason,
#     never as 0 — a zero would read as "healthy";
#   * the exit code is the number of alerts, so the systemd unit fails visibly
#     when something is wrong instead of succeeding quietly.
#
# Output: one JSON document per run on stdout, appended to the log by the unit.
set -uo pipefail

STATE_DIR="${SITE_FACTORY_LOG_DIR:-/var/log/site-factory}"
BACKUP_DIR="${SITE_FACTORY_BACKUP_DIR:-/srv/backups}"
SITES_DIR="${SITE_FACTORY_SITES_DIR:-/srv/sites}"

# Thresholds. Deliberately conservative: this host has 4 vCPU and 10 GB RAM and
# is expected to run browser tests, which spike both.
DISK_WARN_PCT="${DISK_WARN_PCT:-80}"
INODE_WARN_PCT="${INODE_WARN_PCT:-80}"
MEM_WARN_PCT="${MEM_WARN_PCT:-90}"
LOAD_WARN_PER_CPU="${LOAD_WARN_PER_CPU:-2.0}"
TLS_WARN_DAYS="${TLS_WARN_DAYS:-21}"
BACKUP_MAX_AGE_HOURS="${BACKUP_MAX_AGE_HOURS:-30}"

ALERTS=()
CHECKS=()

# Привести владельца файла к владельцу каталога, в котором он лежит.
#
# Вынесено функцией, потому что правило неочевидно: «кто пишет — тот и
# выравнивает». Возвращает 0, даже когда выровнять не удалось: отказ здесь не
# повод завалить проверку здоровья хоста.
align_log_owner() {
  local dir="$1" file="$2"
  [ -e "$dir" ] && [ -e "$file" ] || return 0
  local dir_owner file_owner
  dir_owner="$(stat -c '%U:%G' "$dir" 2>/dev/null)" || return 0
  file_owner="$(stat -c '%U:%G' "$file" 2>/dev/null)" || return 0
  [ "$dir_owner" = "$file_owner" ] && return 0
  chown "$dir_owner" "$file" 2>/dev/null || true
  return 0
}

add_check() { CHECKS+=("$1"); }
add_alert() { ALERTS+=("$1"); }

json_str() { printf '%s' "$1" | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))'; }

check_disk() {
  local pct
  pct="$(df -P / | awk 'NR==2{gsub("%","",$5);print $5}')"
  if [ -z "$pct" ]; then
    add_check '{"check":"disk_root","status":"unmeasured","reason":"df вернул пустой результат"}'
    add_alert "disk_root: не измерено"
    return
  fi
  local status="ok"
  if [ "$pct" -ge "$DISK_WARN_PCT" ]; then
    status="alert"; add_alert "disk_root: ${pct}% >= ${DISK_WARN_PCT}%"
  fi
  add_check "{\"check\":\"disk_root\",\"status\":\"$status\",\"used_pct\":$pct,\"threshold_pct\":$DISK_WARN_PCT}"
}

check_inodes() {
  local pct
  pct="$(df -Pi / | awk 'NR==2{gsub("%","",$5);print $5}')"
  if [ -z "$pct" ]; then
    add_check '{"check":"inodes_root","status":"unmeasured","reason":"df -i вернул пустой результат"}'
    add_alert "inodes_root: не измерено"
    return
  fi
  local status="ok"
  if [ "$pct" -ge "$INODE_WARN_PCT" ]; then
    status="alert"; add_alert "inodes_root: ${pct}% >= ${INODE_WARN_PCT}%"
  fi
  add_check "{\"check\":\"inodes_root\",\"status\":\"$status\",\"used_pct\":$pct,\"threshold_pct\":$INODE_WARN_PCT}"
}

check_memory() {
  # Available, not free: page cache is reclaimable and counting it as used
  # would alert on a perfectly healthy host.
  local total avail used_pct
  total="$(awk '/^MemTotal:/{print $2}' /proc/meminfo)"
  avail="$(awk '/^MemAvailable:/{print $2}' /proc/meminfo)"
  if [ -z "$total" ] || [ -z "$avail" ] || [ "$total" -eq 0 ]; then
    add_check '{"check":"memory","status":"unmeasured","reason":"/proc/meminfo не прочитан"}'
    add_alert "memory: не измерено"
    return
  fi
  used_pct=$(( (total - avail) * 100 / total ))
  local status="ok"
  if [ "$used_pct" -ge "$MEM_WARN_PCT" ]; then
    status="alert"; add_alert "memory: ${used_pct}% >= ${MEM_WARN_PCT}%"
  fi
  add_check "{\"check\":\"memory\",\"status\":\"$status\",\"used_pct\":$used_pct,\"threshold_pct\":$MEM_WARN_PCT}"
}

check_load() {
  local load cpus per_cpu status
  load="$(awk '{print $1}' /proc/loadavg)"
  cpus="$(nproc)"
  if [ -z "$load" ] || [ -z "$cpus" ] || [ "$cpus" -eq 0 ]; then
    add_check '{"check":"load","status":"unmeasured","reason":"/proc/loadavg или nproc недоступны"}'
    add_alert "load: не измерено"
    return
  fi
  per_cpu="$(awk -v l="$load" -v c="$cpus" 'BEGIN{printf "%.2f", l/c}')"
  status="ok"
  if awk -v p="$per_cpu" -v t="$LOAD_WARN_PER_CPU" 'BEGIN{exit !(p>=t)}'; then
    status="alert"; add_alert "load: ${per_cpu} на ядро >= ${LOAD_WARN_PER_CPU}"
  fi
  add_check "{\"check\":\"load\",\"status\":\"$status\",\"load1\":$load,\"cpus\":$cpus,\"per_cpu\":$per_cpu,\"threshold_per_cpu\":$LOAD_WARN_PER_CPU}"
}

check_services() {
  local unit status active
  for unit in ssh nginx docker postgresql fail2ban site-factory-docker-firewall; do
    active="$(systemctl is-active "$unit" 2>/dev/null)"
    status="ok"
    # postgresql.service on Debian is a oneshot wrapper and reports "exited"
    # once the cluster is up; treating that as a failure would alert forever.
    case "$active" in
      active|exited) : ;;
      *) status="alert"; add_alert "service ${unit}: ${active:-unknown}" ;;
    esac
    add_check "{\"check\":\"service\",\"unit\":\"$unit\",\"status\":\"$status\",\"state\":$(json_str "${active:-unknown}")}"
  done
}

check_tls() {
  # Certificates are discovered, never assumed. No sites are deployed yet, so
  # the honest answer today is "no certificates found", not "all valid".
  local found=0 cert days status
  shopt -s nullglob
  for cert in /etc/letsencrypt/live/*/cert.pem "$SITES_DIR"/*/shared/tls/*.pem; do
    [ -r "$cert" ] || continue
    found=$((found + 1))
    if ! days="$(python3 - "$cert" <<'PYEOF'
import subprocess, sys, datetime
out = subprocess.run(["openssl", "x509", "-enddate", "-noout", "-in", sys.argv[1]],
                     capture_output=True, text=True)
if out.returncode != 0:
    sys.exit(1)
end = out.stdout.strip().split("=", 1)[1]
exp = datetime.datetime.strptime(end, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=datetime.timezone.utc)
print((exp - datetime.datetime.now(datetime.timezone.utc)).days)
PYEOF
    )"; then
      add_check "{\"check\":\"tls\",\"cert\":$(json_str "$cert"),\"status\":\"unmeasured\",\"reason\":\"openssl не смог прочитать срок действия\"}"
      add_alert "tls ${cert}: срок не измерен"
      continue
    fi
    status="ok"
    if [ "$days" -le "$TLS_WARN_DAYS" ]; then
      status="alert"; add_alert "tls ${cert}: осталось ${days} дн. <= ${TLS_WARN_DAYS}"
    fi
    add_check "{\"check\":\"tls\",\"cert\":$(json_str "$cert"),\"status\":\"$status\",\"days_left\":$days,\"threshold_days\":$TLS_WARN_DAYS}"
  done
  shopt -u nullglob
  [ "$found" -eq 0 ] && add_check '{"check":"tls","status":"none","reason":"сертификатов на хосте нет: ни один сайт не развёрнут"}'
}

check_backups() {
  local latest age_h status
  if [ ! -d "$BACKUP_DIR" ]; then
    add_check '{"check":"backup","status":"unmeasured","reason":"каталог бэкапов отсутствует"}'
    add_alert "backup: каталог $BACKUP_DIR отсутствует"
    return
  fi
  latest="$(find "$BACKUP_DIR" -maxdepth 2 -name '*.verified.json' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)"
  if [ -z "$latest" ]; then
    # No verified backup yet is a real state, not a passing one.
    add_check '{"check":"backup","status":"none","reason":"подтверждённых бэкапов ещё нет"}'
    add_alert "backup: подтверждённых бэкапов нет"
    return
  fi
  age_h=$(( ( $(date +%s) - $(stat -c %Y "$latest") ) / 3600 ))
  status="ok"
  if [ "$age_h" -ge "$BACKUP_MAX_AGE_HOURS" ]; then
    status="alert"; add_alert "backup: последний подтверждённый ${age_h} ч назад >= ${BACKUP_MAX_AGE_HOURS}"
  fi
  add_check "{\"check\":\"backup\",\"status\":\"$status\",\"latest\":$(json_str "$latest"),\"age_hours\":$age_h,\"threshold_hours\":$BACKUP_MAX_AGE_HOURS}"
}

check_nginx_config() {
  # Runs as root from the timer, which is the only context where `nginx -t`
  # can open its error log and pid file. This is the privileged counterpart of
  # the nginx stage that tests/run-all.sh has to skip as an unprivileged user.
  if ! command -v nginx >/dev/null 2>&1; then
    add_check '{"check":"nginx_config","status":"none","reason":"nginx не установлен"}'
    return
  fi
  local out code
  out="$(nginx -t 2>&1)"; code=$?
  if [ $code -eq 0 ]; then
    add_check '{"check":"nginx_config","status":"ok"}'
  elif printf '%s' "$out" | grep -q "Permission denied"; then
    add_check '{"check":"nginx_config","status":"unmeasured","reason":"нет прав на error_log/pid — запуск не от root"}'
    add_alert "nginx_config: проверка не выполнена (нет прав)"
  else
    add_check "{\"check\":\"nginx_config\",\"status\":\"alert\",\"detail\":$(json_str "$out")}"
    add_alert "nginx_config: конфигурация невалидна"
  fi
}

check_public_ports() {
  # Anything listening on a non-loopback address other than 22/80/443 is a
  # policy violation on this host, including ports Docker publishes past UFW.
  local unexpected
  unexpected="$(ss -tlnH 2>/dev/null \
    | awk '{print $4}' \
    | grep -vE '^(127\.|\[::1\])' \
    | sed -E 's/.*:([0-9]+)$/\1/' \
    | sort -un \
    | grep -vE '^(22|80|443)$' \
    | paste -sd, -)"
  if [ -n "$unexpected" ]; then
    add_check "{\"check\":\"public_ports\",\"status\":\"alert\",\"unexpected\":$(json_str "$unexpected")}"
    add_alert "public_ports: наружу слушают ${unexpected}"
  else
    add_check '{"check":"public_ports","status":"ok","allowed":"22,80,443"}'
  fi
}

check_disk
check_inodes
check_memory
check_load
check_services
check_tls
check_backups
check_nginx_config
check_public_ports

mkdir -p "$STATE_DIR" 2>/dev/null || true

{
  printf '{"report":"host-health","host":%s,"generated_at":%s,"alerts":%d,"checks":[' \
    "$(json_str "$(hostname)")" \
    "$(json_str "$(date -u +%Y-%m-%dT%H:%M:%SZ)")" \
    "${#ALERTS[@]}"
  printf '%s' "$(IFS=,; echo "${CHECKS[*]}")"
  printf '],"alert_details":['
  first=1
  for a in ${ALERTS+"${ALERTS[@]}"}; do
    [ $first -eq 1 ] || printf ','
    printf '%s' "$(json_str "$a")"
    first=0
  done
  printf ']}\n'
} | tee -a "$STATE_DIR/health.log" 2>/dev/null || true

# Владелец лога приводится к владельцу каталога.
#
# Юнит работает от root, поэтому tee создаёт файл root:root. Каталог же
# принадлежит claude, и logrotate для него настроен с `su claude claude` —
# понижает права, а затем не может открыть root-овский файл. Итог: с 2026-09-02
# `logrotate.service` падал ежедневно с `Permission denied`, лог не вращался
# вовсе и рос без предела, а сам отказ выглядел как поломка ротации вообще, хотя
# спотыкалась она об один файл.
#
# Выравнивание делает не logrotate, а тот, кто пишет: он один знает, что создал
# файл, и он один здесь имеет права. Ошибка chown не важна — если прав нет,
# значит юнит запущен не от root, и тогда файл и так создан подходящим
# пользователем.
align_log_owner "$STATE_DIR" "$STATE_DIR/health.log"

for a in ${ALERTS+"${ALERTS[@]}"}; do
  echo "ALERT: $a" >&2
done

exit "${#ALERTS[@]}"
