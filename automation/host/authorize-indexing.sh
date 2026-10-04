#!/usr/bin/env bash
# РАЗРЕШЕНИЕ ВЛАДЕЛЬЦА на открытие ОДНОГО домена для индексации.
#
#   sudo bash /home/claude/wt-portable-site-cell-01/automation/host/authorize-indexing.sh \
#        --domain lordserials22.info
#
#   список: … --domain a.example --domain b.example   (каждый отдельно)
#   отзыв:  … --domain lordserials22.info --undo
#   показ:  … --domain lordserials22.info --show
#
# Почему это отдельная команда от root, а не поле в JSON
# -----------------------------------------------------
# Разрешение владельца жило одним полем реестра (`cells[].indexing.
# open_authorized`), и писателя у него в фабрике не было: задать его можно было
# только правкой `config/site-cells.json` руками. Но этот файл принадлежит
# учётной записи, под которой работают инструменты (`claude`, `rw-------`), —
# значит флаг в реестре НЕ доказывает, что разрешение дал владелец. Его могла
# поставить любая сторона, которой доступен файл, включая модель.
#
# Поэтому разрешение состоит из двух независимых фактов:
#
#   1. файл подтверждения в каталоге root — /var/lib/site-cells/owner-consent/
#      <домен>.json, root:root, 0444. Создать может только root, то есть
#      владелец этой командой; прочитать — кто угодно, поэтому проверка
#      работает и из инструмента, запущенного от claude;
#   2. объявление в реестре ячеек — его делает ЭТА ЖЕ команда, сохраняя все
#      остальные поля записи сайта. Руками JSON править не нужно.
#
# Проверка считает разрешение данным только при совпадении обоих. Флаг без
# подтверждения — не разрешение; подтверждение без флага — тоже.
#
# Что команда НЕ делает: не выдаёт разрешение ВЫПУСКА. Поле
# `indexing.release_permits_open` живёт в `config/site.json` выпуска, едет с
# кодом и этой командой не трогается — слои остаются раздельными.
#
# И не открывает домен. Открытие — отдельная штатная
# операция (`set_indexing_mode` / `factory.qwen indexing-set`) со своими
# предпроверками, включая РАЗРЕШЕНИЕ ВЫПУСКА, которое живёт в выпуске и этой
# командой не выдаётся. Разрешение одного домена не распространяется на другие:
# файл и запись реестра называют один домен.
#
# Имена переменных только ASCII — требование bash.
set -Eeuo pipefail

ROOT_DIR="/home/claude/wt-portable-site-cell-01"
CONSENT_DIR="/var/lib/site-cells/owner-consent"
REGISTRY="${ROOT_DIR}/config/site-cells.json"
DOMAIN=""
MODE="grant"
NOTE=""
DOMAINS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --domain) DOMAINS+=("$2"); DOMAIN="$2"; shift 2 ;;
    --note) NOTE="$2"; shift 2 ;;
    --undo) MODE="revoke"; shift ;;
    --show) MODE="show"; shift ;;
    --sync) MODE="sync"; shift ;;
    --registry) REGISTRY="$2"; shift 2 ;;
    --consent-dir) CONSENT_DIR="$2"; shift 2 ;;
    -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
    *) printf 'неизвестный аргумент: %s\n' "$1" >&2; exit 2 ;;
  esac
done

