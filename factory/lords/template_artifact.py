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


def понижение_прав(repo: Path | str) -> tuple[dict, str]:
    """Как выполнить git в чужом дереве, не давая root доверять этому дереву.

    Дефект LORDS-RELEASE-ADOPT-GIT-PRIVILEGED-33. `adopt` вызывается фазой
    `switch`, а та идёт от root. Рабочее дерево принадлежит `claude`, и git
    отказывается работать с каталогом чужого владельца: сборка архива падала,
    манифест не записывался, и выкладка честно откатывалась уже после подмены
    ссылки. Три часа отрисовки при этом были целы — ломался последний шаг.

    Лечится не доверием, а понижением прав. `safe.directory` заставил бы root
    доверять чужому дереву — ровно то, чего избегает
    `lords-canary-provenance.py`: «без git в привилегированном пути… и без
    доверия к чужому каталогу». Здесь привилегированный процесс вместо этого
    перестаёт быть привилегированным на время чтения: потомок переходит под
    владельца дерева. Движение прав вниз, а не вверх.

    Возвращает добавку к вызову `subprocess` и объяснение для журнала.
    """
    if os.geteuid() != 0:
        return {}, "прав не понижаем: процесс и так не root"
    try:
        владелец = os.stat(repo).st_uid
    except OSError as ошибка:
        raise ArtifactError(f"дерево {repo} недоступно: {ошибка}") from ошибка
    if владелец == 0:
        return {}, "дерево принадлежит root: понижать не к кому"

    import grp
    import pwd

    запись = pwd.getpwuid(владелец)
    группы = sorted({g.gr_gid for g in grp.getgrall() if запись.pw_name in g.gr_mem}
                    | {запись.pw_gid})

    def подготовка() -> None:  # pragma: no cover — исполняется в потомке
        os.setgroups(группы)
        os.setgid(запись.pw_gid)
        os.setuid(владелец)

    return ({"preexec_fn": подготовка},
            f"git выполняется от {запись.pw_name} (uid {владелец}), а не от root")


def собрать(repo: Path | str, revision: str, out: Path | str) -> dict[str, str]:
    """Архив ревизии репозитория. Ревизия — полный SHA, а не ветка.

    Ветка — движущаяся ссылка: артефакт, собранный «из ветки», через день
    означает другое содержимое, и отпечаток перестаёт что-либо доказывать.

    Вызов от root в дереве другого владельца выполняется с понижением прав —
    см. `понижение_прав`.
    """
    if len(revision) != 40 or not all(с in "0123456789abcdef" for с in revision.lower()):
        raise ArtifactError(f"ревизия должна быть полным SHA: {revision!r}")
    цель = Path(out)
    цель.parent.mkdir(parents=True, exist_ok=True)
    временный = цель.with_suffix(цель.suffix + ".tmp")
    добавка, _ = понижение_прав(repo)
    try:
        with open(временный, "wb") as ф:
            subprocess.run(
                ["git", "-C", str(repo), "archive", "--format=tar.gz", revision],
                stdout=ф, stderr=subprocess.PIPE, check=True, timeout=600, **добавка,
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


#: Изменяемое состояние, которое обязано остаться общим для всех релизов.
#:
#: Артефакт неизменяем — в нём нет и не должно быть кэша каталога, очередей и
#: снимков. Но отрисовщик ищет их относительно собственного дерева, и без этой
#: связи закреплённая сборка искала бы живой каталог внутри архива и не находила
#: его: измерено — `BlockedInput: нет кэша живого каталога …/.templates/…/var/…`.
ОБЩЕЕ_СОСТОЯНИЕ = ("var",)


def _связать_состояние(корень: Path, state_root: Path | None) -> None:
    """Общее изменяемое состояние подставляется ссылкой, а не копией.

    Копия означала бы, что каждая витрина работает со своим снимком очередей и
    кэша, и расхождение обнаружилось бы по разному содержимому страниц, а не по
    отказу.
    """
    if state_root is None:
        return
    for имя in ОБЩЕЕ_СОСТОЯНИЕ:
        цель = корень / имя
        if цель.exists() or цель.is_symlink():
            continue
        цель.symlink_to(Path(state_root) / имя)


def распаковать(archive: Path | str, digest: str, into: Path | str,
                *, state_root: Path | str | None = None) -> Path:
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
        _связать_состояние(корень, Path(state_root) if state_root else None)
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
    _связать_состояние(корень, Path(state_root) if state_root else None)
    return корень


def корень_шаблона(манифест: dict, *, runtime: Path | str,
                   artifact_root: Path | str,
                   state_root: Path | str | None = None) -> Path:
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
    return распаковать(архив, отпечаток, Path(runtime) / ПОДКАТАЛОГ,
                      state_root=state_root)


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
