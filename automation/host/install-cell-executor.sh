#!/usr/bin/env bash
# Установка исполнителя заявок на выпуск. Одна команда владельца, один раз.
#
#   sudo bash automation/host/install-cell-executor.sh            # установить
#   sudo bash automation/host/install-cell-executor.sh --dry-run  # только показать
#
# Что он ставит
# -------------
#
#   /usr/local/lib/site-factory-cell/   КОРНЕВАЯ копия пакета factory
#   /var/lib/site-cells/requests/       очередь: пишет claude, читает root
#   /var/lib/site-cells/{results,locks,state}/  результаты и замки: только root
#   site-cell-executor.service/.timer   разбор очереди раз в минуту
#
# Почему корневая копия, а не запуск из рабочего каталога
# -------------------------------------------------------
#
# Юнит, исполняющий код из каталога, куда может писать обычная учётная запись,
# означает, что писать в этот каталог — то же самое, что выполнять команды от
# root. Этот контур уже имеет такую проблему в nova-daily-refresh, и она там
# вынесена в отчёт владельцу как долг. Повторять её в новом компоненте нельзя.
#
# Поэтому пакет копируется под root-владение, и обновление исполнителя —
# осознанное действие владельца (повторный запуск этого сценария), а не
# следствие правки в рабочем каталоге.
#
# Чего сценарий НЕ делает: не меняет sudoers, firewall, SSH, DNS, TLS и
# индексацию; не трогает чужие витрины и не открывает ни одного порта наружу.
set -Eeuo pipefail

dry_run=0
[ "${1:-}" = "--dry-run" ] && dry_run=1

SRC_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
# Опись зафиксированного пакета лежит на уровень выше дерева: <пакет>/manifest.json,
# <пакет>/tree/ = SRC_ROOT. Если сценарий запущен из пакета, источник кода
# неизменен, а корень рабочих копий репозиториев берётся из описи, а не из
# места сценария: это разные вещи, и раньше они совпадали лишь случайно.
MANIFEST="$SRC_ROOT/../manifest.json"
DEST=/usr/local/lib/site-factory-cell
QUEUE=/var/lib/site-cells
UNIT_DIR=/etc/systemd/system
SERVICE=site-cell-executor.service
TIMER=site-cell-executor.timer
# Учётная запись, которой разрешено класть заявки. Читать результаты и замки
# она не должна: они принадлежат исполнителю.
SUBMITTER="${CELL_EXECUTOR_SUBMITTER:-claude}"

log()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
die()  { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }
run()  { if [ "$dry_run" = 1 ]; then printf '   [сухой прогон] %s\n' "$*"; else "$@"; fi; }

[ "$dry_run" = 1 ] || [ "$(id -u)" = 0 ] || die "нужен root"
[ -f "$SRC_ROOT/factory/cell/executor.py" ] || die "не похоже на репозиторий фабрики: $SRC_ROOT"
id "$SUBMITTER" >/dev/null 2>&1 || die "учётной записи $SUBMITTER нет"

PY="$SRC_ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3 || true)"
[ -n "$PY" ] || die "python3 не найден"

log "проверка пакета до установки"
run "$PY" -c "import sys; sys.path.insert(0, '$SRC_ROOT'); from factory.cell import executor, queue; print('   пакет импортируется')"

log "корневая копия пакета в $DEST"
run rm -rf "$DEST.new"
run mkdir -p "$DEST.new"
run cp -a "$SRC_ROOT/factory" "$DEST.new/factory"
run cp -a "$SRC_ROOT/schemas" "$DEST.new/schemas"
run cp -a "$SRC_ROOT/config" "$DEST.new/config"
run chown -R root:root "$DEST.new"
run chmod -R go-w "$DEST.new"
run rm -rf "$DEST.prev"
[ -d "$DEST" ] && run mv "$DEST" "$DEST.prev"
run mv "$DEST.new" "$DEST"

log "запись абсолютных путей установки"
# Корневая копия лежит в /usr/local/lib, рабочие копии репозиториев сайтов — в
# рабочем каталоге фабрики. Вывести второе из первого нельзя, и попытка вывести
# стоила первой настоящей заявки: исполнитель искал tools/build_release.py рядом
# с собой и отверг выпуск. Значение пишет root, оно недоступно на запись
# подающей стороне, и код репозитория root всё равно не исполняет.
PKG_ID=""; PKG_DIGEST=""; PKG_COMMIT=""; REPOS_ROOT="$SRC_ROOT"
if [ -f "$MANIFEST" ]; then
  eval "$("$PY" - "$MANIFEST" <<'PYMANIFEST'
import json, shlex, sys
m = json.load(open(sys.argv[1], encoding="utf-8"))
for name, key in (("PKG_ID", "package_id"), ("PKG_DIGEST", "digest"),
                  ("PKG_COMMIT", "commit"), ("REPOS_ROOT", "site_repos_root")):
    print(f"{name}={shlex.quote(str(m.get(key) or ''))}")
