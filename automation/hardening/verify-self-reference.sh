#!/usr/bin/env bash
# Подтверждение самоссылки: содержимое коммита совпадает с тем, по чему
# посчитан провенанс.
#
# Манифест объявляет источник как «SELF» — тот самый коммит, в котором он
# лежит. Хеша этого коммита во время сборки ещё не существует, поэтому
# провенанс считается по рабочему дереву. Это законно ровно при одном условии:
# дерево и коммит совпадают. Здесь оно и проверяется — после коммита, по
# фактическому содержимому объектов git.
#
# Без этой проверки самоссылка была бы обещанием: «мы посчитали то же самое,
# что зафиксировали». Обещание такого рода не отличается от ошибки.
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "${HERE}/../.." && pwd)"
PROVENANCE="${1:-${HERE}/release/provenance.json}"
COMMIT="${2:-HEAD}"

say()  { printf '[self] %s\n' "$*"; }
fail() { printf '[self] ОТКАЗ: %s\n' "$*" >&2; exit 1; }

[ -f "$PROVENANCE" ] || fail "нет провенанса $PROVENANCE"
FULL="$(git -C "$REPO" rev-parse "${COMMIT}^{commit}")" || fail "не разрешить коммит $COMMIT"

python3 - "$PROVENANCE" "$REPO" "$FULL" <<'PYEOF'
import hashlib, json, subprocess, sys

provenance, repo, commit = sys.argv[1], sys.argv[2], sys.argv[3]
files = json.load(open(provenance, encoding="utf-8"))["files"]

selfrefs = [f for f in files if f["source_commit"] == "SELF"]
if not selfrefs:
    print("[self] в провенансе нет записей SELF — проверять нечего")
    raise SystemExit(0)

bad, checked = [], 0
for item in selfrefs:
    blob = subprocess.run(
        ["git", "-C", repo, "show", f"{commit}:{item['path']}"],
        capture_output=True, check=False)
    if blob.returncode != 0:
        bad.append(f"{item['path']}: отсутствует в коммите {commit[:12]}")
        continue
    got = hashlib.sha256(blob.stdout).hexdigest()
    checked += 1
    if got != item["sha256"]:
        bad.append(f"{item['path']}: в коммите {got[:16]}…, в провенансе {item['sha256'][:16]}…")

if bad:
    print(f"[self] ОТКАЗ: содержимое коммита {commit[:12]} разошлось с провенансом:",
          file=sys.stderr)
    for line in bad[:10]:
        print(f"  {line}", file=sys.stderr)
    print("[self] Провенанс нужно пересобрать и закоммитить заново.", file=sys.stderr)
    raise SystemExit(1)

print(f"[self] самоссылка подтверждена: {checked} файлов коммита {commit[:12]} "
      f"совпали с провенансом")
PYEOF

say "SOURCE_COMMIT = TRANSACTION_COMMIT = INSTALLER_COMMIT = PROVENANCE_COMMIT = MANIFEST_COMMIT = ${FULL}"
