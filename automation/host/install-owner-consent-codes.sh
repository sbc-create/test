#!/usr/bin/env bash
# Одноразовые коды владельца для регистрации согласия ИЗ ЧАТА.
#
#   sudo bash automation/host/install-owner-consent-codes.sh            # выдать 10 кодов
#   sudo bash automation/host/install-owner-consent-codes.sh --count 20 --days 90
#   bash automation/host/install-owner-consent-codes.sh --show          # только состояние
#
# Зачем они
# ---------
#
# Согласие владельца на открытие домена живёт в каталоге root, и создаёт его
# только команда владельца: флаг в реестре разрешением не считается, потому
# что реестр доступен на запись той же учётной записи, под которой работают
# инструменты. Пока единственным способом была оболочка, выдать согласие из
# рабочего чата было нечем.
#
# Прямой инструмент моста задачу НЕ решает: мост работает от `claude`, и
# «инструмент регистрации согласия» без доказательства означал бы право модели
# выдавать разрешения себе — корневой якорь стал бы украшением.
#
# Поэтому вызов из чата несёт доказательство: код, который знает только
# владелец. Проверяет его root по своему файлу (0600, никому другому
# недоступен), и каждый код действует ОДИН раз.
#
# Что видит модель
# ----------------
#
# Код, вписанный владельцем в чат, модель видит — он пришёл ей аргументом.
# Именно поэтому код одноразовый и срочный: захваченное значение мертво сразу
# после операции, на которую владелец его и дал. На диск, доступный `claude`,
# код не попадает вовсе: в заявку кладётся отпечаток `sha256(код|домен|
# действие)`, и снятая с диска заявка не годится ни для другого домена, ни для
# другого действия.
#
# Сами коды печатаются ОДИН раз — здесь, владельцу, — и лежат в файле root.
# Иначе привязку нечем было бы проверить: из отпечатка кода её не вычислить, а
# проверяющая сторона обязана убедиться, что владелец назвал ИМЕННО этот домен
# и ИМЕННО это действие. Ни в журнал, ни в отчёт, ни в git коды не попадают.
set -Eeuo pipefail

STORE="${OWNER_CODES_STORE:-/etc/site-factory/owner-consent-codes.json}"
COUNT=10
DAYS=30
MODE="issue"

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
ok()  { printf '   \033[32mOK\033[0m   %s\n' "$*"; }
die() { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --count) COUNT="$2"; shift 2 ;;
    --days)  DAYS="$2"; shift 2 ;;
    --store) STORE="$2"; shift 2 ;;
    --show)  MODE="show"; shift ;;
    -h|--help)
      sed -n '2,40p' "$0"; exit 0 ;;
    *) die "неизвестный аргумент $1" ;;
  esac
done

if [ "$MODE" = "show" ]; then
  log "состояние хранилища кодов (сами коды не показываются никогда)"
  OWNER_CODES_STORE="$STORE" python3 - <<'PYSHOW'
import json
import os
import pathlib
import sys

sys.path.insert(0, os.environ.get("FACTORY_ROOT", "/home/claude/wt-portable-site-cell-01"))
from factory.cell import owner_codes

owner_codes.ХРАНИЛИЩЕ = pathlib.Path(os.environ["OWNER_CODES_STORE"])
print("   " + json.dumps(owner_codes.сведения(), ensure_ascii=False))
PYSHOW
  exit 0
fi

[ "$(id -u)" = 0 ] || die "нужен root: файл отпечатков принадлежит root и никому больше не доступен"
case "$COUNT" in ''|*[!0-9]*) die "--count ожидает число" ;; esac
case "$DAYS" in ''|*[!0-9]*) die "--days ожидает число" ;; esac
[ "$COUNT" -ge 1 ] && [ "$COUNT" -le 100 ] || die "--count вне 1..100"

log "1. каталог хранилища"
install -d -o root -g root -m 0700 "$(dirname "$STORE")"
ok "$(dirname "$STORE") (root:root, 0700)"

log "2. выдача кодов"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
OWNER_CODES_STORE="$STORE" CODE_COUNT="$COUNT" CODE_DAYS="$DAYS" \
  python3 - > "$TMP" <<'PYISSUE'
import datetime as dt
import hashlib
import json
import os
import secrets

сколько = int(os.environ["CODE_COUNT"])
дней = int(os.environ["CODE_DAYS"])
сейчас = dt.datetime.now(dt.timezone.utc)
до = (сейчас + dt.timedelta(days=дней)).strftime("%Y-%m-%dT%H:%M:%SZ")
алфавит = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # без похожих символов


def код() -> str:
    части = ["".join(secrets.choice(алфавит) for _ in range(5)) for _ in range(3)]
    return "oc-" + "-".join(части)


коды = []
печать = []
for н in range(1, сколько + 1):
    зн = код()
    печать.append(зн)
    коды.append({"id": f"c{н:02d}", "code": зн,
                 "sha256": hashlib.sha256(зн.encode("utf-8")).hexdigest(),
                 "valid_until": до})
хранилище = {"schema_version": 1,
             "issued_at": сейчас.strftime("%Y-%m-%dT%H:%M:%SZ"),
             "valid_until": до,
             "note": ("Одноразовые коды владельца. Файл принадлежит root и "
                      "режимом 0600 недоступен никому другому; проверяющая "
                      "сторона сверяет по нему привязку sha256(код|домен|"
                      "действие) из заявки. Потеряли коды — выдайте новые этой "
                      "же командой, прежние погаснут вместе с файлом."),
             "codes": коды}
with open(os.environ["OWNER_CODES_STORE"], "w", encoding="utf-8") as ф:
    json.dump(хранилище, ф, ensure_ascii=False, indent=2)
    ф.write("\n")
print("\n".join(печать))
PYISSUE
chown root:root "$STORE"
chmod 0600 "$STORE"
ok "$STORE (root:root, 0600) — читает только root"

log "3. КОДЫ ВЛАДЕЛЬЦА (показываются один раз, сохраните их себе)"
printf '\n'
sed 's/^/      /' "$TMP"
printf '\n'
ok "кодов выдано: $COUNT, годны до +$DAYS дней"

log "4. как ими пользоваться"
cat <<'HOWTO'
   В рабочем чате:

       register_owner_consent {"site": "<домен>", "action": "grant", "code": "oc-…"}
       register_owner_consent {"site": "<домен>", "action": "revoke", "code": "oc-…"}

   Код действует ОДИН раз. Выдача согласия и его отзыв — две операции и два
   кода. Открытие домена остаётся отдельной операцией (set_indexing_mode):
   согласие разрешает открытие, но само не открывает.
HOWTO
