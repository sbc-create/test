"""Атомарная публикация релиза.

Прежний способ — `ln -sfn` — на Linux выполняется как `unlink` плюс `symlink`.
Между ними существует окно, в котором ссылки `current` нет вовсе, и запрос,
пришедший в этот момент, получает ошибку. Окно мало, но оно есть, и на витрине
с непрерывным потоком запросов «мало» означает «иногда».

Здесь переключение делается иначе: ссылка создаётся под временным именем рядом,
на той же файловой системе, а затем заменяет `current` вызовом `os.replace`,
который на POSIX выполняется как `rename(2)` — атомарно. Наблюдатель видит либо
прежнюю цель, либо новую, и никогда — отсутствие ссылки.

Требование «на той же файловой системе» не формальность: `rename(2)` между
устройствами не работает вовсе, и попытка дала бы `OSError` уже после того, как
временная ссылка создана.
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


class PublishError(Exception):
    pass


@dataclass(frozen=True)
class PublishResult:
    site_id: str
    previous: Path | None
    current: Path
    replaced: bool


def _same_filesystem(a: Path, b: Path) -> bool:
    try:
        return a.stat().st_dev == b.stat().st_dev
    except FileNotFoundError:
        return False


def preflight(release: Path, *, expect_pages: int = 1) -> None:
    """Проверки до переключения, а не после.

    Переключиться и обнаружить, что релиз пуст, — значит показать пустую
    витрину. Все проверки, которые можно сделать заранее, делаются заранее.
    """
    if not release.is_dir():
        raise PublishError(f"релиза нет: {release}")
    site = release / "site"
    if not site.is_dir():
        raise PublishError(f"в релизе {release.name} нет каталога site")
    страниц = sum(1 for _ in site.rglob("*.html"))
    if страниц < expect_pages:
        raise PublishError(
            f"в релизе {release.name} страниц {страниц}, ожидалось не меньше "
            f"{expect_pages}: публиковать пустую витрину нельзя"
        )
    runtime = release / "serve.py"
    if not runtime.is_file():
        raise PublishError(f"в релизе {release.name} нет serve.py — он не запустится")


def switch(current_link: Path, release: Path) -> PublishResult:
    """Атомарно перевести `current` на новый релиз.

    Возвращает прежнюю цель, чтобы откат имел куда вернуться, и делает это до
    переключения: узнавать прежний адрес после того, как ссылка уже переставлена,
    поздно.
    """
    release = release.resolve()
    if not release.is_dir():
        raise PublishError(f"релиза нет: {release}")

    каталог = current_link.parent
    каталог.mkdir(parents=True, exist_ok=True)
    if not _same_filesystem(каталог, release):
        raise PublishError(
            f"{каталог} и {release} на разных файловых системах: "
            "атомарная замена между устройствами невозможна"
        )

    прежний: Path | None = None
    if current_link.is_symlink() or current_link.exists():
        try:
            прежний = current_link.resolve()
        except OSError:
            прежний = None

    # Временное имя создаётся рядом, в том же каталоге: `os.replace` требует
    # одной файловой системы, а соседний каталог её гарантирует.
    временное = Path(tempfile.mktemp(prefix=".current.", dir=str(каталог)))
    try:
        временное.symlink_to(release)
        # `os.replace` на POSIX — это `rename(2)`. Он атомарен: наблюдатель
        # видит либо старую цель, либо новую, но не отсутствие ссылки.
        os.replace(временное, current_link)
    except OSError as error:
        # Незавершённая замена не должна оставлять мусор рядом с `current`:
        # следующий запуск принял бы его за чужой незавершённый переход.
        временное.unlink(missing_ok=True)
        raise PublishError(f"переключение {current_link} не выполнено: {error}") from error

    return PublishResult(
        site_id=каталог.name,
        previous=прежний,
        current=release,
        replaced=прежний is not None and прежний != release,
    )


def publish(current_link: Path, release: Path, *, expect_pages: int = 1) -> PublishResult:
    """Проверить и переключить. Порядок обратный не имеет смысла."""
    preflight(release, expect_pages=expect_pages)
    return switch(current_link, release)


def rollback(current_link: Path, target: Path) -> PublishResult:
    """Откат — то же переключение, тем же атомарным способом.

    Отдельного пути у отката нет намеренно: механизм, которым откатываются
    реже, чем публикуются, оказывается непроверенным ровно тогда, когда нужен.
    """
    return publish(current_link, target)


def prune(releases_dir: Path, keep: tuple[Path, ...], *, limit: int = 2) -> list[Path]:
    """Убрать старые релизы, не тронув активный и запасной.

    Список сохраняемых передаётся явно, а не вычисляется здесь: уборщик, сам
    решающий, что активно, однажды ошибётся, и ошибётся необратимо.
    """
    сохранить = {p.resolve() for p in keep if p is not None}
    все = sorted(
        (d for d in releases_dir.iterdir() if d.is_dir()),
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    оставить = list(сохранить)
    for каталог in все:
        if len(оставить) >= limit:
            break
        if каталог.resolve() not in сохранить:
            оставить.append(каталог.resolve())

    удалено: list[Path] = []
    for каталог in все:
        if каталог.resolve() in оставить:
            continue
        удалено.append(каталог)
    return удалено
