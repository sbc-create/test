"""Инкрементальный релиз: новый релиз строится из старого, а не с нуля.

Выбор механизма продиктован измерениями на этой машине, а не вкусом.

* Файловая система — ext4. Copy-on-write (reflink) она не поддерживает, поэтому
  вариант с `cp --reflink` отпадает не по предпочтению, а физически.
* Жёсткие ссылки копируют релиз из 61 тысячи файлов за 19 секунд и не занимают
  места: новый релиз ссылается на те же данные.
* Полная копия 1,6 ГБ ради одной серии — то, чего требовалось избежать.

Главная опасность жёстких ссылок и причина, по которой этот модуль существует
отдельно: **запись в файл, на который ссылаются два релиза, меняет оба**.
Прошлый релиз перестаёт быть точкой отката ровно в тот момент, когда он нужен.
Поэтому страница здесь никогда не переписывается на месте: новый файл пишется
рядом и заменяет старый через `os.replace`, что разрывает связь и оставляет
прежний релиз нетронутым.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


class IncrementalError(Exception):
    pass


@dataclass
class BuildResult:
    release: Path
    base: Path | None
    rewritten: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    linked_files: int = 0
    seconds: float = 0.0
    changes: dict[str, str] = field(default_factory=dict)

    @property
    def touched(self) -> int:
        return len(self.rewritten) + len(self.removed)

    def as_dict(self) -> dict:
        return {
            "release": self.release.name,
            "base": self.base.name if self.base else None,
            "rewritten": list(self.rewritten),
            "removed": list(self.removed),
            "linked_files": self.linked_files,
            "touched": self.touched,
            "seconds": round(self.seconds, 3),
        }


def clone(base: Path, target: Path) -> int:
    """Копия релиза жёсткими ссылками: секунды вместо минут, ноль места.

    Возвращает число связанных файлов. `cp -al` выбран вместо обхода на Python
    не из лени: на 61 тысяче файлов разница между ними — минуты.
    """
    if not base.is_dir():
        raise IncrementalError(f"базового релиза нет: {base}")
    if target.exists():
        raise IncrementalError(f"цель уже существует: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(["cp", "-al", str(base), str(target)], check=True,
                       capture_output=True, text=True, timeout=1800)
    except subprocess.CalledProcessError as error:
        raise IncrementalError(
            f"связывание {base} -> {target} не выполнено: {error.stderr.strip()}"
        ) from error
    return sum(1 for p in target.rglob("*") if p.is_file())


def write_page(release: Path, relative: str, content: str) -> None:
    """Заменить страницу, не тронув базовый релиз.

    Здесь всё дело в порядке. Открыть общий файл на запись значило бы изменить и
    прежний релиз: у жёстких ссылок один индексный узел на всех. Поэтому
    содержимое пишется в новый файл и подставляется через `os.replace` —
    операция создаёт новую связь, а старая остаётся у прежнего релиза.
    """
    цель = release / relative.lstrip("/")
    цель.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(цель.parent), suffix=".part")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp, цель)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def remove_page(release: Path, relative: str) -> bool:
    """Убрать страницу из нового релиза, не тронув прежний.

    `unlink` снимает связь только в этом релизе: данные останутся живы, пока на
    них ссылается кто-то ещё.
    """
    цель = release / relative.lstrip("/")
    if not цель.exists():
        return False
    цель.unlink()
    # Пустые каталоги после удаления страницы — мусор, который потом читается
    # как «раздел есть, но пуст».
    родитель = цель.parent
    while родитель != release and родитель.is_dir() and not any(родитель.iterdir()):
        родитель.rmdir()
        родитель = родитель.parent
    return True


def build_incremental(
    base: Path,
    target: Path,
    *,
    pages: dict[str, str] | None = None,
    remove: tuple[str, ...] = (),
) -> BuildResult:
    """Новый релиз = связанная копия прежнего плюс точечные правки."""
    import time

    начало = time.monotonic()
    связано = clone(base, target)
    переписано: list[str] = []
    for relative, content in sorted((pages or {}).items()):
        write_page(target, relative, content)
        переписано.append(relative)
    удалено = [r for r in sorted(remove) if remove_page(target, r)]
    return BuildResult(
        release=target,
        base=base,
        rewritten=tuple(переписано),
        removed=tuple(удалено),
        linked_files=связано,
        seconds=time.monotonic() - начало,
    )


def verify_base_untouched(base: Path, checksums: dict[str, str]) -> list[str]:
    """Убедиться, что прежний релиз не изменился.

    Проверка существует потому, что ошибка здесь необратима и незаметна:
    испорченный базовый релиз выглядит целым, пока не понадобится откат.
    """
    import hashlib

    расхождения: list[str] = []
    for relative, ожидаемый in checksums.items():
        путь = base / relative.lstrip("/")
        if not путь.exists():
            расхождения.append(f"{relative}: файл исчез из базового релиза")
            continue
        текущий = hashlib.sha256(путь.read_bytes()).hexdigest()
        if текущий != ожидаемый:
            расхождения.append(f"{relative}: содержимое базового релиза изменилось")
    return расхождения


def checksums_of(release: Path, relatives: tuple[str, ...]) -> dict[str, str]:
    import hashlib

    out: dict[str, str] = {}
    for relative in relatives:
        путь = release / relative.lstrip("/")
        if путь.exists():
            out[relative] = hashlib.sha256(путь.read_bytes()).hexdigest()
    return out


def discard(release: Path) -> None:
    """Убрать недостроенный релиз. Жёсткие ссылки делают это дешёвым."""
    shutil.rmtree(release, ignore_errors=True)
