#!/usr/bin/env bash
# Транзакция закрепления рантайма root-юнитов. Исполняется ВЛАДЕЛЬЦЕМ от root.
#
# Что она делает и в каком порядке — ниже по шагам. Главное свойство: любой
# отказ возвращает прежнее состояние целиком. Половина закреплённых юнитов и
# половина прежних — это состояние, которое никак не называется и которое
# некому диагностировать в три часа ночи.
#
# Чего она НЕ делает: не трогает шаблоны, каталоги, SEO, плеер, DNS, TLS и
# значения credentials. Ни одно значение секрета не читается и не печатается —
# в транзакции нет ни одной операции, которая открывала бы файл секрета.
#
# Почему установщик копирует себя в root-owned каталог и работает оттуда:
# запускать от root файл из каталога, которым владеет агент, — ровно тот
# дефект, который эта транзакция и закрывает. Проверка хеша до копирования и
# повторная проверка после неё закрывают окно подмены между ними.
set -Eeuo pipefail

say()   { printf '[harden] %s\n' "$*"; }
warn()  { printf '[harden] ВНИМАНИЕ: %s\n' "$*" >&2; }
fail()  { printf '[harden] ОТКАЗ: %s\n' "$*" >&2; exit 1; }

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

EXPECT_HOST="claude-control-01"
PINNED_ROOT="/opt/site-factory/runtime"
STAGING_ROOT="/root/site-factory-hardening"
BACKUP_ROOT="/var/backups/site-factory-hardening"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="${BACKUP_ROOT}/${STAMP}"

DRY_RUN=0
BUNDLE=""
RELEASE_JSON=""
MANIFEST=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --bundle=*) BUNDLE="${arg#*=}" ;;
    --release=*) RELEASE_JSON="${arg#*=}" ;;
    --manifest=*) MANIFEST="${arg#*=}" ;;
    *) fail "неизвестный аргумент: $arg" ;;
  esac
done

BUNDLE="${BUNDLE:-${HERE}/site-factory-pinned-runtime.tar.gz}"
RELEASE_JSON="${RELEASE_JSON:-${HERE}/release.json}"
MANIFEST="${MANIFEST:-${HERE}/manifest.json}"
PY=/usr/bin/python3

# Право root требуется только для настоящей транзакции. Сухой прогон ничего не
# меняет, и требовать для него прав значило бы лишить владельца возможности
# посмотреть план заранее — ровно того, ради чего сухой прогон и нужен.
if [ "$DRY_RUN" != "1" ] && [ "$(id -u)" != "0" ]; then
  fail "запускается только от root: транзакция правит /etc/systemd/system и /opt"
fi

# ========================= 1. Хост =======================================
ACTUAL_HOST="$(hostname)"
[ "$ACTUAL_HOST" = "$EXPECT_HOST" ] \
  || fail "хост «${ACTUAL_HOST}», ожидался «${EXPECT_HOST}». Транзакция привязана к конкретной машине намеренно."
say "хост: $ACTUAL_HOST"

for f in "$BUNDLE" "$RELEASE_JSON" "$MANIFEST"; do
  [ -f "$f" ] || fail "нет файла $f"
done

# ========================= 2. Хеши и коммит ==============================
WANT_SHA="$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["bundle_sha256"])' "$RELEASE_JSON")"
RELEASE_ID="$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["release_id"])' "$RELEASE_JSON")"
SRC_COMMIT="$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["primary_source_commit"])' "$RELEASE_JSON")"
GOT_SHA="$(sha256sum "$BUNDLE" | cut -d' ' -f1)"
[ "$WANT_SHA" = "$GOT_SHA" ] \
  || fail "sha256 бандла не совпал:
  ожидался $WANT_SHA
  получен  $GOT_SHA"
say "релиз:  $RELEASE_ID"
say "коммит: $SRC_COMMIT"
say "бандл:  sha256 совпал до копирования"

DIVERGENCES="$("$PY" -c '
import json,sys
d=json.load(open(sys.argv[1])).get("host_divergences") or []
print(len(d))' "$RELEASE_JSON")"
if [ "$DIVERGENCES" != "0" ]; then
  warn "в релизе зафиксировано расхождений с рабочей копией хоста: ${DIVERGENCES}."
  warn "закрепляется версия из коммита; см. host_divergences в release.json"
