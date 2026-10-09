#!/usr/bin/env bash
# Узкая установка исполнителя ячеек из зафиксированного пакета.
#
#   sudo bash automation/host/install-executor-narrow.sh --package <каталог пакета> --expect-digest <64 hex>
#
# Что делает — и только это
# -------------------------
#   1. сверяет пакет с описью и с ожидаемым digest;
#   2. переносит пакет в root-владение (/var/lib/site-cells/packages/<id>) и
#      сверяет перенесённую копию ещё раз: дальше всё читается ТОЛЬКО из неё,
#      подающая учётная запись источник изменить не может;
#   3. проверяет, что установка не потеряет поля разрешений, записанные в
#      корневую копию реестра командами владельца (indexing, owner_consent,
#      release): при расхождении — отказ ДО изменений. Отказ печатает ОБА
#      значения и готовый ключ согласия
#      `--accept-registry-change <ячейка>.<поле>=<цифра было>-><цифра пакета>`:
#      согласие привязано к измеренной паре значений, поэтому вчерашняя команда
#      не примет сегодняшнее другое расхождение, а для `release` принимается
#      только снятие удержания с записанным основанием (hold_history.evidence);
#   4. снимает резервную копию того, что меняет: /usr/local/lib/site-factory-cell
#      целиком (в tar) — и больше ничего не меняет;
#   5. заменяет корневую копию factory/, schemas/, config/ и пишет
#      cell-install.json (те же шаги и та же форма, что install-cell-executor.sh);
#   6. проверяет результат: check-installed.py (полный вывод в журнал, код
#      обязан быть 0 и итог — «полностью совпадает»), package_id и
#      site_repos_root, наличие установки обработчика обновлений, импорт
#      исполнителя и сверка обработчиков (factory cell updater-check, только чтение).
#
# Чего НЕ делает (в отличие от install-cell-executor.sh и unblock-transfer.sh)
#   * не переподключает upstream nginx ни одной витрины и не трогает теневые
#     конфигурации nginx;
#   * не ставит юниты ячеек (кандидатов AnimeGo в том числе) и не трогает
#     drop-in nova-daily-refresh;
#   * не переписывает юнит site-cell-executor.service: если он в пакете не тот
#     же, что установлен, — отказ, решение принимается отдельно.
#
# Откат: tar -C / -xzf <журнал>/before.tgz (печатается в конце и пишется в
# журнал); прежняя копия также остаётся рядом как /usr/local/lib/site-factory-cell.prev.
set -Eeuo pipefail

package=""; expect=""; accept=""
while [ $# -gt 0 ]; do
  case "$1" in
    --package) package="${2:-}"; shift ;;
    --expect-digest) expect="${2:-}"; shift ;;
    # Согласие владельца на ОДНО названное расхождение реестра: ячейка, поле и
    # ОБА значения. Общего «принять расхождения» здесь нет сознательно: такой
    # ключ нельзя прочитать как решение, а молча принятое разрешение — это
    # потерянное разрешение. Можно повторять для нескольких полей.
    --accept-registry-change) accept="${accept}${accept:+ }${2:-}"; shift ;;
    *) echo "неизвестный аргумент: $1" >&2; exit 2 ;;
  esac
  shift
done
[ -n "$package" ] && [ -n "$expect" ] || { echo "нужны --package и --expect-digest" >&2; exit 2; }

# Пути переопределяются только для проверки сценария на стенде (CELL_NARROW_SANDBOX=1).
DEST="${CELL_NARROW_DEST:-/usr/local/lib/site-factory-cell}"
STAGE_ROOT="${CELL_NARROW_STAGE:-/var/lib/site-cells/packages}"
UNIT_DIR="${CELL_NARROW_UNIT_DIR:-/etc/systemd/system}"
LOG_ROOT="${CELL_NARROW_LOG:-/var/backups/site-factory-cell}"
SANDBOX="${CELL_NARROW_SANDBOX:-0}"
PY=/usr/bin/python3

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
die() { printf '\033[31m[ОТКАЗ]\033[0m %s\n' "$*" >&2; exit 1; }
[ "$SANDBOX" = 1 ] || [ "$(id -u)" = 0 ] || die "нужен root"