PYMANIFEST
)"
  [ -n "$REPOS_ROOT" ] || die "в описи пакета нет site_repos_root"
  [ -f "$REPOS_ROOT/factory/cell/executor.py" ] || die "site_repos_root описи не похож на репозиторий: $REPOS_ROOT"
  log "пакет $PKG_ID, коммит ${PKG_COMMIT:0:12}; рабочие копии репозиториев: $REPOS_ROOT"
else
  log "[!] описи пакета нет: код берётся из $SRC_ROOT как есть"
fi

if [ "$dry_run" = 0 ]; then
  "$PY" - "$DEST/cell-install.json" "$REPOS_ROOT" "$PKG_ID" "$PKG_DIGEST" "$PKG_COMMIT" "$SRC_ROOT" <<'PYWRITE'
import json, sys
from datetime import datetime, timezone
путь, repos, pid, digest, commit, src = sys.argv[1:7]
json.dump({
    "site_repos_root": repos,
    "installed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "package_id": pid or None,
    "package_digest": digest or None,
    "package_commit": commit or None,
    "code_source": src,
}, open(путь, "w", encoding="utf-8"), ensure_ascii=False, indent=2, sort_keys=True)
open(путь, "a", encoding="utf-8").write("\n")
PYWRITE
  chown root:root "$DEST/cell-install.json"
  chmod 0644 "$DEST/cell-install.json"
  log "  основание путей репозиториев: $REPOS_ROOT"
else
  printf '   [сухой прогон] %s/cell-install.json <- site_repos_root=%s package_id=%s\n' "$DEST" "$REPOS_ROOT" "${PKG_ID:-нет}"
fi

log "проверка достижимости рабочих копий репозиториев"
# Установка обязана падать здесь, а не молча оставлять исполнителя, который
# отвергнет первую же заявку. Отсутствие ОДНОЙ копии не останавливает остальные.
if [ "$dry_run" = 0 ]; then
  reachable=0
  while IFS=$'\t' read -r site_id account repo; do
    if [ -z "$repo" ]; then
      log "  [!] $site_id: $account"
      continue
    fi
    if [ ! -f "$repo/tools/build_release.py" ]; then
      log "  [!] $site_id: нет $repo/tools/build_release.py"
      continue
    fi
    # Сборка идёт НЕ от root, а под учётной записью сайта. Права root здесь
    # ничего не доказывают: каталог принадлежит другой учётной записи, и путь к
    # нему лежит через чужой домашний каталог. Проверяется тем, кто будет читать.
    if id "$account" >/dev/null 2>&1 \
       && ! runuser -u "$account" -- test -r "$repo/tools/build_release.py" 2>/dev/null; then
      log "  [!] $site_id: $account не может прочитать $repo/tools/build_release.py"
      continue
    fi
    reachable=$((reachable + 1))
    log "  $site_id: $repo"
  done < <("$PY" - <<PYCHECK
import sys
sys.path.insert(0, "$DEST")
from factory.cell import registry, runtime

for site_id in sorted(registry.extracted_sites()):
    try:
        repo = registry.resolve(site_id).repo_path
        account = runtime.размещение(site_id).account or "root"
    except Exception as exc:
        print(f"{site_id}\t{exc}\t")
        continue
    print(f"{site_id}\t{account}\t{repo}")
PYCHECK
)
  log "  доступно рабочих копий: $reachable"
  [ "$reachable" -gt 0 ] || die "ни одна рабочая копия репозитория не доступна исполнителю"
else
  printf '   [сухой прогон] проверить repo_path каждой выделенной витрины\n'
fi

log "каталоги очереди"
run install -d -o root -g root -m 0755 "$QUEUE"
# Заявки кладёт непривилегированная сторона. Липкий бит: удалить чужую заявку
# нельзя, а значит нельзя и подменить её между проверкой и исполнением.
run install -d -o "$SUBMITTER" -g root -m 1730 "$QUEUE/requests"
# setgid: файлы, созданные root, наследуют группу каталога, а не первичную
# группу процесса. Без него результат выходил `root:root` — режим верный, а
# читать некому. Писатель ставит группу и сам, но полагаться на один механизм
# там, где отказ выглядит как молчание, нельзя.
run install -d -o root -g "$SUBMITTER" -m 2750 "$QUEUE/results"
run install -d -o root -g root -m 0700 "$QUEUE/locks"
run install -d -o root -g root -m 0700 "$QUEUE/state"

