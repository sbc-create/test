#!/usr/bin/env python3
"""Собирает артефакт починки и owner packet под него. Ничего не выкладывает.

Правки этапа сверки изменили исходник витрины, а разрешение владельца
`ZONA-INDEPENDENT-REPAIR-DEPLOY-20260920-01` выдано на другой digest —
`75b84a4d…`. Разрешение не переносится на новый код: владелец соглашался на
конкретный артефакт, а не на будущие изменения.

Поэтому здесь собирается новый неизменяемый артефакт, считаются его digest'ы,
проверяется распаковка и готовится пакет для владельца — с откатом на то, что
сейчас действительно работает на живом. Старый пакет B17 откатывался на
`5fb6295c…`, который с 20 сентября уже не является живым; откатывать на него
значило бы вернуть витрину на две версии назад.

Запуск: python3 scripts/reconciliation/build_repair_artifact.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/zona-reconciliation-artifact"
EV = ROOT / "artifacts/evidence/cursor-work-reconciliation-01"

#: Тот же состав файлов, что у артефакта B17: витрина плюс два её модуля.
FILES = [
    "automation/host/lords-frontend.py",
    "automation/host/genre_aliases.py",
    "automation/host/collection_contract.py",
]

#: Что сейчас живёт на zonafilm.space — цель отката, а не прошлый артефакт B17.
LIVE_ARTIFACT = "75b84a4d686a381a9e9ddbd2b9038d4e6590f95730a65706accb9a521c738fc7"
LIVE_BUILD = "20260920T212359Z-39dc16ed-nova"
LIVE_SOURCE_HEAD = "39dc16ede9490160adfc4719cecc0f5b8c026799"

CONTRACT_DIGEST = "1bcfd44734c8cc4041fa6f5a9b28ac9169ceba41dd2f08494b5236043c6fe017"


def sh(*args: str) -> str:
    return subprocess.check_output(list(args), cwd=ROOT, text=True).strip()


def blob(head: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{head}:{path}"], cwd=ROOT)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    EV.mkdir(parents=True, exist_ok=True)

    head = sh("git", "rev-parse", "HEAD")
    грязно = sh("git", "status", "--porcelain")
    if грязно:
        print("рабочее дерево не чисто — артефакт собирался бы не из того, "
              f"что лежит в истории:\n{грязно}")
        return 1

    art = OUT / f"zona-01-frontend-{head[:12]}.tar.gz"
    subprocess.check_call(
        ["git", "archive", "--format=tar.gz", f"--output={art}", head, "--", *FILES],
        cwd=ROOT,
    )
    art_sha = hashlib.sha256(art.read_bytes()).hexdigest()

    digests = [hashlib.sha256(blob(head, f)).hexdigest() for f in FILES]
    code_tree = hashlib.sha256("\n".join(digests).encode()).hexdigest()
    built_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Учение по распаковке: пакет, который не разворачивается, не артефакт.
    with tempfile.TemporaryDirectory() as td:
        with tarfile.open(art, "r:gz") as tf:
            tf.extractall(td)
        for f in FILES:
            извлечён = Path(td) / f
            if not извлечён.is_file():
                print(f"в архиве нет {f}")
                return 1
            если_бы = hashlib.sha256(blob(head, f)).hexdigest()
            if hashlib.sha256(извлечён.read_bytes()).hexdigest() != если_бы:
                print(f"распакованный {f} не совпал с историей")
                return 1

    manifest = {
        "schema_version": 1,
        "template_family": "zona",
        "design_version": "1.2.0",
        "source_commit": head,
        "build_id": f"zona-reconciliation-{head[:12]}",
        "artifact_sha256": art_sha,
        "code_tree_digest": code_tree,
        "profile": "zona-01",
        "built_at": built_at,
        "artifact_path": str(art.relative_to(ROOT)),
        "contract_digest": CONTRACT_DIGEST,
        "expected_indexability": "noindex,nofollow",
        "files": FILES,
        "domain": "zonafilm.space",
        "service_name": "nova-zona-01",
        "supersedes_build": LIVE_BUILD,
        "supersedes_artifact_sha256": LIVE_ARTIFACT,
    }
    man_path = OUT / "template-manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    man_sha = hashlib.sha256(man_path.read_bytes()).hexdigest()
    (OUT / "ARTIFACT.sha256").write_text(f"{art_sha}  {art.name}\n", encoding="utf-8")
    (OUT / "MANIFEST.sha256").write_text(
        f"{man_sha}  template-manifest.json\n", encoding="utf-8")
    (OUT / "CODE_TREE.sha256").write_text(f"{code_tree}  files\n", encoding="utf-8")

    packet = {
        "STAGE": "SITE-FACTORY-CURSOR-WORK-RECONCILIATION-01",
        "ARTIFACT_SOURCE_HEAD": head,
        "ARTIFACT_SHA256": art_sha,
        "MANIFEST_SHA256": man_sha,
        "CODE_TREE_DIGEST": code_tree,
        "ARTIFACT_PATH": str(art.relative_to(ROOT)),
        "BUILT_AT": built_at,
        "DOMAIN": "zonafilm.space",
        "PROFILE": "zona-01",
        "SERVICE_NAME": "nova-zona-01",
        "DEPLOY_SCOPE": "zona-01-only",
        "EXPECTED_INDEXABILITY": "noindex,nofollow",
        "INDEXABILITY_MUTATIONS_ALLOWED": 0,
        "ROLLBACK_TARGET_ARTIFACT": LIVE_ARTIFACT,
        "ROLLBACK_TARGET_BUILD": LIVE_BUILD,
        "ROLLBACK_TARGET_SOURCE_HEAD": LIVE_SOURCE_HEAD,
        "ROLLBACK_NOTE": (
            "Откат возвращает то, что работает на живом сейчас, а не артефакт "
            "B17 5fb6295c — тот перестал быть живым 20 сентября."
        ),
        "OWNER_DEPLOY_APPROVAL_ID": None,
        "DEPLOY_AUTHORIZED": False,
        "DEPLOY_PERFORMED": 0,
        "WHY_APPROVAL_REQUIRED": (
            "Разрешение ZONA-INDEPENDENT-REPAIR-DEPLOY-20260920-01 выдано на "
            f"артефакт {LIVE_ARTIFACT[:16]}… и на него не распространяется."
        ),
        "CHANGES_SINCE_LIVE": [
            "поиск: отбор кандидатов вместо перебора каталога (p95 3825 → 99.7 ms)",
            "главная: время поступления показывается с минутами",
            "обрезка и прокрутка объявлены разметкой для машинного аудита",
            "пустой раздел без фильтров назван своим именем",
            "страница 400 получила выход навигацией",
            "карточки animedia получили доступное имя",
        ],
    }
    (EV / "OWNER_DEPLOY_PACKET.json").write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "ARTIFACT_SOURCE_HEAD": head,
        "ARTIFACT_SHA256": art_sha,
        "MANIFEST_SHA256": man_sha,
        "CODE_TREE_DIGEST": code_tree,
        "RESTORE_DRILL": "PASS",
        "DEPLOY_AUTHORIZED": False,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