T="$(date -u +%Y%m%dT%H%M%SZ)"
JOURNAL="$LOG_ROOT/$T"
install -d -m 0700 "$JOURNAL"
exec > >(tee -a "$JOURNAL/install.log") 2>&1
log "журнал: $JOURNAL/install.log"

log "1. пакет и ожидаемый digest"
package="$(cd -- "$package" && pwd)"
pkg_id="$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["package_id"])' "$package/manifest.json")"
digest="$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["digest"])' "$package/manifest.json")"
[ "$digest" = "$expect" ] || die "digest описи $digest не равен ожидаемому $expect"
"$PY" "$package/tree/automation/host/freeze-package.py" --check "$package" || die "пакет не совпал с описью"

log "2. перенос пакета под root и повторная сверка"
staged="$STAGE_ROOT/$pkg_id"
install -d -m 0755 "$STAGE_ROOT"
rm -rf "$staged.new"
cp -a "$package" "$staged.new"
if [ "$SANDBOX" != 1 ]; then chown -R root:root "$staged.new"; fi
chmod -R go-w "$staged.new"
rm -rf "$staged"; mv "$staged.new" "$staged"
"$PY" "$staged/tree/automation/host/freeze-package.py" --check "$staged" || die "перенесённая копия не совпала с описью"
[ "$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["digest"])' "$staged/manifest.json")" = "$expect" ] \
  || die "digest перенесённой копии не равен ожидаемому"
SRC="$staged/tree"
repos_root="$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["site_repos_root"])' "$staged/manifest.json")"
commit="$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["commit"])' "$staged/manifest.json")"
[ -f "$repos_root/factory/cell/executor.py" ] || die "site_repos_root описи не похож на фабрику: $repos_root"
[ -d "$repos_root/var/site-repos" ] || die "в site_repos_root нет var/site-repos: $repos_root — заявки всех ячеек были бы отвергнуты"

log "3. защита постоянных данных и установка обработчика в пакете"
[ -f "$SRC/factory/cell/protected.py" ] || die "в пакете нет factory/cell/protected.py"
grep -q "protected.проверить_выпуск" "$SRC/factory/cell/executor.py" || die "executor.py не вызывает protected.проверить_выпуск"
grep -q "protected.проверить_запись" "$SRC/factory/cell/privileged.py" || die "privileged.py не вызывает protected.проверить_запись"
grep -q "установить_обработчик" "$SRC/factory/cell/privileged.py" || die "в пакете нет установки обработчика обновлений"
cmp -s "$SRC/automation/host/site-cell-executor.service" "$UNIT_DIR/site-cell-executor.service" \
  || die "юнит site-cell-executor.service в пакете отличается от установленного — узкая установка его не меняет"
"$PY" -c "import sys; sys.path.insert(0, sys.argv[1]); from factory.cell import executor, queue, updater_units" "$SRC" \
  || die "пакет не импортируется"

log "4. поля разрешений корневого реестра не теряются"
if [ -f "$DEST/config/site-cells.json" ]; then
  "$PY" - "$DEST/config/site-cells.json" "$SRC/config/site-cells.json" "$accept" \
      > "$JOURNAL/registry-change.txt" 2>&1 <<'PYKEEP' && rc_r=0 || rc_r=$?
import hashlib, json, sys

было = {c["site_id"]: c for c in json.load(open(sys.argv[1], encoding="utf-8"))["cells"]}
стало = {c["site_id"]: c for c in json.load(open(sys.argv[2], encoding="utf-8"))["cells"]}
согласие = set(sys.argv[3].split()) if len(sys.argv) > 3 and sys.argv[3].strip() else set()
ПОЛЯ = ("indexing", "owner_consent", "release")


