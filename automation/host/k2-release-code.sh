#!/usr/bin/env bash
# Выпуск ТОЛЬКО кода одной витрины на узле K2: новый выпуск из бандла и рестарт.
# Одна команда на витрину.
#
# От кого выполняется. Либо от root, либо от учётной записи доставки
# `k2deploy` — и второе не послабление, а измеренное положение дел
# (2026-10-17): `k2deploy` состоит в группе КАЖДОЙ витрины, каталоги
# `/srv/<учётка>` и `/srv/<учётка>/releases` имеют режим `drwxrwsr-x`, то есть
# групповую запись и setgid, а перезапуск юнита витрины прямо перечислен в
# `sudo -n -l`. Всё, чего доставке не хватает против root, — это `chown`:
# файлы выпуска остаются за `k2deploy`, группа благодаря setgid — витрины, и
# служба читает их по группе. Для витрины это даже строже: свой код она
# изменить не может, а `ProtectSystem=strict` и так оставляет ей на запись
# только `data`.
#
# Зачем отдельно от k2-launch-site.sh. Тот ЗАПУСКАЕТ витрину с нуля: заводит
# маршрут nginx, кладёт данные каталога из комплекта доставки, ставит юнит.
# Для правки в коде это не подходит по двум причинам, и обе дорогие:
#
#   * он переустанавливает ДАННЫЕ витрины из `stage/data/<site>` — а данные
#     принадлежат витрине, и выпуск их только читает. Наложение проверенных
#     номеров серий (`*.nums.json`) и редакционные правки лежат рядом со
#     снимком, и перезапись комплектом доставки стёрла бы их;
#   * он трогает nginx и режим индексации, которым правка в коде не касается.
#
# Без такого инструмента правка, доставленная бандлом, лежала на узле и не
# доезжала до витрины: измерено 2026-10-15 — у восьми витрин партии выложены
# выпуски от 09:54, а бандлы с тех пор обновлялись дважды.
#
# Что делает и в каком порядке:
#   1. опознаёт витрину по описи комплекта (учётка, порт, юнит, домен);
#   2. берёт голову доставленного бандла; если `current` уже на ней — выходит
#      с кодом 0 и ничего не делает (повторный запуск безопасен);
#   3. собирает артефакт сборщиком ВИТРИНЫ и распаковывает его в
#      releases/<12 знаков>, права — витрине. Из рабочего дерева выпуск
#      не кладётся: штамп происхождения ставит сборка, и без него
#      build_id остаётся заглушкой `worktree-unbuilt`, а
#      runtime_digest_match в /healthz не может быть верным;
#   4. переносит в новый выпуск `config/player.json` ИЗ ТЕКУЩЕГО выпуска.
#      Файл несёт publisher_id, в git его нет, и без него служба не стартует
#      намеренно (fail-closed). Значение не читается и не печатается — файл
#      копируется как есть;
#   5. запоминает прежний выпуск в .previous-release и переключает `current`;
#   6. перезапускает службу, ждёт healthz и ОПОЗНАЁТ витрину: подробный
#      ответ по петле обязан называть каталог только что собранного
#      выпуска, иначе прежний выпуск возвращается;
#   7. при любой неудаче возвращает `current` на прежний выпуск, перезапускает
#      службу и сообщает код выхода.
#
# Чего НЕ делает: не трогает данные витрины, nginx, DNS, сертификаты, режим
# индексации, publisher_id и соседние витрины.
#
# Имена переменных только ASCII: кириллица в именах переменных оболочки падает
# в работе, а `bash -n` её пропускает (проверено на этом же узле).
#
# Запуск:
#   k2-release-code.sh <site_id>              выпуск
#   k2-release-code.sh <site_id> --dry-run    ничего не менять, только сверить
set -uo pipefail

site="${1:?нужен site_id}"
mode="${2:-full}"
case "$mode" in
  full|--dry-run|--verify) : ;;
  *) echo "[x] неизвестный режим $mode" >&2; exit 2 ;;