log "починка ранее записанных результатов"
# Файлы, записанные до исправления, остались `rw------- root:root`. Правим
# ТОЧЕЧНО: только .json в каталоге результатов, только группа и режим. Никакой
# рекурсивной передачи каталогов и никакого 777.
if [ "$dry_run" = 0 ]; then
  fixed_count=0
  for f in "$QUEUE"/results/*.json; do
    [ -e "$f" ] || continue
    chgrp "$SUBMITTER" "$f"
    chmod 0640 "$f"
    fixed_count=$((fixed_count + 1))
  done
  log "  приведено в читаемый вид: $fixed_count"
else
  printf '   [сухой прогон] chgrp %s + chmod 0640 для %s/results/*.json\n' "$SUBMITTER" "$QUEUE"
fi

log "проверка чтения результата подающим"
# Числовой режим сам по себе ничего не доказывает: важно, что файл ДЕЙСТВИТЕЛЬНО
# читается тем, кто подал заявку. Пишем пробу от root и читаем от него.
probe_file="$QUEUE/results/.install-probe.json"
if [ "$dry_run" = 0 ]; then
  "$PY" -c "
import sys; sys.path.insert(0, '$SRC_ROOT')
from pathlib import Path
from factory.cell import queue
queue.записать_атомарно(Path('$probe_file'), {'probe': True})
"
  if runuser -u "$SUBMITTER" -- cat "$probe_file" >/dev/null 2>&1; then
    log "  результат читается пользователем $SUBMITTER"
  else
    rm -f "$probe_file"
    die "пользователь $SUBMITTER не может прочитать результат операции: "\
"обратная связь исполнителя не работает"
  fi
  rm -f "$probe_file"
else
  printf '   [сухой прогон] записать пробу и прочитать её от %s\n' "$SUBMITTER"
fi

log "юнит и таймер"
run install -m 0644 "$SRC_ROOT/automation/host/$SERVICE" "$UNIT_DIR/$SERVICE"
# Учётные данные GitHub. Без них исполнитель не может доказать происхождение
# выпуска и отвергает заявки — это исправное поведение, а не деградация.
# Подключение вынесено в отдельный сценарий: токен не должен приходить сюда ни
# аргументом, ни переменной окружения.
GH_TOKEN_FILE="${CELL_GH_TOKEN_FILE:-/etc/site-factory/gh-token}"
release_ready=0
if [ "$dry_run" = 1 ]; then
  printf '   [сухой прогон] проверить учётные данные GitHub\n'
elif [ -f "$GH_TOKEN_FILE" ]; then
  if bash "$SRC_ROOT/automation/host/install-gh-credential.sh" --check; then
    release_ready=1
  fi
else
  log "  [!] $GH_TOKEN_FILE нет"
fi

log "управляемый upstream для зарегистрированных витрин"
# Без этого переключение трафика — молчаливое бездействие: исполнитель пишет
# файл upstream, которого никто не читает. Каждая витрина подключается
# отдельно; отсутствие её конфигурации не останавливает остальные.
for site in $("$PY" -c "
import sys; sys.path.insert(0, '$SRC_ROOT')
from factory.cell import registry
print(' '.join(sorted(registry.extracted_sites())))
" 2>/dev/null); do
  if [ "$dry_run" = 1 ]; then
    printf '   [сухой прогон] подключить upstream %s\n' "$site"
  elif bash "$SRC_ROOT/automation/host/wire-nginx-upstream.sh" --site "$site"; then
    log "  $site: подключён"
  else
    log "  $site: пропущен (см. вывод выше) — остальные продолжаются"
  fi
done

log "теневые копии конфигураций в загрузке nginx"
# Не входит в установку и ничего не меняет: сообщает о копиях, которые nginx
# загружает как вторую конфигурацию. Их делал не этот контур, и убирать их —
# отдельное решение. Отказ здесь не останавливает установку.
run bash "$SRC_ROOT/automation/host/nginx-shadow-configs.sh" || true

log "проверка после установки"
run systemctl list-timers "$TIMER" --no-pager
run "$PY" -c "import sys; sys.path.insert(0, '$DEST'); from factory.cell import queue; print('   корневая копия импортируется')"

if [ "$dry_run" = 1 ]; then
  echo
  echo "сухой прогон завершён: ничего не менялось"
  exit 0
fi

if [ "$release_ready" = 1 ]; then
  cat <<'ГОТОВО'

ГОТОВ К ВЫПУСКУ. Дальше выпуски идут без команд владельца:

  триггер кладёт заявку в /var/lib/site-cells/requests/, исполнитель
  разбирает её раз в минуту и перед каждой выкладкой доказывает у GitHub
  связку «разрешённый репозиторий → разрешённая ветка → этот коммит →
  успешный прогон».

Посмотреть состояние:
  systemctl status site-cell-executor.service
  ls /var/lib/site-cells/results/

Остановить приём:
  systemctl disable --now site-cell-executor.timer
ГОТОВО
  exit 0
fi

cat <<ГОТОВО

УСТАНОВЛЕН, ВЫПУСК ЗАБЛОКИРОВАН.

Исполнитель, очередь и таймер на месте. Учётных данных GitHub у службы нет,
поэтому происхождение выпуска доказать нечем, и КАЖДАЯ заявка будет отвергнута
до единой операции над витриной. Живые сайты при этом не меняются.

Разблокировать (токен вводится без эха и не попадает в историю команд):

  sudo bash $SRC_ROOT/automation/host/install-gh-credential.sh

Какой токен нужен: fine-grained personal access token владельца sbc-create,
Only select repositories — только site-* из реестра, права Repository
permissions: Actions Read-only и Metadata Read-only. Больше ничего.

Если подходящий токен уже лежит файлом:

  sudo bash $SRC_ROOT/automation/host/install-gh-credential.sh --from-file <путь>

ГОТОВО
exit 3