# СПИСОК ДОМЕНОВ В ОДНОМ ВЫЗОВЕ.
#
# Разрешение владельца выдаётся ОДНОМУ домену — это свойство решения, и оно не
# меняется. Меняется только число команд: требовать от владельца по команде на
# сайт значит перекладывать на человека работу, которую делает цикл. Поэтому
# `--domain` можно повторить, и каждый домен обрабатывается НЕЗАВИСИМО: отказ
# на одном не отменяет остальных, а итог перечисляет каждый с его исходом.
#
# Обход сделан повторным вызовом этого же сценария по одному домену: логика
# одного домена остаётся нетронутой, и независимость отказов получается сама.
if [ "${#DOMAINS[@]}" -gt 1 ]; then
  printf '\033[1m==>\033[0m домена в этом вызове: %s\n' "${#DOMAINS[@]}"
  EXTRA=()
  [ "$MODE" = revoke ] && EXTRA+=(--undo)
  [ "$MODE" = show ] && EXTRA+=(--show)
  [ "$MODE" = sync ] && EXTRA+=(--sync)
  [ -n "$NOTE" ] && EXTRA+=(--note "$NOTE")
  EXTRA+=(--registry "$REGISTRY" --consent-dir "$CONSENT_DIR")
  FAILED=()
  DONE=()
  for one in "${DOMAINS[@]}"; do
    printf '\n\033[1m==>\033[0m ============ %s\n' "$one"
    if bash "$0" --domain "$one" "${EXTRA[@]}"; then
      DONE+=("$one")
    else
      FAILED+=("$one")
      printf '\033[31m[x]\033[0m %s: отказ, остальные домена продолжаются\n' "$one" >&2
    fi
  done
  printf '\n\033[1m==>\033[0m ИТОГ\n'
  for one in "${DONE[@]}"; do printf '   \033[32mOK\033[0m   %s\n' "$one"; done
  for one in "${FAILED[@]}"; do printf '   \033[31m[x]\033[0m %s\n' "$one"; done
  printf '   выполнено %s, отказов %s\n' "${#DONE[@]}" "${#FAILED[@]}"
  [ "${#FAILED[@]}" = 0 ] || exit 1
  exit 0
fi

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
ok()  { printf '   \033[32mOK\033[0m   %s\n' "$*"; }
die() { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ -n "$DOMAIN" ] || die "нужен --domain: разрешение выдаётся ОДНОМУ домену"
[ -f "$REGISTRY" ] || die "нет реестра ячеек $REGISTRY"

# РЕЕСТР ОБЯЗАН БЫТЬ ОБЫЧНЫМ ФАЙЛОМ, А НЕ ССЫЛКОЙ.
#
# Команда работает от root, а файл лежит в каталоге учётной записи
# инструментов. Став ссылкой, он превратил бы две безобидные операции в
# привилегированные: `cp -a` скопировал бы ЧУЖОЙ файл (например, доступный
# только root) в каталог, который читает `claude`, а запись пошла бы не туда,
# куда адресована. Проверка стоит до первого обращения.
[ -L "$REGISTRY" ] && die "реестр $REGISTRY — символическая ссылка: команда работает от root и по ссылке не пишет"
if [ -L "${EXEC_REGISTRY:-/usr/local/lib/site-factory-cell/config/site-cells.json}" ]; then
  die "копия исполнителя — символическая ссылка: отказ"
fi

if [ "$MODE" = show ]; then
  log "подтверждение владельца для ${DOMAIN}"
  python3 - "$CONSENT_DIR" "$DOMAIN" "$REGISTRY" <<'PYSHOW'
import json
import pathlib
import sys

каталог, домен, реестр = sys.argv[1], sys.argv[2].strip().lower(), sys.argv[3]
п = pathlib.Path(каталог) / f"{домен}.json"
if п.exists():
    try:
        св = п.stat()
        print(f"   файл: {п}")
        print(f"   владелец uid={св.st_uid}, режим {oct(св.st_mode & 0o777)}")
        print("   запись:", json.dumps(json.loads(p := п.read_text(encoding='utf-8')),
                                       ensure_ascii=False)[:400])
    except (OSError, ValueError) as ош:
        print(f"   файл есть, но не читается: {type(ош).__name__}: {ош}")
else:
    print(f"   файла подтверждения нет: {п}")