esac

stage="/home/k2deploy/stage"
manifest="$stage/MANIFEST.json"
health_timeout=600
health_interval=3

log() { printf '==> %s\n' "$*"; }
bad() { printf '[x] %s\n' "$*" >&2; }

am_root=0
[ "$(id -u)" = 0 ] && am_root=1
# Перезапуск юнита: от root напрямую, от доставки — через точную команду
# списка sudo. Список проверяется ЗАРАНЕЕ: отказ посреди выпуска оставил бы
# `current` переключённым, а службу — на прежнем коде.
restart_unit() {
  if [ "$am_root" = 1 ]; then systemctl restart "$1"; else sudo -n /usr/bin/systemctl restart "$1"; fi
}
[ -f "$manifest" ] || { bad "нет описи $manifest"; exit 2; }

read -r account port unit domain <<EOF
$(python3 - "$manifest" "$site" <<'PY'
import json, sys
опись = json.load(open(sys.argv[1], encoding="utf-8"))
ячейка = (опись.get("cells") or {}).get(sys.argv[2])
if not ячейка:
    raise SystemExit(f"в описи нет {sys.argv[2]}")
print(ячейка["account"], ячейка["port"], ячейка["unit"], ячейка["domain"])
PY
)
EOF
[ -n "${account:-}" ] || { bad "в описи нет данных по $site"; exit 2; }
log "$site: домен $domain, учётка $account, порт $port, юнит $unit"

bundle="$stage/bundles/$site.bundle"
root="/srv/$account"
current_link="$root/current"
previous_file="$root/.previous-release"
[ -f "$bundle" ] || { bad "нет бандла $bundle"; exit 2; }
[ -L "$current_link" ] || { bad "нет ссылки $current_link: витрина не запущена, это задача k2-launch-site.sh"; exit 2; }

old_release="$(readlink -f "$current_link")"
old_sha="$(basename "$old_release")"
if [ "$mode" = "--verify" ]; then
  # Ни одной мутации: только чтение подробного ответа по петле и сверка с
  # тем каталогом, на который указывает `current`. Отказ закрытый —
  # отсутствие поля означает «подтвердить нечем».
  vf="$(mktemp)"
  curl -fsS --max-time 5 "127.0.0.1:$port/healthz" -o "$vf" 2>/dev/null \
    || log "$site: подробный ответ healthz не прочитан"
  python3 - "$vf" "$old_release" "$site" "$old_release/config/template-manifest.json" <<'PY'
import json
import pathlib
import sys

файл, выпуск, витрина = sys.argv[1:4]
манифест_путь = sys.argv[4]
try:
    д = json.loads(pathlib.Path(файл).read_text(encoding="utf-8"))
except (OSError, ValueError) as пр:
    print(f"{витрина}: ответ healthz не разобран: {пр}")
    raise SystemExit(1)
путь = str(д.get("runtime_path") or "")
выпуск_id = str(д.get("release_id") or "")
совпал = bool(путь) and путь.startswith(выпуск.rstrip("/") + "/")
знак = "исполняется" if совпал else "НЕ ТОТ ВЫПУСК"
print(f"{витрина}: current -> {выпуск}")
print(f"{витрина}: на порту  {путь or '(поля нет)'}  release_id {выпуск_id or '—'}")
print(f"{витрина}: {знак}")

# Штамп происхождения ВЫЛОЖЕННОГО выпуска. Отдельный вопрос от «тот ли
# выпуск»: каталог может быть правильным, а код в нём — непрослеживаемым.
try:
    м = json.loads(pathlib.Path(манифест_путь).read_text(encoding="utf-8"))
except (OSError, ValueError) as пр:
    print(f"{витрина}: манифест выпуска не читается ({пр}) — штамп НЕ ИЗМЕРЕН")
    raise SystemExit(0 if совпал else 1)
build_id = str(м.get("build_id") or "")
пусто = [к for к in ("artifact_sha256", "code_file_sha256", "source_commit",
                     "built_at")
         if not str(м.get(к) or "").strip()]
