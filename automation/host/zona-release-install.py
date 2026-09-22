#!/usr/bin/env python3
"""Сборка и установка релиза витрины Zona — обе дороги активации сразу.

Почему обе. У витрины два пути исполнения, и они расходились: загруженный в
память юнит запускает плоский файл `zona-01-frontend.py`, а файл юнита на
диске — диспетчер, который идёт по ссылке `sites/<витрина>/current`. Пока
обновляли только один путь, `systemctl daemon-reload` молча переводил витрину
на другой код. Здесь обновляются оба, одними и теми же байтами.

Что делает:

1. собирает неизменяемый каталог `releases/<build_id>/` с рантаймом и его
   спутниками;
2. снимает резерв прежних живых байтов и сверяет его побайтово;
3. атомарно переставляет `sites/<витрина>/current`;
4. атомарно подменяет плоский файл, который исполняет загруженный юнит;
5. переписывает манифест витрины под установленные байты.

Чего НЕ делает: не перезапускает службу, не трогает DNS, TLS, robots и
индексацию, не касается чужих витрин. Перезапуск — отдельное решение.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ФРОНТ = Path("/srv/lords/.frontend")
СПУТНИКИ = ("seo_layer.py", "collection_contract.py", "genre_aliases.py",
            "popular_weekly.py", "nova_core_indexability.py",
            "community_ratings_overlay.py")


def sha256(п: Path) -> str:
    return hashlib.sha256(п.read_bytes()).hexdigest()


def атомарно(источник: Path, цель: Path) -> None:
    """Подмена через временный файл в том же каталоге и os.replace.

    Полусостояния не возникает: либо старые байты, либо новые. Запись «поверх»
    оставила бы окно, в котором файл уже неполон, а витрина уже его читает.
    """
    врем = цель.with_suffix(цель.suffix + ".new")
    shutil.copy2(источник, врем)
    os.replace(врем, цель)


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--site", default="zona-01")
    р.add_argument("--runtime", required=True, help="рантайм-кандидат из ветки")
    р.add_argument("--build-id", required=True)
    р.add_argument("--source-commit", required=True)
    р.add_argument("--design-version", default="")
    р.add_argument("--apply", action="store_true",
                   help="без него — только план и отпечатки")
    а = р.parse_args()

    кандидат = Path(а.runtime).resolve()
    if not кандидат.is_file():
        raise SystemExit(f"нет кандидата: {кандидат}")
    манифест_путь = ФРОНТ / f"template-manifest-{а.site}.json"
    if а.site == "lords-01":
        манифест_путь = ФРОНТ / "template-manifest.json"
    if not манифест_путь.is_file():
        raise SystemExit(f"нет манифеста витрины: {манифест_путь}")
    манифест = json.loads(манифест_путь.read_text(encoding="utf-8"))
    if манифест.get("template_family") != "zona":
        raise SystemExit(
            f"манифест {манифест_путь.name} объявляет семейство "
            f"{манифест.get('template_family')!r}: это не витрина Zona, "
            "установка отклонена")

    плоский = ФРОНТ / f"{а.site}-frontend.py"
    ссылка = ФРОНТ / "sites" / а.site / "current"
    релиз = ФРОНТ / "releases" / а.build_id
    метка = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    план = {
        "site": а.site, "build_id": а.build_id,
        "candidate_sha256": sha256(кандидат),
        "live_flat_sha256": sha256(плоский) if плоский.is_file() else None,
        "live_release_target": os.readlink(ссылка) if ссылка.is_symlink() else None,
        "manifest": манифест_путь.name,
        "manifest_design_version": манифест.get("design_version"),
        "release_dir": str(релиз),
    }
    if not а.apply:
        print(json.dumps({"dry_run": True, **план}, ensure_ascii=False, indent=1))
        return 0

    # 1. Резерв прежних живых байтов — цель отката.
    откат = None
    if плоский.is_file():
        (ФРОНТ / ".rollback").mkdir(exist_ok=True)
        откат = ФРОНТ / ".rollback" / f"{метка}-{а.site}-frontend-{план['live_flat_sha256'][:12]}.py"
        shutil.copy2(плоский, откат)
        if sha256(откат) != план["live_flat_sha256"]:
            raise SystemExit("резерв не сошёлся побайтово — установка отменена")

    # 2. Неизменяемый каталог релиза.
    релиз.mkdir(parents=True, exist_ok=True)
    shutil.copy2(кандидат, релиз / "lords-frontend.py")
    для_отчёта = {}
    for имя in СПУТНИКИ:
        источник = ФРОНТ / имя
        if источник.is_file():
            shutil.copy2(источник, релиз / имя)
            для_отчёта[имя] = sha256(релиз / имя)
    (релиз / "RELEASE.json").write_text(json.dumps({
        "build_id": а.build_id, "site": а.site,
        "source_commit": а.source_commit,
        "runtime_sha256": sha256(релиз / "lords-frontend.py"),
        "companions": для_отчёта, "built_at": метка,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    # 3. Ссылка релиза — атомарной перестановкой.
    ссылка.parent.mkdir(parents=True, exist_ok=True)
    if ссылка.is_symlink():
        (ссылка.parent / "PREVIOUS_TARGET.txt").write_text(
            os.readlink(ссылка), encoding="utf-8")
    врем = ссылка.parent / "current.new"
    if врем.exists() or врем.is_symlink():
        врем.unlink()
    os.symlink(os.path.relpath(релиз, ссылка.parent), врем)
    os.replace(врем, ссылка)

    # 4. Плоский файл — тот, который исполняет загруженный юнит.
    атомарно(кандидат, плоский)

    # 5. Манифест описывает установленные байты, а не прежние.
    манифест.update({
        "build_id": а.build_id,
        "source_commit": а.source_commit,
        "runtime_commit": а.source_commit,
        "code_file_sha256": sha256(плоский),
        "artifact_path": str(плоский),
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "release_dir": str(релиз),
    })
    if а.design_version:
        манифест["design_version"] = а.design_version
    if откат:
        манифест["rollback_target_file"] = str(откат)
        манифест["rollback_target_sha256"] = план["live_flat_sha256"]
    врем_м = манифест_путь.with_suffix(".json.new")
    врем_м.write_text(json.dumps(манифест, ensure_ascii=False, indent=2, sort_keys=True),
                      encoding="utf-8")
    os.replace(врем_м, манифест_путь)

    итог = {
        "applied": True, **план,
        "installed_flat_sha256": sha256(плоский),
        "installed_release_sha256": sha256(релиз / "lords-frontend.py"),
        "release_link_now": os.readlink(ссылка),
        "rollback_file": str(откат) if откат else None,
        "restart_performed": 0,
        "restart_command": f"sudo systemctl restart nova-{а.site}.service",
    }
    print(json.dumps(итог, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