данные = json.loads(pathlib.Path(реестр).read_text(encoding="utf-8"))
for я in данные.get("cells") or []:
    if str(я.get("domain", "")).lower() == домен:
        инд = я.get("indexing") or {}
        print("   реестр: open_authorized =", repr(инд.get("open_authorized")),
              "| ref =", инд.get("open_authorization_ref"),
              "| id =", инд.get("open_authorization_id"))
        break
else:
    print("   домена нет в реестре ячеек")
PYSHOW
  exit 0
fi

[ "$(id -u)" = 0 ] || die "нужен root: подтверждение владельца создаётся в каталоге root, и именно это делает его доказательством"

# Кто подтверждает: вошедшая учётная запись, а не свободный параметр.
WHO="${SUDO_USER:-}"
[ -n "$WHO" ] || WHO="root"
WHEN="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
CONSENT_ID="$(cat /proc/sys/kernel/random/uuid 2>/dev/null || date -u +%s%N)"

log "1. домен и реестр"
SITE_ID="$(python3 - "$REGISTRY" "$DOMAIN" <<'PYSITE'
import json
import pathlib
import sys

данные = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
домен = sys.argv[2].strip().lower()
for я in данные.get("cells") or []:
    if str(я.get("domain", "")).lower() == домен:
        print(я.get("site_id") or "")
        break
PYSITE
)"
[ -n "$SITE_ID" ] || die "домена ${DOMAIN} нет в реестре ячеек ${REGISTRY}: разрешение выдаётся только объявленному сайту"
ok "домен ${DOMAIN} -> ${SITE_ID}"

install -d -m 0755 -o root -g root "$CONSENT_DIR"
CONSENT_FILE="${CONSENT_DIR}/$(printf '%s' "$DOMAIN" | tr 'A-Z' 'a-z').json"

# ПЕРЕНОС ОБЪЯВЛЕНИЯ ИЗ ЯКОРЯ (--sync). Нового разрешения не выдаётся.
#
# Зачем режим. Выдача согласия идёт двумя записями: якорь в каталоге root и
# объявление в реестре. Измерено 2026-10-04 на заявке
# `lords-01-consent-grant-20261004-184926`: якорь создан (root:root 0444,
# идентификатор 9687ce8f), а шаг реестра отказал «Read-only file system» —
# служба исполнителя не имела права писать в каталог config. Осталось
# расхождение: подтверждение владельца есть, объявления нет, и одноразовый код
# уже погашен.
#
# Этот режим ничего не РЕШАЕТ: он переносит в реестр то, что владелец уже
# решил и что подтверждено якорём. Поэтому код ему не нужен и не принимается:
# нет якоря — нет и переноса. Создать разрешение этим путём невозможно.
if [ "$MODE" = sync ]; then
  log "перенос объявления из якоря согласия (нового разрешения не выдаётся)"
  CONSENT_FILE="${CONSENT_DIR}/${DOMAIN}.json"
  [ -f "$CONSENT_FILE" ] || die "якоря согласия нет ($CONSENT_FILE): переносить нечего, и выдать разрешение этот режим не может"
  [ -L "$CONSENT_FILE" ] && die "якорь согласия — символическая ссылка: отказ"
  SITE_ID="$(python3 - "$REGISTRY" "$DOMAIN" <<'PYSITE2'
import json
import sys

реестр, домен = sys.argv[1], sys.argv[2].strip().lower()
данные = json.loads(open(реестр, encoding="utf-8").read())
for я in данные.get("cells") or []:
    if str(я.get("domain", "")).lower() == домен:
        print(я.get("site_id") or "")
        break
PYSITE2
)"
  [ -n "$SITE_ID" ] || die "домена ${DOMAIN} нет в реестре ячеек ${REGISTRY}"
  # Проверка якоря делается ФУНКЦИЕЙ ФАБРИКИ, а не чтением файла: наличие
  # файла доказательством не считается — проверяются владелец, режим, схема,
  # домен и site_id.
  FACTORY_ROOT="${FACTORY_ROOT:-/home/claude/wt-portable-site-cell-01}"
  SITE_CELLS_OWNER_CONSENT_ROOT="$CONSENT_DIR" PYTHONPATH="$FACTORY_ROOT" \
    python3 - "$SITE_ID" "$DOMAIN" <<'PYVERIFY'
