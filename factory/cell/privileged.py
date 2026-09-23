"""Привилегированные операции: их исполняет root-овый код, а не скрипт из репы.

Почему не `deploy/activate.sh`
-----------------------------

Исполнитель умел запускать сценарий активации из репозитория сайта. Репозиторий
доступен на запись обычной учётной записи, а исполнитель работает от root — то
есть право писать в репозиторий превращалось в право выполнить что угодно от
root. Проверки коммита, чистого дерева и CI это не закрывают: CI описан тем же
репозиторием, и владелец репозитория владеет и проверкой.

Поэтому привилегированная сторона не исполняет ничего, что пришло из репозитория.
Репозиторий поставляет ДАННЫЕ: проверенный артефакт и объявления в
`config/site.json`. Шаги, шаблон юнита и порядок переключения живут здесь, в
root-овой копии пакета, и меняются только переустановкой исполнителя.

Что разрешено делать
--------------------

Ровно перечисленное в `ОПЕРАЦИИ`. «Выполнить команду», «запустить скрипт» и
«взять путь из заявки» отсутствуют как понятия, а не запрещены проверкой.
"""
from __future__ import annotations

import os
import pwd
import shutil
import subprocess
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factory.cell import runtime

#: Закрытый набор. Расширяется только правкой этого файла и переустановкой.
ОПЕРАЦИИ = ("prepare", "install_release", "switch", "verify", "rollback")

#: Куда разрешено раскладывать сайты. Любой путь вне этого корня — отказ.
КОРЕНЬ_САЙТОВ = Path("/srv")


class PrivilegedRefused(Exception):
    """Операция отклонена. Ничего не изменено."""


@dataclass
class Площадка:
    """Пути сайта. Выводятся из реестра, а не принимаются аргументом."""

    site_id: str
    account: str
    root: Path
    app: Path
    data: Path
    unit: str
    previous_unit: str | None
    port: int

    @classmethod
    def из_реестра(cls, site_id: str) -> Площадка:
        р = runtime.размещение(site_id)
        if not р.account or not р.port:
            raise PrivilegedRefused(
                f"{site_id}: в реестре нет учётной записи или порта — "
                "исполнять по такому описанию нельзя")
        корень = (КОРЕНЬ_САЙТОВ / р.account).resolve()
        if not str(корень).startswith(str(КОРЕНЬ_САЙТОВ) + os.sep):
            raise PrivilegedRefused(
                f"{site_id}: каталог {корень} вне {КОРЕНЬ_САЙТОВ}")
        return cls(site_id=site_id, account=р.account, root=корень,
                   app=корень / "app", data=корень / "data",
                   unit=р.unit or f"nova-{р.account}.service",
                   previous_unit=р.previous_unit, port=int(р.port))


def _нужен_root() -> None:
    if os.geteuid() != 0:
        raise PrivilegedRefused("операция требует root")


def безопасные_члены(архив: tarfile.TarFile, назначение: Path):
    """Члены архива, которые разрешено распаковывать.

    Проверяется каждое имя: `..`, абсолютный путь и символическая ссылка наружу
    дают выход за каталог назначения. Один такой член превращает распаковку
    артефакта в запись куда угодно от root.
    """
    корень = назначение.resolve()
    for член in архив.getmembers():
        цель = (корень / член.name).resolve()
        if not str(цель).startswith(str(корень) + os.sep):
            raise PrivilegedRefused(
                f"артефакт содержит путь за пределами назначения: {член.name!r}")
        if член.issym() or член.islnk():
            связь = (цель.parent / член.linkname).resolve()
            if not str(связь).startswith(str(корень) + os.sep):
                raise PrivilegedRefused(
                    f"ссылка {член.name!r} ведёт наружу: {член.linkname!r}")
        if not (член.isfile() or член.isdir() or член.issym()):
            raise PrivilegedRefused(
                f"в артефакте недопустимый тип записи: {член.name!r}")
        yield член


def prepare(site_id: str, *, dry_run: bool = True) -> dict[str, Any]:
    """Учётная запись и каталоги. Повтор ничего не ломает."""
    п = Площадка.из_реестра(site_id)
    шаги = []
    try:
        pwd.getpwnam(п.account)
        есть = True
    except KeyError:
        есть = False
    if not есть:
        шаги.append(f"useradd --system {п.account}")
        if not dry_run:
            _нужен_root()
            subprocess.run(["useradd", "--system", "--home", str(п.root),
                            "--shell", "/usr/sbin/nologin", п.account], check=True)
    for каталог in (п.root, п.app, п.data):
        шаги.append(f"каталог {каталог}")
        if not dry_run:
            _нужен_root()
            каталог.mkdir(parents=True, exist_ok=True)
            shutil.chown(каталог, п.account, п.account)
            каталог.chmod(0o755)
    return {"operation": "prepare", "site_id": site_id, "dry_run": dry_run,
            "account_existed": есть, "steps": шаги}


