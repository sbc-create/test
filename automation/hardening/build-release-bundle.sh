#!/usr/bin/env bash
# Сборка неизменяемого бандла закреплённого рантайма из отсмотренных коммитов.
#
# Запускается НЕ от root и ничего на хосте не меняет: читает git, пишет один
# tar и один манифест в var/. Установщик потом сверит их хеши уже от root.
#
# Детерминированность здесь не эстетика, а условие проверяемости: владелец
# должен иметь возможность пересобрать бандл из тех же коммитов и получить тот
# же SHA-256. Поэтому у tar фиксируются владелец, группа, права, порядок файлов
# и время модификации — иначе хеш менялся бы от запуска к запуску и не значил
# бы ничего.
set -Eeuo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "${HERE}/../.." && pwd)"
MANIFEST="${HERE}/manifest.json"
OUT_DIR="${HARDENING_OUT:-${REPO}/var/hardening}"

# Рабочая копия на хосте может разойтись с отсмотренным коммитом — например,
# потому что её прямо сейчас правит другая сессия. Молча закрепить такие байты
# нельзя: смысл закрепления в том, что исполняется отсмотренный код. Молча
# отказаться тоже нельзя — тогда чужая незавершённая правка блокирует починку
# прав навсегда. Поэтому расхождение требует явного признания и попадает в
# манифест релиза обоими хешами.
ACCEPT_DIVERGENCE=0
for arg in "$@"; do
  case "$arg" in
    --accept-host-divergence) ACCEPT_DIVERGENCE=1 ;;
    *) printf '[bundle] неизвестный аргумент: %s\n' "$arg" >&2; exit 2 ;;
  esac
done
export ACCEPT_DIVERGENCE
DIVERGENCE_LOG="$(mktemp)"
trap 'rm -f "$DIVERGENCE_LOG"' EXIT
export DIVERGENCE_LOG

say()  { printf '[bundle] %s\n' "$*"; }
fail() { printf '[bundle] ОТКАЗ: %s\n' "$*" >&2; exit 1; }

command -v git >/dev/null 2>&1 || fail "git не найден"
[ -f "$MANIFEST" ] || fail "нет манифеста $MANIFEST"

PYTHON="${HARDENING_PYTHON:-python3}"
command -v "$PYTHON" >/dev/null 2>&1 || fail "интерпретатор $PYTHON не найден"

# Эпоха для mtime всех файлов бандла. Значение фиксированное и намеренно не
# «сейчас»: время сборки не является свойством содержимого.
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1700000000}"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE" "$DIVERGENCE_LOG"' EXIT

say "репозиторий: $REPO"
say "манифест:    $MANIFEST"

# --- 1. Выкладка файлов из каждого коммита-источника ----------------------
# `git archive` берёт содержимое ИЗ КОММИТА, а не из рабочего дерева. Это
# принципиально: рабочее дерево может быть изменено, и собранный из него бандл
# не соответствовал бы никакому отсмотренному состоянию.
SOURCE_COUNT="$("$PYTHON" -c '
import json,sys
print(len(json.load(open(sys.argv[1]))["sources"]))' "$MANIFEST")"

index=0
while [ "$index" -lt "$SOURCE_COUNT" ]; do
  commit="$("$PYTHON" -c '