import sys

from factory.cell import owner_consent

site_id, домен = sys.argv[1], sys.argv[2]
ок, почему, запись = owner_consent.проверить(site_id, домен)
if not ок:
    raise SystemExit(f"якорь согласия не прошёл проверку фабрики: {почему}")
print(f"   якорь подтверждён функцией фабрики: {запись.get('id')}")
PYVERIFY
  CONSENT_ID="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8')).get('id') or '')" "$CONSENT_FILE")"
  WHO="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8')).get('by') or 'owner')" "$CONSENT_FILE")"
  WHEN="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8')).get('at') or '')" "$CONSENT_FILE")"
  [ -n "$CONSENT_ID" ] || die "в якоре нет идентификатора: переносить нечего"
  log "1. объявление в авторитетном реестре"
  cp -a "$REGISTRY" "${REGISTRY}.bak.$(date -u +%Y%m%dT%H%M%SZ)"
  python3 - "$REGISTRY" "$DOMAIN" "grant" "$CONSENT_FILE" "$CONSENT_ID" "$WHO" "$WHEN" <<'PYREG3'
import json
import os
import pathlib
import sys
import tempfile

реестр = pathlib.Path(sys.argv[1])
домен = sys.argv[2].strip().lower()
_, ссылка, ид, кем, когда = sys.argv[3:8]
данные = json.loads(реестр.read_text(encoding="utf-8"))
тронуто = 0
for я in данные.get("cells") or []:
    if str(я.get("domain", "")).lower() != домен:
        continue
    инд = я.setdefault("indexing", {})
    инд["open_authorized"] = True
    инд["open_authorization_ref"] = ссылка
    инд["open_authorization_id"] = ид
    инд["open_authorization_note"] = (
        f"разрешение владельца: {кем}, {когда}. Объявление перенесено из якоря "
        f"{ссылка} режимом --sync: нового разрешения не выдавалось")
    тронуто += 1
if тронуто != 1:
    sys.exit(f"ожидалась одна запись домена, затронуто {тронуто}")
св = реестр.stat()
with tempfile.NamedTemporaryFile("w", dir=реестр.parent, delete=False,
                                 encoding="utf-8") as врем:
    json.dump(данные, врем, ensure_ascii=False, indent=2)
    врем.write("\n")
    времянка = pathlib.Path(врем.name)
os.chown(времянка, св.st_uid, св.st_gid)
os.chmod(времянка, св.st_mode & 0o7777)
времянка.replace(реестр)
print("   реестр: объявление перенесено, desired_state не тронут")
PYREG3
  ok "авторитетный реестр согласован с якорем"
  EXEC_REGISTRY="${EXEC_REGISTRY:-/usr/local/lib/site-factory-cell/config/site-cells.json}"
  if [ -L "$EXEC_REGISTRY" ]; then
    die "копия исполнителя — символическая ссылка: отказ"
  fi
  if [ -f "$EXEC_REGISTRY" ]; then
    log "2. копия исполнителя"
    python3 - "$EXEC_REGISTRY" "$DOMAIN" "$CONSENT_FILE" "$CONSENT_ID" "$WHO" "$WHEN" <<'PYEXEC2'
import json
import os
import pathlib
import sys
import tempfile