def install_release(site_id: str, артефакт: Path, digest: str, *,
                    dry_run: bool = True) -> dict[str, Any]:
    """Распаковать проверенный артефакт. Ни одной строки из репозитория."""
    import hashlib

    п = Площадка.из_реестра(site_id)
    артефакт = Path(артефакт)
    if not артефакт.is_file():
        raise PrivilegedRefused(f"артефакта нет: {артефакт}")
    факт = "sha256:" + hashlib.sha256(артефакт.read_bytes()).hexdigest()
    if факт != digest:
        raise PrivilegedRefused(
            f"digest артефакта {факт} не совпал с заявленным {digest}")

    новый = п.root / "app.new"
    if dry_run:
        with tarfile.open(артефакт) as tf:
            имена = [ч.name for ч in безопасные_члены(tf, новый)]
        return {"operation": "install_release", "site_id": site_id, "dry_run": True,
                "digest": факт, "members": len(имена)}

    _нужен_root()
    if новый.exists():
        shutil.rmtree(новый)
    новый.mkdir(parents=True)
    with tarfile.open(артефакт) as tf:
        tf.extractall(новый, members=безопасные_члены(tf, новый))
    for путь in новый.rglob("*"):
        shutil.chown(путь, п.account, п.account)
    прежний = п.root / "app.prev"
    if прежний.exists():
        shutil.rmtree(прежний)
    if п.app.exists():
        п.app.rename(прежний)
    новый.rename(п.app)
    return {"operation": "install_release", "site_id": site_id, "dry_run": False,
            "digest": факт, "app": str(п.app), "previous": str(прежний)}


def готов(port: int, *, предел: int = 600, шаг: float = 3.0,
          запрос: float = 5.0, жив=None) -> dict[str, Any]:
    """Ждать готовности приложения. Три исхода, и смешивать их нельзя."""
    import urllib.error
    import urllib.request

    начало = time.monotonic()
    while True:
        прошло = time.monotonic() - начало
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz",
                                        timeout=запрос) as r:
                if r.status == 200:
                    return {"ready": True, "elapsed_sec": round(прошло, 1)}
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        if жив is not None and not жив():
            return {"ready": False, "reason": "процесс не работает",
                    "elapsed_sec": round(прошло, 1)}
        if прошло >= предел:
            return {"ready": False, "reason": "предел ожидания",
                    "elapsed_sec": round(прошло, 1)}
        time.sleep(шаг)


def verify(site_id: str, *, ожидаемый_build: str = "",
           маршруты: tuple[str, ...] = ("/", "/healthz")) -> dict[str, Any]:
    """Приёмка по ответу, а не по состоянию юнита."""
    import re
    import urllib.request

    п = Площадка.из_реестра(site_id)
    итог: dict[str, Any] = {"operation": "verify", "site_id": site_id, "routes": {}}
    for м in маршруты:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{п.port}{м}", timeout=30) as r:
                тело = r.read(400000)
                итог["routes"][м] = {"status": r.status, "bytes": len(тело)}
                if м == "/":
                    найдено = re.search(rb'site-factory-build-id" content="([^"]+)"', тело)
                    итог["build_id"] = найдено.group(1).decode() if найдено else None
        except Exception as exc:  # noqa: BLE001 — любой отказ это отказ приёмки
            итог["routes"][м] = {"error": type(exc).__name__}
    итог["ok"] = all(о.get("status") == 200 for о in итог["routes"].values())
    if ожидаемый_build:
        итог["build_matches"] = итог.get("build_id") == ожидаемый_build
        итог["ok"] = итог["ok"] and итог["build_matches"]
    return итог


def описать_границу() -> dict[str, Any]:
    """Что исполнитель может и чего не может. Для проверки перед установкой."""
    return {
        "operations": list(ОПЕРАЦИИ),
        "runs_repository_scripts": False,
        "accepts_paths_from_request": False,
        "site_root": str(КОРЕНЬ_САЙТОВ),
        "unit_template_source": "root-owned package copy",
        "artifact_members_checked": ["traversal", "symlink escape", "member type"],
    }