if build_id == "worktree-unbuilt":
    print(f"{витрина}: ШТАМПА НЕТ — build_id заглушка worktree-unbuilt, "
          f"происхождение кода не подтверждено")
elif пусто:
    print(f"{витрина}: ШТАМП НЕПОЛНЫЙ — пусты поля: {', '.join(пусто)}")
else:
    print(f"{витрина}: штамп на месте, build_id {build_id}")
raise SystemExit(0 if совпал else 1)
PY
  rc=$?
  rm -f "$vf"
  exit $rc
fi

head_sha="$(git ls-remote "$bundle" HEAD | cut -f1 | cut -c1-12)"
[ -n "$head_sha" ] || { bad "голова бандла не читается"; exit 2; }
log "выложено $old_sha, в бандле $head_sha"

if [ "$old_sha" = "$head_sha" ]; then
  log "выложена та же голова: делать нечего"
  exit 0
fi

player_src="$old_release/config/player.json"
if [ ! -f "$player_src" ]; then
  bad "в текущем выпуске нет config/player.json — служба не стартует намеренно"
  bad "publisher_id — вход владельца; подставлять чужой или выдуманный запрещено"
  exit 3
fi

if [ "$mode" = "--dry-run" ]; then
  log "сухой прогон: бандл на месте, плеер на месте, выпуск сменился бы $old_sha -> $head_sha"
  log "ничего не менялось"
  exit 0
fi

# Предполётная проверка прав. Делается ДО первой записи: отказ посреди
# выпуска оставил бы `current` переключённым, а службу — на прежнем коде.
if [ "$am_root" != 1 ]; then
  [ -w "$root" ] || { bad "нет записи в $root (нужна группа витрины и setgid)"; exit 1; }
  [ -w "$root/releases" ] || { bad "нет записи в $root/releases"; exit 1; }
  [ -r "$player_src" ] || { bad "config/player.json текущего выпуска не читается"; exit 1; }
  sudo -n -l 2>/dev/null | grep -qF "/usr/bin/systemctl restart $unit" || {
    bad "перезапуск $unit не разрешён в sudo: выпуск не начинаю"; exit 1; }
  log "права доставки проверены: запись в выпуски есть, перезапуск $unit разрешён"
fi