копия = pathlib.Path(sys.argv[1])
домен = sys.argv[2].strip().lower()
ссылка, ид, кем, когда = sys.argv[3:7]
данные = json.loads(копия.read_text(encoding="utf-8"))
тронуто = 0
for я in данные.get("cells") or []:
    if str(я.get("domain", "")).lower() != домен:
        continue
    инд = я.setdefault("indexing", {})
    инд["open_authorized"] = True
    инд["open_authorization_ref"] = ссылка
    инд["open_authorization_id"] = ид
    инд["open_authorization_note"] = (
        f"разрешение владельца: {кем}, {когда}. Перенесено режимом --sync")
    тронуто += 1
if тронуто != 1:
    sys.exit(f"в копии исполнителя затронуто {тронуто} записей")
св = копия.stat()
with tempfile.NamedTemporaryFile("w", dir=копия.parent, delete=False,
                                 encoding="utf-8") as врем:
    json.dump(данные, врем, ensure_ascii=False, indent=2)
    врем.write("\n")
    времянка = pathlib.Path(врем.name)
os.chown(времянка, св.st_uid, св.st_gid)
os.chmod(времянка, св.st_mode & 0o7777)
времянка.replace(копия)
print("   копия исполнителя согласована")
PYEXEC2
    ok "копия исполнителя согласована с якорем"
  else
    log "2. корневой копии исполнителя нет ($EXEC_REGISTRY): шаг пропущен"
  fi
  log "3. журнал подтверждений"
  printf '%s\n' "$(python3 -c "
import json
print(json.dumps({'at': '$WHEN', 'op': 'sync', 'domain': '$DOMAIN',
                  'site_id': '$SITE_ID', 'by': '$WHO', 'id': '$CONSENT_ID',
                  'reason': 'объявление перенесено из якоря; нового разрешения не выдавалось'},
                 ensure_ascii=False))")" >> "${CONSENT_DIR}/journal.jsonl"
  chmod 0444 "${CONSENT_DIR}/journal.jsonl"
  ok "запись о переносе добавлена в ${CONSENT_DIR}/journal.jsonl"
  log "4. проверка фабрикой"
  SITE_CELLS_REGISTRY="$REGISTRY" SITE_CELLS_OWNER_CONSENT_ROOT="$CONSENT_DIR" \
    PYTHONPATH="${FACTORY_ROOT:-/home/claude/wt-portable-site-cell-01}" \
    python3 - "$SITE_ID" "$DOMAIN" <<'PYCHECK2'
import os
import sys

sys.path.insert(0, os.environ.get("PYTHONPATH", "").split(os.pathsep)[0])
from factory.cell import owner_consent
from factory.qwen import indexing

site_id, домен = sys.argv[1], sys.argv[2]
ок, почему, _ = owner_consent.проверить(site_id, домен)
разрешил, объявлен, пояснение = indexing.разрешение_владельца(site_id)
print(f"   якорь: {'ЕСТЬ' if ок else 'НЕТ'}; разрешение по версии фабрики: {разрешил}")
if not (ок and разрешил):
    raise SystemExit(f"согласованность не достигнута: {пояснение[:200]}")
PYCHECK2
  ok "якорь, реестр и копия исполнителя согласованы"
  exit 0
fi

if [ "$MODE" = revoke ]; then
  log "2. отзыв разрешения"
  rm -f "$CONSENT_FILE"
  python3 - "$REGISTRY" "$DOMAIN" "revoke" "" "" "" "" <<'PYREG'
import json
import pathlib
import sys
import tempfile

реестр = pathlib.Path(sys.argv[1])
домен = sys.argv[2].strip().lower()
данные = json.loads(реестр.read_text(encoding="utf-8"))
тронуто = 0
for я in данные.get("cells") or []:
    if str(я.get("domain", "")).lower() != домен:
        continue
    инд = я.setdefault("indexing", {})
    # Снимается ТОЛЬКО разрешение. Остальные поля записи сохраняются: режим,
    # пояснения, всё прочее принадлежит сайту, а не этой команде.
    инд["open_authorized"] = False
    инд.pop("open_authorization_ref", None)
    инд.pop("open_authorization_id", None)
    инд["open_authorization_note"] = "разрешение отозвано владельцем"
    тронуто += 1