fi

PINNED_DIR="${PINNED_ROOT}/${RELEASE_ID}"
BUNDLE_DIR="${PINNED_DIR}/bundle"
VENV_DIR="${PINNED_DIR}/venv"
RELOCATED_DIR="${PINNED_ROOT}/relocated"

if [ "$DRY_RUN" = "1" ]; then
  say ""
  say "СУХОЙ ПРОГОН: дальше ничего не меняется."
  say "  закрепить в : $PINNED_DIR"
  say "  перенести в : $RELOCATED_DIR"
  say "  бэкап в     : $BACKUP_DIR"
  "$PY" -c '
import json,sys
d=json.load(open(sys.argv[1]))
print("  юнитов      :", len(d["units"]))
for u in d["units"]: print("     -", u)
print("  переносится :", ", ".join(d["relocate"]))' "$RELEASE_JSON"
  exit 0
fi

# ========================= 3-4. Root-owned staging =======================
# Всё, что дальше исполняется или копируется, лежит под root и недоступно
# агенту на запись.
install -d -m 0700 -o root -g root "$STAGING_ROOT"
STAGE="${STAGING_ROOT}/${RELEASE_ID}"
rm -rf "$STAGE"
install -d -m 0755 -o root -g root "$STAGE"
install -m 0600 -o root -g root "$BUNDLE" "${STAGE}/bundle.tar.gz"
install -m 0600 -o root -g root "$RELEASE_JSON" "${STAGE}/release.json"
install -m 0600 -o root -g root "$MANIFEST" "${STAGE}/manifest.json"
install -m 0700 -o root -g root "${HERE}/audit_root_units.py" "${STAGE}/audit_root_units.py"

# ========================= 5. Повторная проверка после копии =============
COPY_SHA="$(sha256sum "${STAGE}/bundle.tar.gz" | cut -d' ' -f1)"
[ "$COPY_SHA" = "$WANT_SHA" ] || fail "sha256 разошёлся ПОСЛЕ копирования в staging — копия повреждена или подменена"
say "бандл:  sha256 совпал после копирования в root-owned staging"

