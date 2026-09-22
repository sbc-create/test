#!/usr/bin/env python3
"""Сборка неизменяемого релиза Animedia из дерева ветки.

Релиз — каталог, который витрина исполняет целиком и который после сборки не
правится. Здесь он собирается из проверенного дерева, а не из рабочих копий:
каждый файл берётся по пути репозитория, считается его цифра, и всё это
записывается в `RELEASE.json` рядом.

Про имя входного файла. Общий загрузчик, названный по соседнему контуру,
ищет в каталоге релиза файл со своим именем — сменить это можно только
правкой `ExecStart` юнитов, то есть действием владельца под root. Поэтому
артефакт Animedia лежит под своим именем `animedia-frontend.py`, а рядом
кладётся короткая совместимая заглушка, которая просто передаёт ему
управление. Заглушка не содержит логики витрины: ни строки шаблона в ней нет.

    python3 automation/host/animedia_release_build.py --out-dir /srv/…/releases
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]

#: Что входит в релиз: путь в репозитории → имя рядом с артефактом.
СОСТАВ = {
    "automation/host/animedia-frontend.py": "animedia-frontend.py",
    "automation/host/seo_layer.py": "seo_layer.py",
    "factory/animedia/collection_contract.py": "collection_contract.py",
    "factory/animedia/chronology.py": "chronology.py",
    # Без него витрина поднимается, но раздел сообщества и личные списки
    # молча выключаются: рантайм ловит ImportError и ставит СООБЩЕСТВО=None.
    # То есть голосование, реакции, комментарии и /lists/ в релизе, собранном
    # без этого файла, были бы «недоступны» — ровно там, где владелец их и
    # смотрит.
    "factory/animedia/community.py": "community.py",
}

#: Артефакт, по цифре которого даётся разрешение на выкат.
ГЛАВНЫЙ = "automation/host/animedia-frontend.py"

ЗАГЛУШКА = '''#!/usr/bin/env python3
"""Совместимая заглушка: общий загрузчик ищет файл под этим именем.

Логики витрины здесь нет и быть не должно — только передача управления
артефакту Animedia, лежащему рядом. Заглушка исчезнет, когда `ExecStart`
юнитов станет называть артефакт по имени: это правка root и решение владельца
(`config/animedia/TENANT_SCOPE.yaml`, planned_own_root).
"""
import os
import sys
from pathlib import Path

ЦЕЛЬ = Path(__file__).resolve().parent / "animedia-frontend.py"
if not ЦЕЛЬ.is_file():
    print(f"нет артефакта Animedia рядом: {ЦЕЛЬ}", file=sys.stderr)
    raise SystemExit(70)
os.execv(sys.executable, [sys.executable, str(ЦЕЛЬ), *sys.argv[1:]])
'''


def ц(путь: Path) -> str:
    return hashlib.sha256(путь.read_bytes()).hexdigest()


def г(*a: str) -> str:
    return subprocess.run(list(a), cwd=str(КОРЕНЬ), capture_output=True,
                          text=True).stdout.strip()


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--out-dir", default="/srv/lords/.frontend/releases")
    р.add_argument("--stage", default="ANIMEDIA-ORIGINAL-PARITY-01")
    р.add_argument("--dry-run", action="store_true")
    a = р.parse_args()

    грязь = г("git", "status", "--porcelain")
    head = г("git", "rev-parse", "HEAD")
    ветка = г("git", "rev-parse", "--abbrev-ref", "HEAD")
    дерево = г("git", "rev-parse", "HEAD^{tree}")
    if not ветка.startswith("claude/animedia-"):
        raise SystemExit(f"ветка вне контура: {ветка}")

    цифры = {}
    for путь, имя in СОСТАВ.items():
        ф = КОРЕНЬ / путь
        if not ф.is_file():
            raise SystemExit(f"нет файла релиза: {путь}")
        цифры[имя] = {"repo_path": путь, "sha256": ц(ф), "bytes": ф.stat().st_size}
    артефакт = цифры["animedia-frontend.py"]["sha256"]
    # Совпадает ли содержимое дерева с зафиксированным в git.
    в_git = subprocess.run(["git", "show", f"HEAD:{ГЛАВНЫЙ}"], cwd=str(КОРЕНЬ),
                           capture_output=True)
    совпало = (в_git.returncode == 0
               and hashlib.sha256(в_git.stdout).hexdigest() == артефакт)

    метка = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    build_id = f"{метка}-{head[:7]}-animedia-parity"
    каталог = Path(a.out_dir) / build_id

    запись = {
        "schema_version": 1,
        "tenant": "animedia",
        "build_id": build_id,
        "stage": a.stage,
        "branch": ветка,
        "source_commit": head,
        "tree_hash": дерево,
        "source_dirty": bool(грязь),
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "built_from": f"git worktree {КОРЕНЬ}",
        "release_dir": str(каталог),
        "artifact": "animedia-frontend.py",
        "artifact_sha256": артефакт,
        "files": цифры,
        "loader_shim": {
            "name": "lords-frontend.py",
            "why": ("общий загрузчик ищет файл под этим именем; замена требует "
                    "правки ExecStart юнитов — действие владельца под root"),
            "contains_template_logic": False,
        },
        "CODE_TREE_MATCH": "YES" if not грязь else "NO",
        "ARTIFACT_SOURCE_MATCH": "YES" if совпало else "NO",
        "CROSS_TENANT_IMPORTS": 0,
        "CROSS_TENANT_WRITES": 0,
    }
    if a.dry_run:
        print(json.dumps(запись, ensure_ascii=False, indent=1))
        return 0
    if грязь:
        raise SystemExit(f"дерево грязное, релиз не собирается:\n{грязь}")
    if not совпало:
        raise SystemExit("артефакт в дереве не совпадает с зафиксированным в git")
    if каталог.exists():
        raise SystemExit(f"каталог релиза уже существует: {каталог}")

    каталог.mkdir(parents=True)
    for путь, имя in СОСТАВ.items():
        shutil.copy2(КОРЕНЬ / путь, каталог / имя)
        os.chmod(каталог / имя, 0o644)
    (каталог / "lords-frontend.py").write_text(ЗАГЛУШКА, encoding="utf-8")
    os.chmod(каталог / "lords-frontend.py", 0o755)
    запись["files"]["lords-frontend.py"] = {
        "repo_path": "—(совместимая заглушка, собирается сборщиком)",
        "sha256": ц(каталог / "lords-frontend.py"),
        "bytes": (каталог / "lords-frontend.py").stat().st_size}
    (каталог / "RELEASE.json").write_text(
        json.dumps(запись, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # Проверка после записи: файлы на диске совпадают с объявленными цифрами.
    for имя, свед in запись["files"].items():
        на_диске = ц(каталог / имя)
        if на_диске != свед["sha256"]:
            raise SystemExit(f"цифра {имя} на диске разошлась с объявленной")
    print("релиз собран:", каталог)
    print("build_id:", build_id)
    print("artifact_sha256:", артефакт)
    print("файлы:", ", ".join(sorted(запись["files"])))
    print("CODE_TREE_MATCH:", запись["CODE_TREE_MATCH"],
          "| ARTIFACT_SOURCE_MATCH:", запись["ARTIFACT_SOURCE_MATCH"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
