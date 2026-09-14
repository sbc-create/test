#!/usr/bin/env bash
# Манифест закреплённого релиза: перечень файлов, их sha256 и коммит-источник.
#
# Архива здесь нет намеренно. Прежняя версия собирала tar и делала его хеш
# якорем доверия — и упёрлась в правило репозитория «архивы в git не хранятся»
# (`tests/unit/test_repo_hygiene.py`). Правило верное, и обходить его не нужно:
# текстовый манифест с пофайловым sha256 — якорь строго сильнее.
#
#   tar даёт ОДИН хеш: сошёлся — «наверное, всё в порядке», не сошёлся —
#   непонятно, какой файл виноват;
#   манифест даёт хеш НА КАЖДЫЙ файл: установщик проверяет их поштучно и
#   называет конкретный путь, если что-то разошлось.
#
# Установщик не распаковывает архив, а выкладывает файлы `git archive` прямо из
# названных коммитов и сверяет каждый. Содержимое коммита адресуется его
# хешем, поэтому подменить его, не сменив хеш, нельзя.
#
# Запускается НЕ от root и ничего на хосте не меняет.
set -Eeuo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "${HERE}/../.." && pwd)"
MANIFEST="${HERE}/manifest.json"
OUT_DIR="${HARDENING_OUT:-${HERE}/release}"

ACCEPT_DIVERGENCE=0
for arg in "$@"; do
  case "$arg" in
    --accept-host-divergence) ACCEPT_DIVERGENCE=1 ;;
    *) printf '[release] неизвестный аргумент: %s\n' "$arg" >&2; exit 2 ;;
  esac
done

say()  { printf '[release] %s\n' "$*"; }
fail() { printf '[release] ОТКАЗ: %s\n' "$*" >&2; exit 1; }

command -v git >/dev/null 2>&1 || fail "git не найден"
[ -f "$MANIFEST" ] || fail "нет манифеста $MANIFEST"
PYTHON="${HARDENING_PYTHON:-python3}"

mkdir -p "$OUT_DIR"

"$PYTHON" - "$MANIFEST" "$REPO" "$OUT_DIR" "$ACCEPT_DIVERGENCE" <<'PYEOF'
import hashlib, json, subprocess, sys
from pathlib import Path

manifest_path, repo, out_dir, accept = sys.argv[1], sys.argv[2], Path(sys.argv[3]), sys.argv[4] == "1"
doc = json.load(open(manifest_path, encoding="utf-8"))


def git(*args) -> bytes:
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, check=True).stdout


files, divergences = [], []

for source in doc["sources"]:
    self_ref = source["commit"] == "SELF"
    if self_ref:
        # «SELF» — коммит, которым эта работа будет зафиксирована. Его хеша
        # ещё не существует, поэтому содержимое берётся из рабочего дерева, а
        # совпадение дерева с будущим коммитом подтверждается сверкой ПОСЛЕ
        # коммита (`--verify-self`). Без этой сверки самоссылка была бы
        # обещанием, а не свойством.
        full = "SELF"
        listing = git("ls-files", "--", *source["paths"]).decode().split()
    else:
        full = git("rev-parse", source["commit"] + "^{commit}").decode().strip()
        # Перечень файлов берётся из коммита, а не из рабочего дерева: дерево
        # может быть изменено, и собранный из него релиз не соответствовал бы
        # никакому отсмотренному состоянию.
        listing = git("ls-tree", "-r", "--name-only", full, "--", *source["paths"]).decode().split()

    if not listing:
        raise SystemExit(f"[release] ОТКАЗ: в источнике {full[:12]} нет ни одного из путей")

    for path in sorted(listing):
        blob = (Path(repo, path).read_bytes() if self_ref
                else git("show", f"{full}:{path}"))
        files.append({
            "path": path,
            "sha256": hashlib.sha256(blob).hexdigest(),
            "bytes": len(blob),
            "source_commit": full,
        })

    # Сверка с рабочей копией там, где манифест этого требует.
    for path, host in (source.get("verify_host_copies") or {}).items():
        want = hashlib.sha256(git("show", f"{full}:{path}")).hexdigest()
        try:
            got = hashlib.sha256(Path(host).read_bytes()).hexdigest()
        except OSError as exc:
            raise SystemExit(f"[release] ОТКАЗ: не прочитать {host}: {exc}")
        if want == got:
            print(f"[release] сверено с хостом: {path}")
            continue
        divergences.append({"path": path, "host_path": host, "pinned_commit": full,
                            "pinned_sha256": want, "host_sha256": got})
        if not accept:
            raise SystemExit(
                f"[release] ОТКАЗ: {path} на хосте разошёлся с коммитом {full[:12]}.\n"
                f"[release]   Закреплять непроверенные байты нельзя, а ждать чужую\n"
                f"[release]   незавершённую правку бесконечно — тоже.\n"
                f"[release]   Осознанное решение: --accept-host-divergence")
        print(f"[release] ПРИНЯТО РАСХОЖДЕНИЕ: {path}")

# Совокупный отпечаток: по отсортированным парам (путь, sha256). Он не заменяет
# пофайловую проверку, а служит коротким именем релиза.
aggregate = hashlib.sha256()
for item in sorted(files, key=lambda f: f["path"]):
    aggregate.update(item["path"].encode())
    aggregate.update(item["sha256"].encode())
digest = aggregate.hexdigest()

primary = doc["sources"][0]
primary_full = ("SELF" if primary["commit"] == "SELF"
                else git("rev-parse", primary["commit"] + "^{commit}").decode().strip())
# Имя релиза не может содержать хеш ещё не созданного коммита, поэтому при
# самоссылке оно строится только из совокупного отпечатка содержимого. Это и
# честнее: релиз определяется тем, что в нём лежит.
release_id = (f"self-{digest[:16]}" if primary_full == "SELF"
              else f"{primary_full[:12]}-{digest[:12]}")

(out_dir / "provenance.json").write_text(
    json.dumps({"file_count": len(files), "files": sorted(files, key=lambda f: f["path"])},
               ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

(out_dir / "release.json").write_text(json.dumps({
    "release_id": release_id,
    "aggregate_sha256": digest,
    "primary_source_commit": primary_full,
    "sources": [{"commit": ("SELF" if s["commit"] == "SELF"
                            else git("rev-parse", s["commit"] + "^{commit}").decode().strip()),
                 "ref": s.get("ref", ""), "note": s["note"]} for s in doc["sources"]],
    "file_count": len(files),
    "pinned_root": doc["release"]["pinned_root"],
    "units": [u["unit"] for u in doc["units"]],
    "relocate": [r["id"] for r in doc["relocate"]],
    "host_divergences": divergences,
    "host_divergence_note": (
        "Рабочая копия на хосте разошлась с отсмотренным коммитом: закрепляется "
        "версия коммита. Владеющая сессия обязана закоммитить правку, после чего "
        "манифест пересобирается." if divergences else ""),
    "note": ("Архива нет намеренно: установщик выкладывает файлы git archive из "
             "названных коммитов и сверяет каждый по provenance.json. Значений "
             "секретов в перечне нет — только код и конфигурация."),
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(f"[release] release_id : {release_id}")
print(f"[release] файлов     : {len(files)}")
print(f"[release] совокупный : {digest}")
print(f"[release] манифест   : {out_dir}/release.json")
PYEOF
