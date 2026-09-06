"""Закреплённый артефакт шаблона: чем собран релиз и чем он будет пересобран.

Обновление каталога раньше отрисовывало витрину тем, что лежало в развёрнутом
checkout. Это и есть источник инцидента: чужая правка в рабочем дереве
попадала на боевую витрину без выкладки, а выложенная канарейка — исчезала.

Здесь артефакт **закрепляется**: содержимое ревизии складывается в архив, у
архива есть отпечаток, и отрисовка идёт из распакованного архива, а не из
рабочего дерева. Отпечаток проверяется дважды — при распаковке и перед
отрисовкой: артефакт, подменённый между этими моментами, ничем не отличался бы
от исходного.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from pathlib import Path

from factory.lords.release_manifest import ManifestError, отпечаток_файла

#: Куда распаковываются закреплённые шаблоны витрины. Внутри рантайма, а не в
#: /tmp: у службы обновления /tmp — отдельное монтирование, и жёсткие ссылки
#: между ним и /srv/lords не создаются.
ПОДКАТАЛОГ = ".templates"


class ArtifactError(Exception):
    """Артефакт недоступен, подменён или непригоден для отрисовки."""


def собрать(repo: Path | str, revision: str, out: Path | str) -> dict[str, str]:
    """Архив ревизии репозитория. Ревизия — полный SHA, а не ветка.

    Ветка — движущаяся ссылка: артефакт, собранный «из ветки», через день
    означает другое содержимое, и отпечаток перестаёт что-либо доказывать.
    """
    if len(revision) != 40 or not all(с in "0123456789abcdef" for с in revision.lower()):
        raise ArtifactError(f"ревизия должна быть полным SHA: {revision!r}")
    цель = Path(out)
    цель.parent.mkdir(parents=True, exist_ok=True)
    временный = цель.with_suffix(цель.suffix + ".tmp")
    try:
        with open(временный, "wb") as ф:
            subprocess.run(
                ["git", "-C", str(repo), "archive", "--format=tar.gz", revision],
                stdout=ф, stderr=subprocess.PIPE, check=True, timeout=600,
            )
    except subprocess.CalledProcessError as ошибка:
        временный.unlink(missing_ok=True)
        сказано = (ошибка.stderr or b"").decode("utf-8", "replace").strip()
        raise ArtifactError(f"git archive не собрал ревизию {revision[:12]}: {сказано}") from ошибка
    except (OSError, subprocess.SubprocessError) as ошибка:
        временный.unlink(missing_ok=True)
        raise ArtifactError(f"артефакт не собран: {ошибка}") from ошибка
    временный.replace(цель)
    return {"path": str(цель), "digest": отпечаток_файла(цель), "revision": revision}


def распаковать(archive: Path | str, digest: str, into: Path | str) -> Path:
    """Распаковать артефакт с проверкой отпечатка. Возвращает корень шаблона.

    Уже распакованный артефакт не распаковывается заново: каталог назван его
    отпечатком, и совпадение имени означает совпадение содержимого.
    """
    архив = Path(archive)
    if not архив.is_file():
        raise ArtifactError(f"артефакта шаблона нет: {архив}")
    фактический = отпечаток_файла(архив)
    if фактический != digest:
        raise ArtifactError(
            f"отпечаток артефакта {фактический[:12]}… не совпадает с объявленным "
            f"{str(digest)[:12]}…: шаблон подменён"
        )
    корень = Path(into) / digest
    готово = корень / ".unpacked"
    if готово.is_file():
        return корень
    корень.parent.mkdir(parents=True, exist_ok=True)
    временный = Path(tempfile.mkdtemp(prefix=f"{digest[:12]}.", dir=str(корень.parent)))
    try:
        subprocess.run(["tar", "-xzf", str(архив), "-C", str(временный)],
                       check=True, capture_output=True, timeout=900)
        (временный / ".unpacked").write_text(digest + "\n", encoding="utf-8")
        os.replace(временный, корень)
    except FileNotFoundError:
        # Каталог с таким отпечатком уже появился — распаковал соседний вызов.
        subprocess.run(["rm", "-rf", str(временный)], check=False)
    except (OSError, subprocess.SubprocessError) as ошибка:
        subprocess.run(["rm", "-rf", str(временный)], check=False)
        if not готово.is_file():
            raise ArtifactError(f"артефакт не распакован: {ошибка}") from ошибка
    return корень


def корень_шаблона(манифест: dict, *, runtime: Path | str,
                   artifact_root: Path | str) -> Path:
    """Каталог, из которого обязана идти отрисовка этого релиза."""
    ссылка = str(манифест.get("template_artifact_ref") or "")
    отпечаток = str(манифест.get("template_digest") or "")
    if not ссылка or not отпечаток:
        raise ManifestError(
            "манифест не называет артефакт шаблона: восстановить шаблон релиза нечем"
        )
    архив = Path(ссылка)
    if not архив.is_absolute():
        архив = Path(artifact_root) / ссылка
    return распаковать(архив, отпечаток, Path(runtime) / ПОДКАТАЛОГ)


def отпечаток_дерева(корень: Path | str, *, подкаталоги: tuple[str, ...]) -> str:
    """Отпечаток отрисовывающей части дерева — для сверки после распаковки.

    Считается по содержимому файлов и их путям: переименование файла меняет
    отпечаток так же, как правка его содержимого.
    """
    ш = hashlib.sha256()
    основа = Path(корень)
    for под in sorted(подкаталоги):
        каталог = основа / под
        if not каталог.exists():
            continue
        for путь in sorted(p for p in каталог.rglob("*") if p.is_file()):
            ш.update(str(путь.relative_to(основа)).encode("utf-8"))
            ш.update(b"\0")
            ш.update(путь.read_bytes())
            ш.update(b"\0")
    return ш.hexdigest()
