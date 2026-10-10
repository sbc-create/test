#!/usr/bin/env bash
# Подключение self-hosted runner для сборок витрин. Одна команда владельца.
#
#   bash automation/host/install-github-runner.sh \
#       --repo <owner/name> --labels site-factory-builder \
#       --token-file /etc/site-factory/secrets/github_runner_token \
#       [--account runner] [--version 2.321.0] [--dry-run]
#
# Зачем он есть. GitHub-hosted runner'ы платные, способа оплаты сейчас нет, а
# выпуск КОДА ячейки без зелёного прогона CI исполнитель не принимает и
# принимать не должен: он сверяет прогон, его коммит и его ветку. Значит нужен
# свой runner — и ровно это здесь и ставится, без подмены статусов и без
# отключения обязательного CI.
#
# Чего сценарий НЕ делает: не меняет firewall, sudoers, SSH, DNS и TLS; не
# ставит docker; не публикует приватные репозитории; не создаёт ничего
# платного; не трогает витрины и очередь выпуска.
#
# ВАЖНО О ПРОВЕРЕННОСТИ. На момент написания (2026-10-10) сценарий НЕ
# исполнялся ни на одной машине: подходящей машины нет, а операции GitHub вне
# профиля сессии. Проверены синтаксис (`bash -n`) и собственные отказы на
# недостающих входах. Первый настоящий запуск — на машине владельца, и его
# результат надо прочитать, а не предположить.
set -Eeuo pipefail

FORBIDDEN_HOST="claude-control-01"
VERSION="2.321.0"
ACCOUNT="runner"
REPO=""
LABELS=""
TOKEN_FILE=""
dry_run=0

die() { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 2; }
log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
ok()  { printf '   \033[32mOK\033[0m   %s\n' "$*"; }
run() { if [ "$dry_run" = 1 ]; then printf '   [dry_run прогон] %s\n' "$*"; else "$@"; fi; }

while [ $# -gt 0 ]; do
  case "$1" in
    --repo)       REPO="${2:-}"; shift 2 ;;
    --labels)     LABELS="${2:-}"; shift 2 ;;
    --token-file) TOKEN_FILE="${2:-}"; shift 2 ;;
    --account)    ACCOUNT="${2:-}"; shift 2 ;;
    --version)    VERSION="${2:-}"; shift 2 ;;
    --dry-run)    dry_run=1; shift ;;
    *) die "неизвестный аргумент $1" ;;
  esac
done

# --- 1. Где запускать нельзя ------------------------------------------------
#
# Решение владельца: production-хост под сборки не отдаётся. Проверка стоит
# первой и по ИМЕНИ МАШИНЫ, а не по совести запускающего: перепутать хост в
# ssh-сессии проще всего.
log "проверка машины"
THIS_HOST="$(hostname)"
if [ "$THIS_HOST" = "$FORBIDDEN_HOST" ]; then
  die "это $FORBIDDEN_HOST — production-хост сети. Под сборки он не
   отдаётся решением владельца, и память здесь уже заканчивалась (OOM 10.10).
   Запускайте на отдельной машине."
fi
ok "машина $THIS_HOST — не production-хост сети"