release="$root/releases/$head_sha"
if [ ! -d "$release" ]; then
  # Выпуск собирается, а не копируется. Прежний порядок клонировал бандл прямо
  # в каталог выпуска, и штамп манифеста не ставился никогда: измерено
  # 2026-10-18 — у всех восьми витрин узла `build_id` = `worktree-unbuilt`, а
  # `artifact_sha256`, `code_file_sha256`, `source_commit` и `built_at` пусты.
  # То есть происхождение выложенного кода ничем не подтверждалось, и
  # `runtime_digest_match` в /healthz не мог быть верным — сравнивать было
  # нечего с чем.
  #
  # Штамп ставит сборщик ВИТРИНЫ (`tools/build_release.py`) и ставит его
  # внутрь артефакта. Поэтому порядок такой: клон -> сборка -> РАСПАКОВКА
  # артефакта в каталог выпуска. Логика штампа здесь не повторяется: копия
  # разошлась бы со сборщиком, а это ровно тот случай, когда проверка зеленеет,
  # а витрина называет чужие цифры.
  work="$(mktemp -d)"
  git clone --quiet "$bundle" "$work/repo" || { bad "клон бандла не удался"; exit 1; }
  if [ ! -f "$work/repo/tools/build_release.py" ]; then
    bad "в бандле нет tools/build_release.py: выпуск без штампа происхождения не делаю"
    exit 1
  fi
  ( cd "$work/repo" && python3 tools/build_release.py --output dist ) \
    | sed 's/^/    сборка| /' \
    || { bad "сборка артефакта не удалась"; exit 1; }
  art="$(ls -1 "$work/repo/dist"/*.tar.gz 2>/dev/null | head -1)"
  [ -n "$art" ] || { bad "сборка не оставила артефакта"; exit 1; }
  mkdir -p "$release" || { bad "каталог выпуска не создаётся"; exit 1; }
  tar -xzf "$art" -C "$release" || { bad "артефакт не распаковался"; exit 1; }
  cp "$work/repo/dist/release-manifest.json" "$release/release-manifest.json" \
    || { bad "опись выпуска не перенеслась"; exit 1; }
  # Удаляется ровно созданный mktemp-каталог и только он.
  case "$work" in /tmp/*) rm -rf "$work" ;; esac
  if [ "$am_root" = 1 ]; then
    chown -R "$account:$account" "$release"
  else
    # Владелец останется за доставкой, группа — за витриной (setgid на
    # каталоге выпусков). Служба читает по группе, поэтому групповое чтение
    # ставится явно, а не предполагается по umask.
    chmod -R g+rX "$release"
  fi
  stamp_problem="$(python3 - "$release/config/template-manifest.json" <<'PY'
import json
import pathlib
import sys

try:
    д = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
except (OSError, ValueError) as пр:
    print(f"манифест выпуска не читается: {пр}")
    raise SystemExit(0)
плохо = [к for к in ("build_id", "artifact_sha256", "code_file_sha256",
                     "source_commit", "built_at")
         if not str(д.get(к) or "").strip()]
if str(д.get("build_id") or "") == "worktree-unbuilt":
    print("build_id остался заглушкой worktree-unbuilt")
elif плохо:
    print("в манифесте выпуска пусты поля: " + ", ".join(плохо))
PY
)"
  if [ -n "$stamp_problem" ]; then
    bad "штамп происхождения не проставлен: $stamp_problem"
    bad "выпуск не переключаю — непрослеживаемый код на витрину не кладу"
    exit 1
  fi
  log "выпуск $head_sha собран из артефакта, штамп происхождения на месте"
else
  log "каталог выпуска $head_sha уже существует: беру как есть"
fi

if [ "$am_root" = 1 ]; then
  install -m 0640 -o "$account" -g "$account" "$player_src" "$release/config/player.json"
else
  # `install -o/-g` требует root. Содержимое не читается и не печатается ни в
  # одном из двух путей; группа достаётся от setgid каталога выпуска.
  cp "$player_src" "$release/config/player.json" || { bad "плеер не перенёсся"; exit 3; }
  chmod 0640 "$release/config/player.json"
fi
log "плеер перенесён из прежнего выпуска (значение не читается)"

printf '%s\n' "$old_release" > "$previous_file"
[ "$am_root" = 1 ] && chown "$account:$account" "$previous_file"
ln -sfn "$release" "$current_link"
[ "$am_root" = 1 ] && chown -h "$account:$account" "$current_link"
log "current -> $release"

restart_unit "$unit"
ready=0
waited=0
while [ "$waited" -lt "$health_timeout" ]; do
  if curl -fsS --max-time 5 "127.0.0.1:$port/healthz" >/dev/null 2>&1; then ready=1; break; fi
  sleep "$health_interval"
  waited=$((waited + health_interval))
done

if [ "$ready" = 0 ]; then
  bad "витрина не ответила на healthz за $health_timeout с: возвращаю прежний выпуск"
  ln -sfn "$old_release" "$current_link"
  [ "$am_root" = 1 ] && chown -h "$account:$account" "$current_link"
  restart_unit "$unit"
  # Журнал службы доступен только root; при его отсутствии это
  # так и печатается, а не подменяется пустым выводом.
  journalctl -u "$unit" -n 20 --no-pager 2>/dev/null | sed 's/^/log| /' \
    || log "журнал службы недоступен этой учётной записи"
  exit 1
fi
log "healthz отвечает через $waited с"

# Ответ на healthz доказывает, что КТО-ТО на порту жив, — но не что это ЭТА
# витрина на ЭТОМ выпуске. Порт мог занять сосед, а служба — остаться на
# прежнем коде после неудачного рестарта: оба случая выглядят как успех, и
# сценарий объявил бы выпуск состоявшимся. Поэтому подробный ответ (его
# отдаёт только внутренний вызов по петле) сверяется с тем, что сценарий
# ТОЛЬКО ЧТО поставил.
#
# Измерено 2026-10-18 на живой витрине семейства: healthz по петле отдаёт
# `runtime_path` = /srv/<учётка>/releases/<12 знаков>/src/lords-frontend.py
# (путь после разрешения ссылок) и `release_id` = <12 знаков>-<site>. Оба
# поля называют выпуск явно, и сверять их не с чем, кроме только что
# собранного каталога.
#
# Отказ закрытый: отсутствие поля — это «подтвердить нечем», а не
# «подтверждено». Если поле однажды пропадёт, сценарий вернёт прежний выпуск
# и назовёт причину; лечится это добавлением поля в рантайм, а не снятием
# проверки.
health_file="$(mktemp)"
if ! curl -fsS --max-time 5 "127.0.0.1:$port/healthz" -o "$health_file" 2>/dev/null; then
  printf '%s\n' "подробный ответ healthz не прочитан" > "$health_file.why"
fi
identity="$(python3 - "$health_file" "$release" <<'PY'
import json
import pathlib
import sys

файл, выпуск = sys.argv[1:3]
try:
    д = json.loads(pathlib.Path(файл).read_text(encoding="utf-8"))
except (OSError, ValueError) as пр:
    print(f"ответ healthz не разобран: {пр}")
    raise SystemExit(0)
путь = str(д.get("runtime_path") or "")
# Сверяется ПУТЬ, и только он. `release_id` для этого не годится: измерено
# 2026-10-18 на восьми витринах узла — там у всех `worktree-unbuilt`, то есть
# метка сборки, а не номер выпуска, и условие по ней отвергало бы каждую
# исправную выкладку. Путь же называет выпуск прямо: у соседа на порту будет
# чужая учётная запись, у службы на прежнем коде — прежний каталог.
if not путь:
    print("в ответе нет runtime_path: подтвердить выпуск нечем")
elif not путь.startswith(выпуск.rstrip("/") + "/"):
    print(f"на порту исполняется {путь}, а выложен {выпуск}")
PY
)"
rm -f "$health_file" "$health_file.why"
if [ -n "$identity" ]; then
  bad "на порту $port не та витрина или не тот выпуск: $identity"
  bad "возвращаю прежний выпуск"
  ln -sfn "$old_release" "$current_link"
  [ "$am_root" = 1 ] && chown -h "$account:$account" "$current_link"
  restart_unit "$unit"
  exit 1
fi
log "опознано: на порту $port исполняется выпуск $head_sha этой витрины"

# Признак новой версии ищется в журнале службы, а не в файлах: файл на диске
# доказывает доставку, а строка журнала — что рантайм этот файл ИСПОЛНЯЕТ.
sync_line="$(journalctl -u "$unit" --since "-5 min" --no-pager 2>/dev/null | grep -c "согласование доступности серий" || true)"
log "строк о согласовании доступности в журнале за 5 минут: ${sync_line:-0}"

code=0
for route in "/" "/catalog/"; do
  rc=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "127.0.0.1:$port$route")
  printf '    route %-14s code=%s\n' "$route" "$rc"
  [ "$rc" = "200" ] || code=1
done
if [ "$code" != 0 ]; then
  bad "главная или каталог ответили не 200: возвращаю прежний выпуск"
  ln -sfn "$old_release" "$current_link"
  [ "$am_root" = 1 ] && chown -h "$account:$account" "$current_link"
  restart_unit "$unit"
  exit 1
fi

log "$site: выпуск $head_sha принят, прежний $old_sha остаётся на диске для отката"
log "откат вручную: ln -sfn $old_release $current_link && systemctl restart $unit"