def цифра(значение) -> str:
    """Короткий отпечаток значения: им согласие привязывается к ИЗМЕРЕННОЙ паре."""
    сырое = json.dumps(значение, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(сырое.encode("utf-8")).hexdigest()[:12]


def основание(поле, старое, новое) -> str:
    """Чем расхождение обосновано в самом пакете. Пусто — значит ничем.

    Для `release` основание — запись `hold_history` с непустым `evidence`:
    снятие удержания без записанного основания принимать нельзя даже с
    согласием, иначе причина снятия исчезает вместе с прежним значением.
    """
    if поле != "release":
        return "основание в этом поле не требуется"
    снимается = bool((старое or {}).get("hold")) and not (новое or {}).get("hold")
    if not снимается:
        return "основание в этом поле не требуется"
    журнал = [з for з in ((новое or {}).get("hold_history") or [])
              if isinstance(з, dict) and str(з.get("evidence") or "").strip()]
    if not журнал:
        return ""
    п = журнал[-1]
    return (f"hold_history[-1]: снято {п.get('lifted_at')} "
            f"{п.get('lifted_by')} — {str(п.get('evidence'))[:400]}")


беды, принято = [], []
for site, c in было.items():
    if site not in стало:
        беды.append(f"{site}: ячейки нет в пакете")
        continue
    for поле in ПОЛЯ:
        старое, новое = c.get(поле), стало[site].get(поле)
        if старое == новое:
            continue
        токен = f"{site}.{поле}={цифра(старое)}->{цифра(новое)}"
        описание = (f"{site}.{поле}: установлено "
                    f"{json.dumps(старое, ensure_ascii=False)[:300]} != пакет "
                    f"{json.dumps(новое, ensure_ascii=False)[:300]}")
        if токен not in согласие:
            беды.append(описание + f"\n        согласие владельца: "
                        f"--accept-registry-change {токен}")
            continue
        чем = основание(поле, старое, новое)
        if not чем:
            беды.append(описание + "\n        согласие названо, но в пакете нет "
                        "записанного основания (release.hold_history с evidence): "
                        "снятие удержания без основания не принимается")
            continue
        принято.append(описание + f"\n        принято владельцем ({токен})\n"
                       f"        основание: {чем}")

for б in беды:
    print("   [отказ]", б)
for п in принято:
    print("   [принято]", п)
print(f"   ячеек сверено: {len(было)}, расхождений: {len(беды) + len(принято)}, "
      f"из них принято владельцем: {len(принято)}")
sys.exit(1 if беды else 0)
PYKEEP
  cat "$JOURNAL/registry-change.txt"
  [ "$rc_r" -eq 0 ] || die "установка потеряла бы разрешения корневого реестра (см. выше)"
fi

log "5. резервная копия"
if [ -d "$DEST" ]; then
  tar -C "$(dirname "$DEST")" -czf "$JOURNAL/before.tgz" "$(basename "$DEST")"
  log "   $JOURNAL/before.tgz"
fi
cat > "$JOURNAL/ROLLBACK.txt" <<EOF
Откат узкой установки $T (пакет $pkg_id):
  rm -rf "$DEST" && tar -C "$(dirname "$DEST")" -xzf "$JOURNAL/before.tgz"
Юниты, nginx и данные сайтов этой установкой не менялись.
EOF

log "6. замена корневой копии"
rm -rf "$DEST.new"; mkdir -p "$DEST.new"
cp -a "$SRC/factory" "$DEST.new/factory"
cp -a "$SRC/schemas" "$DEST.new/schemas"
cp -a "$SRC/config" "$DEST.new/config"
if [ "$SANDBOX" != 1 ]; then chown -R root:root "$DEST.new"; fi
chmod -R go-w "$DEST.new"
rm -rf "$DEST.prev"
[ -d "$DEST" ] && mv "$DEST" "$DEST.prev"
mv "$DEST.new" "$DEST"
"$PY" - "$DEST/cell-install.json" "$repos_root" "$pkg_id" "$digest" "$commit" "$SRC" <<'PYWRITE'
import json, sys
from datetime import datetime, timezone
путь, repos, pid, digest, commit, src = sys.argv[1:7]
json.dump({"site_repos_root": repos,
           "installed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "package_id": pid, "package_digest": digest, "package_commit": commit,
           "code_source": src, "installed_by": "install-executor-narrow.sh"},
          open(путь, "w", encoding="utf-8"), ensure_ascii=False, indent=2, sort_keys=True)
open(путь, "a", encoding="utf-8").write("\n")
PYWRITE
chmod 0644 "$DEST/cell-install.json"

log "7. проверка результата"
failed=0
# check-installed.py сверяет ИМЕННО /usr/local/lib/site-factory-cell; на стенде
# этот шаг проверяет свою копию теми же правилами.
if [ "$SANDBOX" = 1 ]; then
  "$PY" - "$DEST" "$staged/manifest.json" > "$JOURNAL/check-installed.txt" 2>&1 <<'PYSAND' && rc=0 || rc=$?
import hashlib, json, sys
from pathlib import Path
dest, m = Path(sys.argv[1]), json.load(open(sys.argv[2]))
плохо = [o for o, h in m["files"].items() if o.startswith(("factory/", "schemas/", "config/"))
         and (not (dest / o).is_file() or hashlib.sha256((dest / o).read_bytes()).hexdigest() != h)]
print("отличается или отсутствует:", плохо[:10])
print("ИТОГ: установленное полностью совпадает с зафиксированным пакетом." if not плохо else "ИТОГ: расхождения")
sys.exit(1 if плохо else 0)
PYSAND
else
  (cd "$repos_root" && "$PY" "$SRC/automation/host/check-installed.py" --package "$staged") \
    > "$JOURNAL/check-installed.txt" 2>&1 && rc=0 || rc=$?
fi
cat "$JOURNAL/check-installed.txt"
if [ "$rc" -ne 0 ] || ! grep -q "полностью совпадает с зафиксированным пакетом" "$JOURNAL/check-installed.txt"; then
  echo "   [нет] check-installed: код $rc, полного совпадения нет"; failed=1
else
  echo "   [ок] check-installed: код 0, полное совпадение"
fi
if "$PY" - "$DEST/cell-install.json" "$pkg_id" "$repos_root" <<'PYID'; then echo "   [ок] package_id и site_repos_root"; else failed=1; fi
import json, sys
c = json.load(open(sys.argv[1]))
ok = c.get("package_id") == sys.argv[2] and c.get("site_repos_root") == sys.argv[3]
print("   cell-install.json:", c.get("package_id"), c.get("site_repos_root"))
sys.exit(0 if ok else 1)
PYID
if (cd /tmp && "$PY" -c "
import sys; sys.path.insert(0, sys.argv[1])
from factory.cell import privileged, updater_units, executor, queue
assert hasattr(privileged, 'установить_обработчик') and hasattr(privileged, 'сверить_обработчик')
print('   установленная копия импортируется, установка обработчика на месте')" "$DEST"); then
  echo "   [ок] исполнитель импортируется"
else
  echo "   [нет] исполнитель не импортируется"; failed=1
fi
# Работоспособность исполнителя — только чтением: сверка обработчиков из
# установленной копии проходит реестр, привилегированный модуль и юниты
# systemd. Разбор очереди (`cell serve`) здесь не запускается даже сухим:
# пришедшая в эту минуту чужая заявка была бы обработана.
(cd /tmp && PYTHONPATH="$DEST" "$PY" -m factory cell updater-check) \
  > "$JOURNAL/updater-check.json" 2>&1 && rc_u=0 || rc_u=$?
if "$PY" - "$JOURNAL/updater-check.json" <<'PYU'; then echo "   [ок] исполнитель отвечает: сверка обработчиков выполнена (код $rc_u)"; else echo "   [нет] сверка обработчиков не выполнилась, см. $JOURNAL/updater-check.json"; failed=1; fi
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except ValueError:
    print(open(sys.argv[1]).read()[-500:]); sys.exit(1)
for s in d["sites"]:
    print(f"   {s.get('site_id')}: согласован={s.get('согласован')} план={(s.get('plan') or {}).get('действие')} {s.get('error','')}")
sys.exit(0 if d["sites"] and not any(s.get("error") for s in d["sites"]) else 1)
PYU
echo
if [ "$failed" -ne 0 ]; then
  # Неподтверждённая копия не остаётся работать: исполнитель разбирает очередь
  # раз в минуту, и заявка, пришедшая сейчас, исполнялась бы непроверенным кодом.
  if [ -d "$DEST.prev" ]; then
    rm -rf "$DEST.failed"; mv "$DEST" "$DEST.failed"; mv "$DEST.prev" "$DEST"
    echo "УСТАНОВКА НЕ ПОДТВЕРЖДЕНА: прежняя копия возвращена, отвергнутая — $DEST.failed"
  else
    echo "УСТАНОВКА НЕ ПОДТВЕРЖДЕНА. Откат: $(sed -n 2p "$JOURNAL/ROLLBACK.txt")"
  fi
  exit 4
fi
echo "УСТАНОВЛЕНО: $pkg_id (коммит ${commit:0:12}). Журнал: $JOURNAL. Откат: $JOURNAL/ROLLBACK.txt"