# --- 2. Входы, которые нельзя угадывать -------------------------------------
[ -n "$REPO" ]   || die "нужен --repo <owner/name>: угадывать репозиторий нельзя"
[ -n "$LABELS" ]  || die "нужен --labels: по метке задания отличаются от чужих"
case "$REPO" in */*) : ;; *) die "--repo должен быть в форме owner/name" ;; esac

[ -n "$TOKEN_FILE" ] || die "нужен --token-file с токеном регистрации.
   Взять: GitHub → репозиторий → Settings → Actions → Runners →
   New self-hosted runner. Токен живёт час. В git, лог и отчёт он не попадает:
   сценарий читает его из файла и нигде не печатает."
[ -f "$TOKEN_FILE" ] || die "файла токена нет: $TOKEN_FILE"
# Права проверяются, а не предполагаются: токен регистрации даёт право
# подключить машину к репозиторию.
MODE="$(stat -c '%a' "$TOKEN_FILE")"
case "$MODE" in 600|400) ok "права файла токена $MODE" ;;
  *) die "файл токена доступен шире, чем 600: $MODE" ;; esac

# --- 3. Что need на машине -------------------------------------------------
log "проверка окружения"
for need in curl tar python3; do
  command -v "$need" >/dev/null 2>&1 || die "нет $need"
done
ok "curl, tar, python3 на месте"
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  die "нужен Python 3.10 или новее: на нём идут проверки репозитория"
fi
ok "python3 $(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"

FREE_MIB="$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)"
if [ "${FREE_MIB:-0}" -lt 2048 ]; then
  die "доступно ${FREE_MIB} МиБ памяти: прогон тестов требует около гигабайта,
   и ставить runner на машину без запаса значит получить падения вместо проверок"
fi
ok "памяти доступно ${FREE_MIB} МиБ"

# --- 4. Учётная запись под runner -------------------------------------------
#
# Своя, не root и не учётная запись сайтов: кто исполняет код из репозитория,
# тот не должен иметь прав ни на витрины, ни на очередь.
log "учётная запись $ACCOUNT"
if id "$ACCOUNT" >/dev/null 2>&1; then
  ok "учётная запись уже есть"
else
  run useradd --create-home --shell /bin/bash "$ACCOUNT"
  ok "учётная запись создана"
fi
HOME_DIR="/home/$ACCOUNT"
RUNNER_DIR="$HOME_DIR/actions-runner"

# --- 5. Официальный пакет runner'а ------------------------------------------
log "пакет runner $VERSION"
ARCHIVE="actions-runner-linux-x64-${VERSION}.tar.gz"
URL="https://github.com/actions/runner/releases/download/v${VERSION}/${ARCHIVE}"
run install -d -o "$ACCOUNT" -g "$ACCOUNT" -m 0750 "$RUNNER_DIR"
run su - "$ACCOUNT" -c "cd '$RUNNER_DIR' && curl -fsSL -o '$ARCHIVE' '$URL'"
run su - "$ACCOUNT" -c "cd '$RUNNER_DIR' && tar xzf '$ARCHIVE' && rm -f '$ARCHIVE'"
ok "пакет распакован в $RUNNER_DIR"

# --- 6. Регистрация на НАЗВАННЫЙ репозиторий --------------------------------
#
# Токен передаётся аргументом команды внутри su и не печатается ни одной
# строкой вывода. `--unattended` и `--replace` нужны, чтобы повторный запуск
# сценария не требовал ответов и не плодил вторую запись той же машины.
log "регистрация на https://github.com/$REPO"
TOKEN="$(cat "$TOKEN_FILE")"
if [ "$dry_run" = 1 ]; then
  printf '   [dry_run прогон] config.sh --url https://github.com/%s --labels %s --unattended --replace\n' "$REPO" "$LABELS"
else
  su - "$ACCOUNT" -c "cd '$RUNNER_DIR' && ./config.sh \
      --url 'https://github.com/$REPO' \
      --token '$TOKEN' \
      --name '$(hostname)-site-factory' \
      --labels '$LABELS' \
      --work _work --unattended --replace" >/dev/null
  ok "runner зарегистрирован (вывод подавлен: в нём бывает токен)"
fi
unset TOKEN

# --- 7. Служба --------------------------------------------------------------
log "служба runner'а"
run bash -c "cd '$RUNNER_DIR' && ./svc.sh install '$ACCOUNT'"
run bash -c "cd '$RUNNER_DIR' && ./svc.sh start"
ok "служба поставлена и запущена"

# --- 8. Что проверить дальше ------------------------------------------------
log "готово; проверить вручную, не предполагая"
cat <<HINT
   1. В GitHub: Settings → Actions → Runners — машина обязана быть Idle
      с меткой: $LABELS
   2. Пробное задание: .github/workflows/runner-smoke.yml на ветке проверки.
      Пока оно не зелёное, метки в боевых release.yml НЕ менять: задание на
      несуществующей метке встанет в очередь навсегда и выпуск замрёт молча.
   3. Только после зелёного пробного: в release.yml витрин
        runs-on: ubuntu-latest
      меняется на
        runs-on: [self-hosted, linux, x64, $LABELS]
      Остальное в workflow и все проверки исполнителя (коммит, ветка, digest,
      прогон CI) остаются как есть.
HINT