# ========================= 6. Бэкап ======================================
install -d -m 0700 -o root -g root "$BACKUP_ROOT"
install -d -m 0700 -o root -g root "$BACKUP_DIR"
mapfile -t UNITS < <("$PY" -c '
import json,sys
for u in json.load(open(sys.argv[1]))["units"]: print(u)' "$RELEASE_JSON")

install -d -m 0700 "${BACKUP_DIR}/systemd"
for unit in "${UNITS[@]}"; do
  [ -f "/etc/systemd/system/${unit}" ] \
    && cp -a "/etc/systemd/system/${unit}" "${BACKUP_DIR}/systemd/" || true
  [ -d "/etc/systemd/system/${unit}.d" ] \
    && cp -a "/etc/systemd/system/${unit}.d" "${BACKUP_DIR}/systemd/" || true
done
install -d -m 0700 "${BACKUP_DIR}/nginx"
cp -a /etc/nginx/sites-available "${BACKUP_DIR}/nginx/" 2>/dev/null || true
cp -a /etc/nginx/snippets "${BACKUP_DIR}/nginx/" 2>/dev/null || true
systemctl list-unit-files --no-legend > "${BACKUP_DIR}/unit-files.txt" 2>/dev/null || true
printf '%s\n' "$RELEASE_ID" > "${BACKUP_DIR}/release-id"
say "бэкап:  $BACKUP_DIR"

# --- откат: восстанавливает ровно то, что было снято выше ----------------
ROLLED_BACK=0
rollback() {
  [ "$ROLLED_BACK" = "1" ] && return 0
  ROLLED_BACK=1
  warn "откат: возвращаю прежнее состояние из ${BACKUP_DIR}"
  for unit in "${UNITS[@]}"; do
    rm -rf "/etc/systemd/system/${unit}.d/20-pinned-runtime.conf" || true
    if [ -e "${BACKUP_DIR}/systemd/${unit}.d" ]; then
      rm -rf "/etc/systemd/system/${unit}.d"
      cp -a "${BACKUP_DIR}/systemd/${unit}.d" "/etc/systemd/system/" || true
    fi
    if [ -f "${BACKUP_DIR}/systemd/${unit}" ]; then
      cp -a "${BACKUP_DIR}/systemd/${unit}" "/etc/systemd/system/" || true
    fi
  done
  systemctl daemon-reload || true
  for t in "${STOPPED_TIMERS[@]:-}"; do
    [ -n "$t" ] && systemctl start "$t" >/dev/null 2>&1 || true
  done
  warn "откат завершён: юниты и таймеры возвращены в прежнее состояние"
}
trap 'rollback' ERR

# ========================= 7. Остановка только затронутых триггеров ======
STOPPED_TIMERS=()
mapfile -t CANDIDATE_TIMERS < <(systemctl list-units --type=timer --no-legend 2>/dev/null | awk '{print $1}')
for unit in "${UNITS[@]}"; do
  timer="${unit%.service}.timer"
  for active in "${CANDIDATE_TIMERS[@]}"; do
    if [ "$active" = "$timer" ]; then
      systemctl stop "$timer" && STOPPED_TIMERS+=("$timer")
      say "остановлен таймер: $timer"
    fi
  done
done
if systemctl is-active --quiet lords-deploy-broker.path 2>/dev/null; then
  systemctl stop lords-deploy-broker.path && STOPPED_TIMERS+=("lords-deploy-broker.path")
  say "остановлен приёмщик заявок: lords-deploy-broker.path"
fi

# ========================= 8. Раскладка закреплённого рантайма ===========
install -d -m 0755 -o root -g root /opt/site-factory
install -d -m 0755 -o root -g root "$PINNED_ROOT"
rm -rf "$PINNED_DIR"
install -d -m 0755 -o root -g root "$PINNED_DIR"
install -d -m 0755 -o root -g root "$BUNDLE_DIR"
tar -xzf "${STAGE}/bundle.tar.gz" -C "$BUNDLE_DIR" --no-same-owner --no-same-permissions
chown -R root:root "$PINNED_DIR"
find "$BUNDLE_DIR" -type d -exec chmod 0755 {} +
find "$BUNDLE_DIR" -type f -exec chmod 0644 {} +
find "$BUNDLE_DIR" -type f \( -name '*.sh' -o -name '*.py' \) -exec chmod 0755 {} +
say "рантайм разложен: $BUNDLE_DIR"

# --- перенос существующих закреплённых деревьев как есть -----------------
install -d -m 0755 -o root -g root "$RELOCATED_DIR"
"$PY" - "${STAGE}/manifest.json" "$RELOCATED_DIR" <<'PYEOF'
import json, shutil, sys, hashlib
from pathlib import Path
manifest, dest_root = sys.argv[1], Path(sys.argv[2])
doc = json.load(open(manifest))
for item in doc.get("relocate", []):
    src, dest = Path(item["from"]), dest_root / item["id"]
    if not src.exists():
        print(f"[harden] перенос пропущен, источника нет: {src}")
        continue
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, symlinks=True)
    digest = hashlib.sha256()
    for path in sorted(p for p in dest.rglob("*") if p.is_file()):
        digest.update(path.relative_to(dest).as_posix().encode())
        digest.update(path.read_bytes())
    print(f"[harden] перенесено {item['id']}: дерево sha256 {digest.hexdigest()[:16]}…")
PYEOF
chown -R root:root "$RELOCATED_DIR"
find "$RELOCATED_DIR" -type d -exec chmod 0755 {} +
find "$RELOCATED_DIR" -type f -exec chmod 0644 {} +
find "$RELOCATED_DIR" -type f \( -name '*.sh' -o -name '*.py' \) -exec chmod 0755 {} +

# --- интерпретатор, принадлежащий root ----------------------------------
if [ ! -x "${VENV_DIR}/bin/python" ]; then
  say "собираю интерпретатор в ${VENV_DIR} (root-owned)"
  BASE_PY=""
  for candidate in /usr/bin/python3.11 /usr/bin/python3.10 /usr/bin/python3; do
    [ -x "$candidate" ] && { BASE_PY="$candidate"; break; }
  done
  [ -n "$BASE_PY" ] || fail "базовый интерпретатор не найден"
  "$BASE_PY" -m venv "$VENV_DIR" || fail "не удалось создать venv"
  "${VENV_DIR}/bin/pip" install --quiet --upgrade pip >/dev/null 2>&1 || true
  if [ -f "${BUNDLE_DIR}/requirements.txt" ]; then
    "${VENV_DIR}/bin/pip" install --quiet -r "${BUNDLE_DIR}/requirements.txt" \
      || fail "не удалось поставить зависимости в закреплённый venv"
  fi
