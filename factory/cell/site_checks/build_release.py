#!/usr/bin/env python3
"""Сборка установочного пакета с воспроизводимым digest.

В архив не попадает ничего переменного: порядок файлов задан, времена обнулены,
владелец обезличен, режим канонизирован. Git хранит у файла ровно один бит прав;
остальное берётся из umask сборщика, и без нормализации один коммит давал разный
digest у разработчика и на раннере CI — digest отвечал бы на вопрос «кто
собирал», а не «то же ли это самое».
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "__pycache__", "dist", "data", "var"}
SKIP_FILES = {"config/player.json"}


def files() -> list:
    """Файлы артефакта — те, что ведёт Git, и только они.

    Обход файловой системы клал в артефакт всё, что лежит в рабочем каталоге:
    не только отслеживаемое, но и игнорируемое. Два следствия, оба живые.

    Первое: digest переставал быть функцией коммита. Один и тот же коммит,
    собранный в рабочем каталоге и в рабочей копии исполнителя, дал
    `0e068b87d274` и `e8976b9ca670` — разница была в каталоге `.claude/`,
    который Git игнорирует. Исполнитель сверяет digest заявки со своей
    пересборкой, то есть такой выпуск он бы отверг, и правильно.

    Второе, тише и хуже: `checks/no_secrets.py` проверяет ИНДЕКС Git, а
    сборщик паковал РАБОЧИЙ КАТАЛОГ. Проверка и артефакт говорили о разном, и
    любой посторонний файл рядом с проектом уезжал в выпуск; единственным
    исключением был `config/player.json`, названный поимённо, — то есть
    защита держалась на списке известных имён.
    """
    вывод = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", "--cached"],
                           capture_output=True, check=True).stdout
    out = []
    for имя in вывод.split(b"\0"):
        rel = имя.decode("utf-8")
        if not rel or rel in SKIP_FILES:
            continue
        if any(part in SKIP_DIRS for part in Path(rel).parts):
            continue
        p = ROOT / rel
        if p.is_file():
            out.append(p)
    return sorted(out, key=lambda p: str(p.relative_to(ROOT)))


#: Поля манифеста, которые обязана проставить СБОРКА. В репозитории они пусты
#: намеренно: заполненное здесь значение пережило бы свой выпуск и продолжило
#: бы называть его цифры.
#:
#: Каждое отвечает на свой вопрос, и подменять один ответ другим нельзя:
#:
#:   source_commit      откуда взят ЗАКРЕПЛЁННЫЙ РАНТАЙМ (репозиторий-
#:                      производитель). Берётся из pins.lock.json, а не из
#:                      манифеста: тогда объявленное происхождение не может
#:                      разойтись с тем, что проверяет verify_pins.
#:   site_repo_commit   коммит ЭТОГО репозитория — версия самого сайта.
#:   runtime_commit     какой выпуск сайта исполняется.
#:   artifact_sha256    сумма ФАЙЛА РАНТАЙМА: по ней судят, какой код работает.
#:   built_at           время КОММИТА выпуска.
#:   release_dir        куда выпуск ставится на боевой машине.
#:   bound_release_link ссылка, которой он привязан.
#:
#: `release_dir` и `bound_release_link` до этой правки указывали в дерево
#: ОБЩЕЙ фабрики `/srv/lords/.frontend/…`, потому что родословная у сборщиков
#: общая. Каждая выделенная ячейка объявляла своей раскладкой чужую.
ПОЛЯ_ВЫПУСКА = ("build_id", "artifact_sha256", "runtime_commit", "site_repo_commit",
                "site_repo_dirty", "built_at", "built_from", "release_dir",
                "bound_release_link", "source_commit", "source_dirty")

#: Поле, которое сборка НЕ трогает: происхождение шаблона неподвижно.
ПОЛЕ_ПРОИСХОЖДЕНИЯ = "template_origin"


def commit_time(commit: str) -> str:
    """Время коммита в UTC. Детерминировано: один коммит — одно значение.

    Берётся `%ct` — секунды эпохи, а не `%cI`. Форматирование отдано Python
    намеренно: `%cI` у git на раннере даёт `2026-09-26T10:44:55Z`, а
    `datetime.fromisoformat` в Python 3.10 такую строку не принимает. Отсюда
    проверка проходила в чистом клоне и падала в CI. Число секунд не зависит
    ни от версии git, ни от локали, ни от часового пояса машины.
    """
    out = subprocess.run(["git", "-C", str(ROOT), "show", "-s", "--format=%ct", commit],
                         capture_output=True, text=True, check=True).stdout.strip()
    return datetime.fromtimestamp(int(out), timezone.utc).isoformat()


def штамп(manifest: dict, cfg: dict, pins: dict, commit: str, dirty: bool) -> dict:
    """Проставить сведения о выпуске поверх сведений о шаблоне.

    Функция вынесена, чтобы проверка сверяла ровно то, что кладётся в
    артефакт, а не свою копию правил: расхождение проверки и сборки — это и
    есть тот случай, когда CI зеленеет, а витрина называет чужие цифры.
    """
    dep = cfg.get("deployment") or {}
    короткий = commit[:12]
    out = dict(manifest)
    out["source_commit"] = pins["pins"]["source_commit"]
    out["source_dirty"] = False
    out["site_repo_commit"] = commit
    out["site_repo_dirty"] = bool(dirty)
    out["runtime_commit"] = commit
    out["build_id"] = f"{короткий}-{cfg['site_id']}"
    out["artifact_sha256"] = hashlib.sha256(
        (ROOT / "src" / cfg["entrypoint"]).read_bytes()).hexdigest()
    out["built_at"] = commit_time(commit)
    out["built_from"] = "site-repo git commit"
    if dep.get("release_parent"):
        out["release_dir"] = f"{dep['release_parent'].rstrip('/')}/{короткий}"
    if dep.get("current_link"):
        out["bound_release_link"] = dep["current_link"]
    return out


def anonymise(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    info.mode = 0o755 if info.mode & 0o111 else 0o644
    return info


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dist")
    args = parser.parse_args()
    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)

    cfg = json.loads((ROOT / "config" / "site.json").read_text(encoding="utf-8"))
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"],
                           capture_output=True, text=True, check=True).stdout.strip()

    # Манифест штампуется коммитом ЭТОЙ репы: иначе живой сайт объявлял бы
    # build_id чужой сборки, и связь commit → CI → digest → живой сайт
    # обрывалась бы на последнем звене. Отметки ВРЕМЕНИ СБОРКИ нет намеренно —
    # она сделала бы digest невоспроизводимым; built_at берётся от коммита.
    manifest_path = "config/template-manifest.json"
    pins = json.loads((ROOT / "pins.lock.json").read_text(encoding="utf-8"))
    stamped = None
    if (ROOT / manifest_path).is_file():
        stamped = штамп(json.loads((ROOT / manifest_path).read_text(encoding="utf-8")),
                        cfg, pins, commit, bool(dirty))
        stamped_bytes = (json.dumps(stamped, ensure_ascii=False, indent=1) + "\n").encode()

    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for p in files():
            arc = str(p.relative_to(ROOT))
            if stamped is not None and arc == manifest_path:
                info = tarfile.TarInfo(arc)
                info.size = len(stamped_bytes)
                info.mode = 0o644
                tar.addfile(anonymise(info), io.BytesIO(stamped_bytes))
                continue
            tar.add(p, arcname=arc, filter=anonymise)
    artifact = out / f"{cfg['site_id']}-{commit[:12]}.tar.gz"
    with artifact.open("wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
        gz.write(raw.getvalue())

    digest = "sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 1,
        "site_id": cfg["site_id"],
        "domain": cfg["domain"],
        "artifact": artifact.name,
        "digest": digest,
        "size_bytes": artifact.stat().st_size,
        "source_commit": commit,
        "source_dirty": bool(dirty),
        "pins": pins["pins"],
        "built_at": datetime.now(timezone.utc).isoformat(),
        "live_build_id": stamped["build_id"] if stamped else None,
        "contains": {"code": True, "config": True, "database": False,
                     "media": False, "secrets": False, "catalog_snapshot": False},
    }
    (out / "release-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"артефакт: {artifact}")
    print(f"digest:   {digest}")
    print(f"коммит:   {commit}")
    if dirty:
        print("ВНИМАНИЕ: дерево грязное, артефакт не воспроизводим из коммита")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