import json,sys
print(json.load(open(sys.argv[1]))["sources"][int(sys.argv[2])]["commit"])' "$MANIFEST" "$index")"

  # Полный sha: короткий в манифесте удобен человеку, но в провенанс обязан
  # уйти однозначный идентификатор.
  full="$(git -C "$REPO" rev-parse "${commit}^{commit}")" \
    || fail "коммит $commit не найден в репозитории"

  mapfile -t paths < <("$PYTHON" -c '
import json,sys
for p in json.load(open(sys.argv[1]))["sources"][int(sys.argv[2])]["paths"]:
    print(p)' "$MANIFEST" "$index")

  say "источник ${full:0:12}: ${#paths[@]} путей"
  for path in "${paths[@]}"; do
    git -C "$REPO" cat-file -e "${full}:${path}" 2>/dev/null \
      || fail "в коммите ${full:0:12} нет пути ${path}"
    # Каталог или файл — `git archive` разбирает оба случая одинаково.
    git -C "$REPO" archive --format=tar "$full" -- "$path" | tar -x -C "$STAGE" \
      || fail "не удалось выложить ${path} из ${full:0:12}"
  done

  # Сверка с рабочей копией на хосте там, где манифест этого требует: файл,
  # которого нет в ветке задачи, обязан совпадать с тем, что реально работает,
  # иначе «закрепили проверенное» было бы неправдой.
  "$PYTHON" - "$MANIFEST" "$index" "$REPO" "$full" <<'PYEOF'
import hashlib, json, os, subprocess, sys
manifest, index, repo, full = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
accept = os.environ.get("ACCEPT_DIVERGENCE") == "1"
log = os.environ.get("DIVERGENCE_LOG", "")
src = json.load(open(manifest))["sources"][index]
for path, host in (src.get("verify_host_copies") or {}).items():
    blob = subprocess.run(["git", "-C", repo, "show", f"{full}:{path}"],
                          capture_output=True, check=True).stdout
    want = hashlib.sha256(blob).hexdigest()
    try:
        got = hashlib.sha256(open(host, "rb").read()).hexdigest()
    except OSError as exc:
        print(f"[bundle] ОТКАЗ: не прочитать {host}: {exc}", file=sys.stderr)
        raise SystemExit(1)
    if want == got:
        print(f"[bundle] сверено с хостом: {path} == {want[:16]}…")
        continue
    message = (f"{path}: закрепляется версия коммита {full[:12]} ({want[:16]}…), "
               f"а на хосте сейчас лежит другая ({got[:16]}…)")
    if log:
        with open(log, "a", encoding="utf-8") as handle:
            json.dump({"path": path, "host_path": host, "pinned_commit": full,
                       "pinned_sha256": want, "host_sha256": got}, handle,
                      ensure_ascii=False)
            handle.write("\n")
    if not accept:
        print(f"[bundle] ОТКАЗ: {message}\n"
              f"[bundle]   Закреплять непроверенные байты нельзя, а ждать чужую "
              f"незавершённую правку бесконечно — тоже.\n"
              f"[bundle]   Осознанное решение: --accept-host-divergence "
              f"(расхождение попадёт в манифест релиза и в отчёт).",
              file=sys.stderr)
        raise SystemExit(1)
    print(f"[bundle] ПРИНЯТО РАСХОЖДЕНИЕ: {message}")
PYEOF

  index=$((index + 1))
done

# --- 2. Провенанс: sha256 каждого файла и коммит, из которого он пришёл ----
say "считаю провенанс"
"$PYTHON" - "$STAGE" "$MANIFEST" "$REPO" > "${STAGE}/.provenance.json" <<'PYEOF'
import hashlib, json, subprocess, sys
from pathlib import Path
stage, manifest, repo = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
doc = json.load(open(manifest))

origin = {}
for src in doc["sources"]:
    full = subprocess.run(["git", "-C", repo, "rev-parse", src["commit"] + "^{commit}"],
                          capture_output=True, text=True, check=True).stdout.strip()
    listing = subprocess.run(["git", "-C", repo, "ls-tree", "-r", "--name-only", full,
                              "--", *src["paths"]],
                             capture_output=True, text=True, check=True).stdout.split()
    for name in listing:
        origin[name] = full

files = []
for path in sorted(p for p in stage.rglob("*") if p.is_file()):
    rel = str(path.relative_to(stage))
    if rel.startswith("."):
        continue
    files.append({
        "path": rel,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_commit": origin.get(rel, "UNKNOWN"),
    })
unknown = [f["path"] for f in files if f["source_commit"] == "UNKNOWN"]
if unknown:
    print(f"[bundle] ОТКАЗ: файлы без провенанса: {unknown[:5]}", file=sys.stderr)
    raise SystemExit(1)
json.dump({"file_count": len(files), "files": files}, sys.stdout,
          ensure_ascii=False, indent=1, sort_keys=True)
PYEOF

# --- 3. Детерминированный tar --------------------------------------------
mkdir -p "$OUT_DIR"
BUNDLE="${OUT_DIR}/site-factory-pinned-runtime.tar.gz"
say "собираю $BUNDLE"

# --sort=name и фиксированные owner/mtime дают воспроизводимый архив.
# gzip -n убирает из заголовка имя и время — иначе они попадают в хеш.
tar --sort=name \
    --mtime="@${SOURCE_DATE_EPOCH}" \
    --owner=0 --group=0 --numeric-owner \
    --format=gnu \
    -C "$STAGE" -cf - . \
  | gzip -n -9 > "$BUNDLE"

BUNDLE_SHA="$(sha256sum "$BUNDLE" | cut -d' ' -f1)"
cp "${STAGE}/.provenance.json" "${OUT_DIR}/provenance.json"

# --- 4. Итоговый манифест релиза -----------------------------------------
"$PYTHON" - "$MANIFEST" "$BUNDLE" "$BUNDLE_SHA" "$REPO" "${OUT_DIR}/provenance.json" \
    "$DIVERGENCE_LOG" > "${OUT_DIR}/release.json" <<'PYEOF'
import hashlib, json, subprocess, sys
manifest, bundle, bundle_sha, repo, provenance, divergence = sys.argv[1:7]
doc = json.load(open(manifest))
prov = json.load(open(provenance))

divergences = []
try:
    for line in open(divergence, encoding="utf-8"):
        line = line.strip()
        if line:
            divergences.append(json.loads(line))
except OSError:
    pass

sources = []
for src in doc["sources"]:
    full = subprocess.run(["git", "-C", repo, "rev-parse", src["commit"] + "^{commit}"],
                          capture_output=True, text=True, check=True).stdout.strip()
    sources.append({"commit": full, "ref": src.get("ref", ""), "note": src["note"]})

primary = sources[0]["commit"]
release_id = f"{primary[:12]}-{bundle_sha[:12]}"

json.dump({
    "release_id": release_id,
    "bundle": bundle,
    "bundle_sha256": bundle_sha,
    "primary_source_commit": primary,
    "sources": sources,
    "file_count": prov["file_count"],
    "pinned_root": doc["release"]["pinned_root"],
    "units": [u["unit"] for u in doc["units"]],
    "relocate": [r["id"] for r in doc["relocate"]],
    "host_divergences": divergences,
    "host_divergence_note": (
        "Рабочая копия на хосте разошлась с отсмотренным коммитом: закрепляется "
        "версия коммита. Владеющая сессия обязана закоммитить свою правку, после "
        "чего бандл пересобирается — иначе после установки будет исполняться не "
        "то, что сейчас лежит на хосте." if divergences else ""),
    "note": ("Бандл детерминирован: та же пара коммитов даёт тот же sha256. "
             "Значений секретов в нём нет — только код и конфигурация."),
}, sys.stdout, ensure_ascii=False, indent=2)
PYEOF

RELEASE_ID="$("$PYTHON" -c '
import json,sys; print(json.load(open(sys.argv[1]))["release_id"])' "${OUT_DIR}/release.json")"

say ""
say "готово"
say "  release_id : $RELEASE_ID"
say "  бандл      : $BUNDLE"
say "  sha256     : $BUNDLE_SHA"
say "  файлов     : $("$PYTHON" -c '
import json,sys; print(json.load(open(sys.argv[1]))["file_count"])' "${OUT_DIR}/release.json")"
say "  манифест   : ${OUT_DIR}/release.json"