if тронуто != 1:
    sys.exit(f"ожидалась одна запись домена, затронуто {тронуто}")
# Владелец, группа и режим реестра СОХРАНЯЮТСЯ. Команда работает от root, а
# файл принадлежит учётной записи инструментов (`rw-------`, claude): запись
# «по-новому» сделала бы его файлом root, и инструменты потеряли бы доступ к
# собственному реестру. Это не теория — так ломается всё, что его читает.
св = реестр.stat()
with tempfile.NamedTemporaryFile("w", dir=реестр.parent, delete=False,
                                 encoding="utf-8") as врем:
    json.dump(данные, врем, ensure_ascii=False, indent=2)
    врем.write("\n")
    времянка = pathlib.Path(врем.name)
import os as _os
_os.chown(времянка, св.st_uid, св.st_gid)
_os.chmod(времянка, св.st_mode & 0o7777)
времянка.replace(реестр)
print("   реестр: open_authorized = False, ссылки на подтверждение убраны")
PYREG
  ok "подтверждение удалено, разрешение в реестре снято"
  exit 0
fi

log "2. подтверждение владельца (каталог root)"
TMP_CONSENT="$(mktemp)"
python3 - "$DOMAIN" "$SITE_ID" "$WHO" "$WHEN" "$CONSENT_ID" "$NOTE" > "$TMP_CONSENT" <<'PYCONSENT'
import json
import sys

домен, site_id, кем, когда, ид, пояснение = sys.argv[1:7]
print(json.dumps({
    "schema_version": 1,
    "domain": домен.strip().lower(),
    "site_id": site_id,
    "authorized": True,
    "by": кем,
    "at": когда,
    "id": ид,
    "note": пояснение or ("разрешение владельца на открытие индексации этого "
                         "домена; выдано командой authorize-indexing.sh"),
    "scope": "один домен: разрешение не распространяется на другие сайты",
    "not_a_release_permission": ("разрешение ВЫПУСКА живёт в config/site.json "
                                 "выпуска и этой записью не выдаётся"),
}, ensure_ascii=False, indent=2))
PYCONSENT
install -m 0444 -o root -g root "$TMP_CONSENT" "$CONSENT_FILE"
rm -f "$TMP_CONSENT"
ok "создан ${CONSENT_FILE} (root:root, 0444)"

log "3. объявление в реестре ячеек (остальные поля сохраняются)"
cp -a "$REGISTRY" "${REGISTRY}.bak.$(date -u +%Y%m%dT%H%M%SZ)"
python3 - "$REGISTRY" "$DOMAIN" "grant" "$CONSENT_FILE" "$CONSENT_ID" "$WHO" "$WHEN" <<'PYREG2'
import json
import pathlib
import sys
import tempfile

реестр = pathlib.Path(sys.argv[1])
домен = sys.argv[2].strip().lower()
_, ссылка, ид, кем, когда = sys.argv[3:8]
данные = json.loads(реестр.read_text(encoding="utf-8"))
тронуто = 0
прежнее = None
for я in данные.get("cells") or []:
    if str(я.get("domain", "")).lower() != домен:
        continue
    инд = я.setdefault("indexing", {})
    прежнее = dict(инд)
    # Меняются ТОЛЬКО поля разрешения. `desired_state` не трогается: он
    # говорит, какой режим объявлен, и менять его — работа операции, а не
    # разрешения.
    инд["open_authorized"] = True
    инд["open_authorization_ref"] = ссылка
    инд["open_authorization_id"] = ид
    инд["open_authorization_note"] = (
        f"разрешение владельца: {кем}, {когда}. Подтверждение — файл root "
        f"{ссылка}; флаг в реестре без него разрешением не считается")
    тронуто += 1
if тронуто != 1:
    sys.exit(f"ожидалась одна запись домена, затронуто {тронуто}")