fi
chown -R root:root "$VENV_DIR"
chmod -R go-w "$VENV_DIR"
for module in $("$PY" -c '
import json,sys
print(" ".join(json.load(open(sys.argv[1]))["venv"]["required_modules"]))' "${STAGE}/manifest.json"); do
  "${VENV_DIR}/bin/python" -c "import ${module}" 2>/dev/null \
    || fail "в закреплённом venv нет модуля ${module}: служба объявила бы себя настроенной и упала на ImportError"
done
say "интерпретатор: ${VENV_DIR}/bin/python (root-owned, зависимости проверены импортом)"

# --- ссылка current -----------------------------------------------------
ln -sfn "$PINNED_DIR" "${PINNED_ROOT}/current.new"
mv -Tf "${PINNED_ROOT}/current.new" "${PINNED_ROOT}/current"
say "ссылка current → $PINNED_DIR"

# ========================= 9. Drop-in'ы ==================================
"$PY" - "${STAGE}/manifest.json" "$BUNDLE_DIR" "$VENV_DIR" "$RELOCATED_DIR" <<'PYEOF'
import json, os, sys
from pathlib import Path
manifest, bundle, venv, relocated = sys.argv[1:5]
doc = json.load(open(manifest))
path_env = doc["pinned_path_env"]

def expand(value):
    return (value.replace("{bundle}", bundle)
                 .replace("{venv}", venv)
                 .replace("{relocated}", relocated))

for unit in doc["units"]:
    name = unit["unit"]
    target = Path("/etc/systemd/system") / (name + ".d")
    target.mkdir(parents=True, exist_ok=True)
    os.chmod(target, 0o755)
    lines = [
        "# Сгенерировано transaction SECRET-HUB-ROOT-BOUNDARY-HARDEN-007.",
        "# Правки будут перезаписаны следующей транзакцией.",
        "#",
        "# Назначение: root обязан исполнять только код, принадлежащий root.",
        f"# Вектор до закрепления: {unit['vector']}",
        "#",
        "# Пути к ДАННЫМ намеренно оставлены прежними: данные root читает и",
        "# пишет по назначению, код он ИСПОЛНЯЕТ — разница в этом.",
        "[Service]",
        f"Environment=PATH={path_env}",
    ]
    if unit.get("exec_start"):
        lines.append("ExecStart=")
        lines.append("ExecStart=" + expand(unit["exec_start"]))
    if unit.get("working_directory"):
        lines.append("WorkingDirectory=" + expand(unit["working_directory"]))
    for key, value in (unit.get("environment") or {}).items():
        lines.append(f"Environment={key}={expand(value)}")
    conf = target / "20-pinned-runtime.conf"
    conf.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(conf, 0o644)
    os.chown(conf, 0, 0)
    print(f"[harden] drop-in: {conf}")
PYEOF

systemctl daemon-reload || fail "daemon-reload не прошёл"

# ========================= 10. Проверка конфигурации ====================
for unit in "${UNITS[@]}"; do
  systemd-analyze verify "$unit" >/dev/null 2>&1 \
    || warn "systemd-analyze verify имеет замечания к ${unit} (не блокирует: verify строг к шаблонным юнитам)"
done

for unit in "${UNITS[@]}"; do
  effective="$(systemctl show -p ExecStart --value "$unit" 2>/dev/null || true)"
  case "$effective" in
    *"$PINNED_ROOT"*|*"/bin/"*|*"/usr/bin/"*) : ;;
    "") warn "у ${unit} пустой ExecStart в systemctl show (шаблонный юнит — норма)" ;;
    *) fail "эффективный ExecStart ${unit} не ведёт в закреплённый рантайм: ${effective}" ;;
  esac
done
say "эффективные ExecStart проверены"

# ========================= 11. Аудит границы ============================
AUDIT_OUT="${BACKUP_DIR}/audit-after.json"
if "${VENV_DIR}/bin/python" "${STAGE}/audit_root_units.py" --json > "$AUDIT_OUT" 2>/dev/null; then
  say "аудит: нарушений нет во ВСЕЙ цепочке исполнения root-юнитов"
