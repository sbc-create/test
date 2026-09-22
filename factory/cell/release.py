"""Готовый релиз: неизменяемый артефакт с digest и манифестом.

Собирается из чистого коммита проекта сайта. На целевом сервере ничего не
собирается: собранное там — другая сборка, и проверяли не её.

Воспроизводимость обеспечивается тем, что в архив не попадает ничего
переменного: порядок файлов задан, времена обнулены, владелец обезличен. Один и
тот же коммит даёт один и тот же digest — и это проверяется тестом, а не
предполагается. Без этого свойства digest бесполезен: он подтверждал бы только
момент упаковки.

Что в манифесте релиза и зачем каждое поле:

* `digest` — по нему установка отказывается ставить не то, что проверяли;
* `source_commit` — по нему находится исходник без старого сервера;
* `schema_versions` — по ним видно, совместимы ли данные;
* `pins` — по ним видно, что общий модуль не подъехал сам собой.
"""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.cell import siterepo

SCHEMA_VERSION = "1.0"
MANIFEST_NAME = "release-manifest.json"

#: Что не попадает в артефакт ни при каких условиях.
EXCLUDED = (".git", "__pycache__", "node_modules", "var", "data", "media")


class ReleaseError(RuntimeError):
    pass


class DigestMismatch(ReleaseError):
    """Артефакт не тот, что описан манифестом. Установка не начинается."""


class StaleSource(ReleaseError):
    """Выкат основан на исходнике старее того, что уже выпущен."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Release:
    site_id: str
    artifact: Path
    manifest_path: Path
    digest: str
    source_commit: str
    manifest: dict[str, Any]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _archive_member(info: tarfile.TarInfo) -> tarfile.TarInfo:
    """Обезличенная запись архива.

    Времена, владелец и группа обнуляются: иначе digest менялся бы от того, кто
    и когда собирал, и перестал бы отвечать на вопрос «то же ли это самое».

    Режим тоже приводится к каноническому. Git хранит у файла ровно один бит
    прав — исполняемый; всё остальное берётся из umask сборщика. Без этой
    нормализации один и тот же коммит давал разный digest у разработчика (664)
    и на раннере CI (644), и сравнивать артефакты было нечем.
    """
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    info.mode = 0o755 if info.mode & 0o111 else 0o644
    return info


def _files(root: Path) -> list[Path]:
    out: list[Path] = []
    for path in root.rglob("*"):
        if any(part in EXCLUDED for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            out.append(path)
    # Порядок задан явно: порядок обхода файловой системы не гарантирован, а
    # архив, собранный в другом порядке, даст другой digest при том же содержимом.
    return sorted(out, key=lambda p: str(p.relative_to(root)))


def pack(source: Path, destination: Path) -> str:
    """Собрать воспроизводимый архив. Возвращает digest."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for path in _files(source):
            arcname = str(path.relative_to(source))
            tar.add(path, arcname=arcname, filter=_archive_member)
    # gzip с mtime=0: иначе штамп времени в заголовке gzip менял бы digest
    # при каждой сборке, и сравнивать было бы нечего.
    import gzip

    payload = raw.getvalue()
    with destination.open("wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
        gz.write(payload)
    return sha256_file(destination)


def build(*, site_id: str, repo: Path, output_dir: Path,
          pins: dict[str, Any] | None = None,
          schema_versions: dict[str, Any] | None = None,
          allow_dirty: bool = False) -> Release:
    """Собрать релиз из текущего коммита проекта сайта."""
    if not (repo / ".git").exists():
        raise ReleaseError(f"{repo} не Git-проект: релиз собирается из коммита")
    if not allow_dirty and not siterepo.is_clean(repo):
        raise ReleaseError(
            f"в проекте {repo} есть незакоммиченные изменения; "
            "релиз собирается из чистого коммита, иначе исходник артефакта не найти"
        )
    commit = siterepo.head_commit(repo)

    manifest_file = repo / "site-manifest.json"
    if not manifest_file.exists():
        raise ReleaseError(f"в проекте {repo} нет site-manifest.json")
    site_manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if site_manifest["site_id"] != site_id:
        raise ReleaseError(
            f"проект описывает сайт {site_manifest['site_id']}, а собрать просят "
            f"{site_id}: чужой артефакт не выпускается"
        )

    if pins is None:
        pins_file = repo / "pins.lock.json"
        pins = json.loads(pins_file.read_text(encoding="utf-8")).get("pins", {}) \
            if pins_file.exists() else {}

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = output_dir / f"{site_id}-{commit[:12]}.tar.gz"
    digest = pack(repo, artifact)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "site_id": site_id,
        "domain": site_manifest.get("domain"),
        "artifact": artifact.name,
        "digest": digest,
        "size_bytes": artifact.stat().st_size,
        "source_commit": commit,
        "source_repo": str(repo),
        "template": site_manifest.get("template", {}),
        "modules": site_manifest.get("modules", []),
        "pins": pins,
        "schema_versions": schema_versions or {
            "site_manifest": site_manifest.get("schema_version"),
            "release_manifest": SCHEMA_VERSION,
        },
        "built_at": utc_now(),
        "contains": {
            "code": True,
            "config": True,
            # Сказано явно, потому что «пакет = бэкап» — самое дорогое из
            # возможных заблуждений при переносе.
            "database": False,
            "media": False,
            "secrets": False,
        },
    }
    manifest_path = output_dir / f"{site_id}-{commit[:12]}.{MANIFEST_NAME}"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return Release(site_id=site_id, artifact=artifact, manifest_path=manifest_path,
                   digest=digest, source_commit=commit, manifest=manifest)