# Остальные поля записи обязаны остаться прежними: сверяем по ключам.
потеряно = sorted(set(прежнее) - set(
    [я for я in данные.get("cells") if str(я.get("domain","")).lower() == домен][0]["indexing"]))
if потеряно:
    sys.exit(f"правка потеряла поля {потеряно}: отказ")
# Владелец, группа и режим реестра СОХРАНЯЮТСЯ. Команда работает от root, а
# файл принадлежит учётной записи инструментов (`rw-------`, claude): запись
# «по-новому» сделала бы его файлом root, и инструменты потеряли бы доступ к
# собственному реестру. Это не теория — так ломается всё, что его читает.
св = реестр.stat()
with tempfile.NamedTemporaryFile("w", dir=реестр.parent, delete=False,
                                 encoding="utf-8") as врем:
    json.dump(данные, врем, ensure_ascii=False, indent=2)
    врем.write("\n")
    времянка = pathlib.Path(врем.name)
import os as _os
_os.chown(времянка, св.st_uid, св.st_gid)
_os.chmod(времянка, св.st_mode & 0o7777)
времянка.replace(реестр)
print("   open_authorized = True, ref и id записаны, desired_state не тронут")
PYREG2
ok "реестр обновлён, копия прежнего рядом (.bak.<метка>)"

# ДОСТАВКА РАЗРЕШЕНИЯ В КОРНЕВУЮ КОПИЮ ИСПОЛНИТЕЛЯ (решение D147).
#
# Исполнитель читает СВОЮ копию реестра (`/usr/local/lib/site-factory-cell/
# config/site-cells.json`, root:root): ссылаться оттуда на рабочий каталог
# нельзя — реестр задаёт учётную запись, порт, имя юнита и пути установки, и
# право записи в него равнялось бы праву решать, что поставит root.
#
# Отсюда следовала цена, измеренная 2026-10-04: разрешение, легшее в
# авторитетный реестр в 08:32:42, не дошло до копии от 07:10:34, и исполнитель
# отказал словами «indexing.open_authorized не равно true». Разрешение владельца
# доставляет эта команда — она уже работает от root и переносит ТОЛЬКО поля
# разрешения названного домена. Остальные поля копии не трогаются вовсе: ни
# порт, ни юнит, ни пути из рабочего каталога в привилегированную копию не
# попадают. Нет установленной копии — это не ошибка: исполнитель ещё не
# установлен, и разрешение попадёт в неё при установке.
EXEC_REGISTRY="${EXEC_REGISTRY:-/usr/local/lib/site-factory-cell/config/site-cells.json}"
if [ -L "$EXEC_REGISTRY" ]; then
  die "копия исполнителя $EXEC_REGISTRY — символическая ссылка: root по ссылке не пишет"
fi
if [ -f "$EXEC_REGISTRY" ]; then
  log "3б. доставка полей разрешения в корневую копию исполнителя"
  python3 - "$EXEC_REGISTRY" "$DOMAIN" "$CONSENT_FILE" "$CONSENT_ID" "$WHO" "$WHEN" <<'PYEXEC'
import json
import os
import pathlib
import sys
import tempfile

копия = pathlib.Path(sys.argv[1])
домен = sys.argv[2].strip().lower()
ссылка, ид, кем, когда = sys.argv[3:7]
данные = json.loads(копия.read_text(encoding="utf-8"))
тронуто = 0
for я in данные.get("cells") or []:
    if str(я.get("domain", "")).lower() != домен:
        continue
    инд = я.setdefault("indexing", {})
    # Ровно те же четыре поля, что и в авторитетном реестре. Ничего больше:
    # всё остальное в этой копии принадлежит установке.
    инд["open_authorized"] = True
    инд["open_authorization_ref"] = ссылка
    инд["open_authorization_id"] = ид
    инд["open_authorization_note"] = (
        f"разрешение владельца: {кем}, {когда}. Доставлено authorize-indexing.sh "
        "в корневую копию исполнителя")
    тронуто += 1