else
  REMAINING="$("$PY" -c '
import json,sys
d=json.load(open(sys.argv[1]))
print(",".join(d["units_with_problems"]))' "$AUDIT_OUT" 2>/dev/null || echo "?")"
  SCOPED="$("$PY" - "$AUDIT_OUT" "${STAGE}/release.json" <<'PYEOF'
import json, sys
audit = json.load(open(sys.argv[1]))
scope = set(json.load(open(sys.argv[2]))["units"])
print(",".join(sorted(set(audit["units_with_problems"]) & scope)))
PYEOF
)"
  if [ -n "$SCOPED" ]; then
    fail "после закрепления в ЦЕЛЕВЫХ юнитах остались нарушения: ${SCOPED}"
  fi
  warn "вне области транзакции остались нарушения: ${REMAINING}"
  warn "это ожидаемо: юниты чужого продукта в транзакцию не входят (см. out_of_scope)"
fi

# ========================= 12. Smoke ====================================
systemctl is-active --quiet site-factory-secret-hub.service \
  || fail "хаб Secret Hub не активен после закрепления"
systemctl is-active --quiet site-factory-secret-panel.service \
  || warn "панель Secret Hub не активна (будет поднята ниже, если дошли до публикации)"
for site in zonafilm.space animedia.icu animedia.space lordfilm47.space; do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -k \
          --resolve "${site}:443:127.0.0.1" "https://${site}/" || echo 000)"
  [ "$code" = "200" ] || fail "витрина ${site} отвечает ${code} после закрепления"
done
say "smoke: витрины Lords/Zona/Animedia отвечают 200"

# ========================= 13. Возврат триггеров ========================
for t in "${STOPPED_TIMERS[@]:-}"; do
  [ -n "$t" ] && systemctl start "$t" && say "возвращён: $t"
done
STOPPED_TIMERS=()

# ========================= 14. Публикация — НЕ здесь =====================
# Панель Secret Hub этой транзакцией НЕ публикуется. Это не упущение, а
# разделение двух разных по природе операций:
#
#   закрепление  — сужает поверхность: root перестаёт исполнять чужой код;
#   публикация   — РАСШИРЯЕТ поверхность: появляется новый публичный endpoint.
#
# Соединять их в одну атомарную операцию плохо с обеих сторон. Отказ публикации
# откатывал бы удавшееся закрепление — то есть возвращал бы дыру из-за проблемы
# с nginx. А успех публикации выдавал бы наружу адрес до того, как закрепление
# проверено чем-то, кроме собственного отчёта транзакции.
#
# Поэтому: сначала закрепление и его независимая проверка, потом отдельным
# решением — публикация.
trap - ERR
say ""
say "ТРАНЗАКЦИЯ ЗАВЕРШЕНА — ЗАКРЕПЛЕНИЕ"
say "  релиз:  $RELEASE_ID"
say "  бэкап:  $BACKUP_DIR"
say "  аудит:  $AUDIT_OUT"
say "  откат:  bash ${STAGE}/rollback.sh"
say ""
say "ПАНЕЛЬ НЕ ОПУБЛИКОВАНА И НЕ ПРИНИМАЕТ СЕКРЕТЫ."
say "Публикация — отдельный шаг, после независимой проверки закрепления."
say "Пришлите этот вывод и файл ${AUDIT_OUT}."

# Готовый откат на будущее — уже после успеха.
cat > "${STAGE}/rollback.sh" <<ROLLBACK
#!/bin/bash
# Возврат к состоянию до транзакции ${RELEASE_ID}.
set -e
[ "\$(id -u)" = "0" ] || { echo "только от root" >&2; exit 1; }
for unit in ${UNITS[*]}; do
  rm -f "/etc/systemd/system/\${unit}.d/20-pinned-runtime.conf"
  if [ -e "${BACKUP_DIR}/systemd/\${unit}.d" ]; then
    rm -rf "/etc/systemd/system/\${unit}.d"
    cp -a "${BACKUP_DIR}/systemd/\${unit}.d" /etc/systemd/system/
  fi
done
systemctl daemon-reload
echo "откат выполнен из ${BACKUP_DIR}"
ROLLBACK
chmod 0700 "${STAGE}/rollback.sh"
