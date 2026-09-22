"""Перенос сайта: export → install → verify → cutover → rollback.

Порядок не декоративный. Каждый шаг существует потому, что пропуск именно его
однажды стоил данных:

* **export** снимает согласованный снимок только этого арендатора и записывает
  числа строк и контрольные суммы — иначе «перенеслось вроде всё» проверить
  нечем;
* **install** ставит готовый артефакт по digest и держит данные вне сменяемого
  каталога релиза;
* **verify** проверяет настоящие маршруты и совместимость данных, а не код 200
  на главной: главная отдаёт 200 и на пустом каталоге;
* **cutover** делает бэкап, репетицию и короткое окно запрета записи, чтобы
  последняя дельта переехала, пока никто не пишет в оба места сразу;
* **rollback** возвращает код и маршрутизацию, **сохраняя** записи, принятые на
  новой стороне. Восстановление вчерашней базы откатом не является: комментарии
  этого дня в ней отсутствуют.

Одновременный перенос или выкат одного сайта исключён блокировкой. Блокировка
не держится вечно и не снимается за чужим процессом без подтверждения.
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.cell import release as release_mod
from factory.cell import tenant
from factory.locks import LockBusy, site_lock

SCHEMA_VERSION = "1.0"
EXPORT_MANIFEST = "export-manifest.json"

#: Запас места, ниже которого перенос не начинается. Развернуться «впритык»
#: означает получить оборванную распаковку и ни старого, ни нового.
MIN_FREE_BYTES = 256 * 1024 * 1024


class TransferError(RuntimeError):
    pass


class TransferBusy(TransferError):
    """Этот сайт уже переносят или выкатывают."""


class VerificationFailed(TransferError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Layout:
    """Расположение сайта на сервере.

    Данные и релизы разнесены намеренно: `current` меняется при каждом выкате,
    а каталог данных не меняется никогда.
    """

    root: Path

    def __post_init__(self) -> None:
        # Путь приводится к абсолютному здесь и один раз. Относительный корень
        # давал символическую ссылку, разрешаемую от каталога самой ссылки:
        # `current` указывала в несуществующее место, и обнаруживалось это не
        # при переключении, а при следующей записи рядом с ней.
        self.root = Path(self.root).resolve()

    @property
    def releases(self) -> Path:
        return self.root / "releases"

    @property
    def current(self) -> Path:
        return self.root / "current"

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def database(self) -> Path:
        return self.data / "site.sqlite3"

    @property
    def media(self) -> Path:
        return self.data / "media"

    @property
    def public(self) -> Path:
        """Собранные страницы витрины.

        Живут в каталоге данных, а не внутри релиза: каталог, SEO-тексты и
        пользовательские записи не должны лежать в сменяемой папке. Иначе откат
        кода уносит с собой опубликованные страницы, и «откатили релиз»
        означает «сайт исчез».
        """
        return self.data / "public"

    @property
    def backups(self) -> Path:
        return self.root / "backups"

    @property
    def state_file(self) -> Path:
        return self.root / "install-state.json"

    def ensure(self) -> Layout:
        for directory in (self.releases, self.data, self.media, self.public,
                          self.backups):
            directory.mkdir(parents=True, exist_ok=True)
        return self


@dataclass
class ExportPackage:
    site_id: str
    path: Path
    manifest: dict[str, Any]

    @property
    def snapshot(self) -> Path:
        return self.path / "site.sqlite3"


@dataclass
class StepResult:
    step: str
    status: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"step": self.step, "status": self.status, "detail": self.detail}


def _lock(site_id: str, environment: str = "transfer"):
    try:
        return site_lock(site_id, environment, timeout=0.0)
    except LockBusy as exc:
        raise TransferBusy(
            f"{site_id}: перенос или выкат уже идёт ({exc.holder}); "
            "два одновременных не допускаются"
        ) from exc


def export(*, site_id: str, layout: Layout, destination: Path,
           dry_run: bool = False) -> ExportPackage:
    """Согласованный снимок данных одного арендатора."""
    if not layout.database.exists():
        # Открытие хранилища создаёт файл базы. На сухом прогоне это была бы
        # мутация — ровно то, чего `--dry-run` обещает не делать; на обычном
        # прогоне это пустая база вместо честного «переносить нечего».
        raise TransferError(
            f"{site_id}: базы данных нет по пути {layout.database}; "
            "переносить нечего, и пустая база вместо неё не создаётся"
        )
    store = tenant.open_store(site_id, layout.database)
    try:
        counts = store.row_counts()
        checksum = store.checksum()
        rows = store.export_rows()
        foreign = {row.get("site_id") for table in rows.values() for row in table} - {site_id}
        if foreign:
            raise TransferError(
                f"в выгрузку попали данные сайтов {sorted(foreign)}; "
                "пакет одного арендатора не содержит соседей"
            )
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "site_id": site_id,
            "row_counts": counts,
            "checksum": checksum,
            "tables": list(tenant.TRANSFERABLE_TABLES),
            "taken_at": utc_now(),
            "method": "sqlite online backup api",
            "contains_secrets": False,
            "note": "Данные, не код. Артефакт релиза переносится отдельно.",
        }
        if dry_run:
            return ExportPackage(site_id=site_id, path=destination, manifest=manifest)
        destination.mkdir(parents=True, exist_ok=True)
        store.snapshot(destination / "site.sqlite3")
        (destination / "rows.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        if layout.media.exists() and any(layout.media.iterdir()):
            shutil.copytree(layout.media, destination / "media", dirs_exist_ok=True)
        (destination / EXPORT_MANIFEST).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return ExportPackage(site_id=site_id, path=destination, manifest=manifest)
    finally:
        store.close()


def import_data(*, site_id: str, package: Path, layout: Layout,
                dry_run: bool = False) -> dict[str, Any]:
    """Приём выгрузки на целевой стороне со сверкой чисел и сумм."""
    manifest_path = package / EXPORT_MANIFEST
    if not manifest_path.exists():
        raise TransferError(f"в пакете {package} нет {EXPORT_MANIFEST}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["site_id"] != site_id:
        raise TransferError(
            f"пакет собран для {manifest['site_id']}, а ставится в {site_id}")
    if dry_run:
        return {"status": "dry-run", "expected": manifest["row_counts"],
                "checksum": manifest["checksum"]}

    layout.ensure()
    rows = json.loads((package / "rows.json").read_text(encoding="utf-8"))
    store = tenant.open_store(site_id, layout.database)
    try:
        store.import_rows(rows, expected_site_id=site_id)
        counts = store.row_counts()
        checksum = store.checksum()
    finally:
        store.close()

    if counts != manifest["row_counts"]:
        raise TransferError(
            f"после переноса числа строк не сошлись: {counts} вместо "
            f"{manifest['row_counts']}")
    if checksum != manifest["checksum"]:
        raise TransferError(
            f"контрольная сумма не сошлась: {checksum} вместо {manifest['checksum']}")
    media = package / "media"
    if media.exists():
        shutil.copytree(media, layout.media, dirs_exist_ok=True)
    return {"status": "imported", "row_counts": counts, "checksum": checksum}


def _free_bytes(path: Path) -> int:
    usage = shutil.disk_usage(path)
    return usage.free


def install(*, site_id: str, artifact: Path, manifest: Path | dict[str, Any],
            layout: Layout, dry_run: bool = False,
            expected_digest: str | None = None,
            require_own_repo: bool = True) -> dict[str, Any]:
    """Поставить готовый артефакт. Сборки здесь не происходит.

    Перед установкой проверяется, что у сайта есть собственный репозиторий.
    Случай, ради которого: создание репозитория сорвалось, конвейер пошёл
    дальше и выложил сайт из монорепозитория. Снаружи это неотличимо от
    нормального выпуска — до первой правки, когда выясняется, что менять нечего
    и откатывать некуда. Поэтому отказ, а не предупреждение.

    `require_own_repo=False` оставлен для пилотов и стендов, которых нет в
    реестре: они и не публикуются наружу.
    """
    if require_own_repo:
        from factory.cell import registry as _registry
        try:
            cell = _registry.resolve(site_id)
        except _registry.UnknownCell:
            raise TransferError(
                f"{site_id}: сайта нет в реестре ячеек, собственный репозиторий "
                "не подтверждён; выкладка из монорепозитория запрещена"
            ) from None
        _registry.require_own_repo(cell)
    data = (json.loads(Path(manifest).read_text(encoding="utf-8"))
            if isinstance(manifest, str | Path) else manifest)
    if data["site_id"] != site_id:
        raise TransferError(
            f"артефакт собран для {data['site_id']}, а ставится в {site_id}: "
            "чужой артефакт не устанавливается")
    checked = release_mod.verify_artifact(artifact, data)
    if expected_digest and checked["digest"] != expected_digest:
        raise release_mod.DigestMismatch(
            f"ожидали {expected_digest}, в артефакте {checked['digest']}")

    layout.ensure()
    free = _free_bytes(layout.root)
    needed = max(data.get("size_bytes", 0) * 4, MIN_FREE_BYTES)
    if free < needed:
        raise TransferError(
            f"свободно {free} байт, для установки нужно не меньше {needed}")

    plan = {
        "site_id": site_id,
        "artifact": str(artifact),
        "digest": checked["digest"],
        "source_commit": data["source_commit"],
        "release_dir": str(layout.releases / data["source_commit"][:12]),
        "free_bytes": free,
        "data_untouched": str(layout.data),
    }
    if dry_run:
        return {"status": "dry-run", **plan}

    with _lock(site_id, "install"):
        target = layout.releases / data["source_commit"][:12]
        if target.exists():
            shutil.rmtree(target)
        release_mod.unpack(artifact, target, expected_digest=checked["digest"])
        previous = None
        if layout.current.is_symlink():
            previous = os.readlink(layout.current)
        # Переключение через os.replace: окна без ссылки не возникает.
        temporary = layout.current.parent / f".{layout.current.name}.new"
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()
        temporary.symlink_to(target)
        os.replace(temporary, layout.current)

        state = {
            "site_id": site_id,
            "digest": checked["digest"],
            "source_commit": data["source_commit"],
            "release_dir": str(target),
            "previous_release": previous,
            "installed_at": utc_now(),
        }
        layout.state_file.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "installed", **plan, "previous_release": previous}


def verify(*, site_id: str, layout: Layout,
           expected_routes: tuple[str, ...] = ()) -> dict[str, Any]:
    """Готовность: совместимость данных и настоящие маршруты.

    Проверять только код 200 на главной бессмысленно — главная отдаёт 200 и
    тогда, когда каталог пуст, а все страницы произведений исчезли.
    """
    steps: list[StepResult] = []

    current_ok = layout.current.exists()
    steps.append(StepResult("current-release", "PASS" if current_ok else "FAIL",
                            {"path": str(layout.current)}))

    manifest_file = layout.current / "site-manifest.json" if current_ok else None
    site_manifest: dict[str, Any] = {}
    if manifest_file and manifest_file.exists():
        site_manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        ok = site_manifest.get("site_id") == site_id
        steps.append(StepResult("manifest-belongs-to-site", "PASS" if ok else "FAIL",
                                {"declared": site_manifest.get("site_id")}))
    else:
        steps.append(StepResult("manifest-belongs-to-site", "FAIL",
                                {"reason": "site-manifest.json не найден"}))

    if layout.database.exists():
        store = tenant.open_store(site_id, layout.database)
        try:
            steps.append(StepResult("database-integrity",
                                    "PASS" if store.integrity_ok() else "FAIL",
                                    store.row_counts()))
        finally:
            store.close()
    else:
        steps.append(StepResult("database-integrity", "NOT_RUN",
                                {"reason": "база данных ещё не перенесена"}))

    missing_routes: list[str] = []
    if expected_routes:
        # Страницы ищутся в каталоге содержимого, а не в релизе: релиз меняется,
        # опубликованные адреса — нет.
        published = layout.public
        for route in expected_routes:
            candidate = (published / "index.html" if route == "/"
                         else published / route.strip("/") / "index.html")
            if not candidate.exists():
                missing_routes.append(route)
        steps.append(StepResult(
            "published-routes", "PASS" if not missing_routes else "FAIL",
            {"checked": len(expected_routes), "missing": missing_routes}))
    else:
        steps.append(StepResult("published-routes", "NOT_RUN",
                                {"reason": "список ожидаемых маршрутов не передан"}))

    failed = [s for s in steps if s.status == "FAIL"]
    return {
        "site_id": site_id,
        "status": "FAIL" if failed else "PASS",
        "steps": [s.to_dict() for s in steps],
        "checked_at": utc_now(),
    }


def freeze_writes(*, site_id: str, layout: Layout, reason: str) -> Path:
    """Короткое окно запрета записи только для этого сайта."""
    marker = tenant.freeze_marker(layout.database)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(f"{site_id}: {reason} ({utc_now()})\n", encoding="utf-8")
    return marker


def thaw_writes(*, layout: Layout) -> None:
    tenant.freeze_marker(layout.database).unlink(missing_ok=True)


def backup(*, site_id: str, layout: Layout) -> Path:
    """Бэкап перед переключением. Без него репетиция бессмысленна."""
    layout.ensure()
    stamp = utc_now().replace(":", "").replace("-", "")
    destination = layout.backups / f"{site_id}-{stamp}"
    destination.mkdir(parents=True, exist_ok=True)
    if layout.database.exists():
        store = tenant.open_store(site_id, layout.database)
        try:
            store.snapshot(destination / "site.sqlite3")
            (destination / "counts.json").write_text(
                json.dumps({"row_counts": store.row_counts(),
                            "checksum": store.checksum()},
                           ensure_ascii=False, indent=2), encoding="utf-8")
        finally:
            store.close()
    return destination


def cutover(*, site_id: str, source: Layout, target: Layout,
            reason: str, dry_run: bool = False,
            rehearsal: bool = True) -> dict[str, Any]:
    """Перенос последней дельты под запретом записи.

    Настоящий перенос домена здесь не выполняется: переключение маршрутизации —
    отдельный разрешённый шаг, и делать его побочным эффектом этой функции
    значило бы переключить домен из репетиции.
    """
    steps: list[StepResult] = []
    if dry_run:
        steps.append(StepResult("rehearsal", "PASS",
                                {"note": "репетиция: ничего не менялось"}))
        return {"site_id": site_id, "status": "dry-run",
                "steps": [s.to_dict() for s in steps],
                "dns_switched": False}

    with _lock(site_id, "cutover"):
        saved = backup(site_id=site_id, layout=source)
        steps.append(StepResult("backup", "PASS", {"path": str(saved)}))

        if rehearsal:
            trial = export(site_id=site_id, layout=source,
                           destination=source.root / "rehearsal", dry_run=True)
            steps.append(StepResult("rehearsal", "PASS",
                                    {"row_counts": trial.manifest["row_counts"]}))

        freeze_writes(site_id=site_id, layout=source,
                      reason=f"перенос последней дельты: {reason}")
        steps.append(StepResult("freeze-source", "PASS", {"scope": site_id}))

        # Источник остаётся замороженным и после успеха, и после ошибки.
        # Разморозка здесь разрешила бы запись в оба места сразу — ровно то,
        # чего окно запрета и не допускает. Снимает запрет отдельное решение:
        # после того, как маршрут переключён, или после отмены переноса
        # (`thaw_writes`).
        delta = export(site_id=site_id, layout=source,
                       destination=source.root / "delta")
        steps.append(StepResult("export-delta", "PASS",
                                {"row_counts": delta.manifest["row_counts"]}))
        imported = import_data(site_id=site_id, package=delta.path, layout=target)
        steps.append(StepResult("import-delta", "PASS", imported))

    failed = [s for s in steps if s.status == "FAIL"]
    return {
        "site_id": site_id,
        "status": "FAIL" if failed else "PASS",
        "steps": [s.to_dict() for s in steps],
        # Переключение домена сюда не входит и честно называется невыполненным.
        "dns_switched": False,
        "source_frozen": True,
        "at": utc_now(),
    }


def rollback(*, site_id: str, layout: Layout, reason: str,
             dry_run: bool = False) -> dict[str, Any]:
    """Вернуть прежний релиз, сохранив данные, принятые после переключения."""
    if not layout.state_file.exists():
        raise TransferError(f"{site_id}: нечего откатывать — состояния установки нет")
    state = json.loads(layout.state_file.read_text(encoding="utf-8"))
    previous = state.get("previous_release")
    if not previous:
        raise TransferError(
            f"{site_id}: предыдущего релиза нет; откат кода невозможен, "
            "и подменять его восстановлением базы нельзя")

    before = None
    if layout.database.exists():
        store = tenant.open_store(site_id, layout.database)
        try:
            before = {"row_counts": store.row_counts(), "checksum": store.checksum()}
        finally:
            store.close()

    plan = {"site_id": site_id, "to": previous, "from": state.get("release_dir"),
            "data_preserved": True, "reason": reason, "data_before": before}
    if dry_run:
        return {"status": "dry-run", **plan}

    with _lock(site_id, "rollback"):
        temporary = layout.current.parent / f".{layout.current.name}.rollback"
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()
        temporary.symlink_to(previous)
        os.replace(temporary, layout.current)
        state["previous_release"] = state.get("release_dir")
        state["release_dir"] = previous
        state["rolled_back_at"] = utc_now()
        state["rollback_reason"] = reason
        layout.state_file.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    after = None
    if layout.database.exists():
        store = tenant.open_store(site_id, layout.database)
        try:
            after = {"row_counts": store.row_counts(), "checksum": store.checksum()}
        finally:
            store.close()
    if before is not None and after != before:
        raise TransferError(
            f"{site_id}: откат кода изменил данные ({before} → {after}); "
            "это не откат, а потеря записей"
        )
    return {"status": "rolled-back", **plan, "data_after": after}