def verify_artifact(artifact: Path, manifest: dict[str, Any] | Path) -> dict[str, Any]:
    """Проверить артефакт по манифесту до установки, а не после."""
    data = (json.loads(Path(manifest).read_text(encoding="utf-8"))
            if isinstance(manifest, str | Path) else manifest)
    if not artifact.exists():
        raise ReleaseError(f"артефакта нет: {artifact}")
    actual = sha256_file(artifact)
    if actual != data["digest"]:
        raise DigestMismatch(
            f"digest артефакта {actual} не совпадает с манифестом {data['digest']}: "
            "ставится не то, что проверяли"
        )
    contains = data.get("contains", {})
    for forbidden in ("database", "media", "secrets"):
        if contains.get(forbidden):
            raise ReleaseError(
                f"манифест объявляет {forbidden} внутри артефакта; "
                "данные и секреты переносятся отдельно"
            )
    return {
        "artifact": str(artifact),
        "digest": actual,
        "source_commit": data["source_commit"],
        "site_id": data["site_id"],
        "verified": True,
    }


def guard_stale_source(*, incoming_commit: str, deployed_commit: str | None,
                       repo: Path) -> None:
    """Отказать выкату, основанному на устаревшем исходнике.

    Случай, ради которого написано: сессия открыта вчера, за это время вышел
    новый релиз, и вчерашняя сборка перезаписала бы его молча. Проверяется
    родство коммитов, а не время: время на разных машинах не совпадает, а предок
    остаётся предком.
    """
    if not deployed_commit or deployed_commit == incoming_commit:
        return
    result = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor",
         incoming_commit, deployed_commit],
        capture_output=True, text=True, check=False,
    )
    if result.returncode == 0:
        raise StaleSource(
            f"выкат основан на {incoming_commit[:12]}, а развёрнут уже потомок "
            f"{deployed_commit[:12]}: устаревшая сессия не перезаписывает свежий релиз"
        )


def unpack(artifact: Path, destination: Path, *, expected_digest: str | None = None) -> Path:
    """Распаковать артефакт в каталог релиза."""
    if expected_digest:
        actual = sha256_file(artifact)
        if actual != expected_digest:
            raise DigestMismatch(f"digest {actual} вместо ожидаемого {expected_digest}")
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(artifact, "r:gz") as tar:
        for member in tar.getmembers():
            # Архив приходит извне: путь с «..» или абсолютный распаковался бы
            # мимо каталога назначения. Отдельный сайт не пишет за свои пределы.
            name = Path(member.name)
            if name.is_absolute() or ".." in name.parts:
                raise ReleaseError(f"в архиве недопустимый путь: {member.name}")
        tar.extractall(destination, filter="data")
    return destination