if тронуто != 1:
    sys.exit(f"в копии исполнителя ожидалась одна запись домена, затронуто {тронуто}")
св = копия.stat()
with tempfile.NamedTemporaryFile("w", dir=копия.parent, delete=False,
                                 encoding="utf-8") as врем:
    json.dump(данные, врем, ensure_ascii=False, indent=2)
    врем.write("\n")
    времянка = pathlib.Path(врем.name)
os.chown(времянка, св.st_uid, св.st_gid)
os.chmod(времянка, св.st_mode & 0o7777)
времянка.replace(копия)
print(f"   {копия}: open_authorized = True (только поля разрешения)")
PYEXEC
  ok "корневая копия исполнителя знает разрешение — переустановка не нужна"
else
  log "3б. корневой копии исполнителя нет ($EXEC_REGISTRY): шаг пропущен"
fi

log "4. журнал подтверждений (каталог root)"
printf '%s\n' "$(python3 -c "
import json, sys
print(json.dumps({'at': '$WHEN', 'op': 'grant', 'domain': '$DOMAIN',
                  'site_id': '$SITE_ID', 'by': '$WHO', 'id': '$CONSENT_ID'},
                 ensure_ascii=False))")" >> "${CONSENT_DIR}/journal.jsonl"
chmod 0444 "${CONSENT_DIR}/journal.jsonl"
ok "запись добавлена в ${CONSENT_DIR}/journal.jsonl"

log "5. проверка фабрикой (её собственной функцией)"
# Проверяются ИМЕННО те файлы, которые написала эта команда. Прежде проверка
# шла по путям по умолчанию: с `--registry`/`--consent-dir` она отвечала про
# постороннее состояние — то есть про чужие файлы, а выглядела как приёмка.
sudo -u claude env PYTHONPATH="$ROOT_DIR" \
  SITE_CELLS_REGISTRY="$REGISTRY" \
  SITE_CELLS_OWNER_CONSENT_ROOT="$CONSENT_DIR" \
  python3 - "$SITE_ID" "$DOMAIN" <<'PYCHECK'
import os
import sys

sys.path.insert(0, os.environ.get("PYTHONPATH", "").split(os.pathsep)[0]
                or "/home/claude/wt-portable-site-cell-01")
from factory.cell import owner_consent
from factory.qwen import indexing

site_id, домен = sys.argv[1], sys.argv[2]
ок, почему, _ = owner_consent.проверить(site_id, домен)
print(f"   подтверждение: {'ЕСТЬ' if ок else 'НЕТ'} — {почему}")
разрешил, объявлен, пояснение = indexing.разрешение_владельца(site_id)
print(f"   разрешение владельца по версии фабрики: {разрешил}")
print(f"   пояснение: {пояснение[:200]}")
if not (ок and разрешил):
    raise SystemExit("проверка фабрики не подтвердила разрешение")
PYCHECK
ok "фабрика видит разрешение владельца"

log "готово"
cat <<SUMMARY
   Разрешение выдано ОДНОМУ домену: ${DOMAIN} (${SITE_ID}).
   Домен этим НЕ открыт: открытие — отдельная операция с предпроверками,
   включая разрешение ВЫПУСКА (config/site.json выпуска).

   Открыть штатной операцией (она же меняет приложение, слой nginx, robots и
   карту согласованно и возвращает состояние при частичном отказе):
     python3 -m factory.qwen indexing-set --site ${DOMAIN} --mode open \\
         --expect-release <выложенный выпуск>
   в сессии Qwen — set_indexing_mode {"site": "${DOMAIN}", "mode": "open"}

   Отзыв: sudo bash $0 --domain ${DOMAIN} --undo
   Показ: sudo bash $0 --domain ${DOMAIN} --show
SUMMARY
