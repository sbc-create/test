"""Журнал состояния, который переживает падение процесса и гонку.

Все реестры ячейки (пул шаблонов, паспорта сайтов, этапы onboarding) меняются
по одному образцу: взять исключительную блокировку, прочитать, изменить,
записать рядом и заменить через `os.replace`. Образец собран здесь, потому что
повторённый в четырёх местах он разъезжается — и разъезжается именно в той
ветке, которая выполняется раз в месяц.

Два свойства, ради которых модуль существует:

* **Атомарность записи.** Читатель видит либо прежнее содержимое, либо новое, и
  никогда — половину. Обрыв питания посреди записи не оставляет обрезанный
  JSON, из-за которого пул шаблонов перестал бы читаться весь.
* **Взаимное исключение.** Два одновременных заказа не получают один и тот же
  свободный шаблон. Это проверяемое свойство, а не обещание: блокировка берётся
  через `flock`, который ядро снимает само, если процесс умер.
"""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from factory.paths import PATHS


class LedgerBusy(RuntimeError):
    """Журнал уже держит другой процесс.

    Отдельный тип, потому что «занято» — это не ошибка данных: повтор через
    секунду обычно проходит, а вот трактовать занятость как отказ реестра
    значило бы уронить второй заказ вместо того, чтобы его подождать.
    """

    def __init__(self, path: Path) -> None:
        super().__init__(f"журнал {path} уже изменяется другим процессом")
        self.path = path


class LedgerError(RuntimeError):
    pass


def _lock_file(path: Path) -> Path:
    PATHS.locks.mkdir(parents=True, exist_ok=True)
    # Имя блокировки выводится из пути журнала, а не из его имени: два журнала
    # с именем state.json в разных каталогах делили бы один замок.
    key = str(path.resolve()).replace(os.sep, "_").strip("_")
    return PATHS.locks / f"ledger.{key}.lock"


@contextmanager
def exclusive(path: Path, *, timeout: float = 10.0) -> Iterator[None]:
    """Исключительный доступ к журналу на время блока."""
    lock = _lock_file(path)
    handle = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if timeout <= 0:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            import time

            deadline = time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise LedgerBusy(path) from None
                    time.sleep(0.02)
        yield
    except BlockingIOError:
        raise LedgerBusy(path) from None
    finally:
        try:
            fcntl.flock(handle, fcntl.LOCK_UN)
        finally:
            os.close(handle)


#: Отличает «умолчания нет» от «умолчание — None». Без него журнал, для
#: которого None является законным значением по умолчанию, падал бы вместо того,
#: чтобы вернуть это None.
MISSING = object()


def read(path: Path, *, default: Any = MISSING) -> Any:
    if not path.exists():
        if default is MISSING:
            raise LedgerError(f"журнала нет: {path}")
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LedgerError(f"журнал {path} повреждён: {exc}") from exc


def write(path: Path, payload: Any) -> None:
    """Запись через временный файл рядом и `os.replace`.

    Рядом — обязательно: `rename(2)` между файловыми системами не работает, и
    временный файл в /tmp сделал бы замену неатомарной именно на тех хостах, где
    /tmp вынесен отдельно.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    handle, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    # Каталог тоже синхронизируется: без этого переименование может не пережить
    # потерю питания, и журнал вернётся к прежнему содержимому уже после того,
    # как вызывающий счёл запись состоявшейся.
    dir_handle = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dir_handle)
    finally:
        os.close(dir_handle)


def mutate(path: Path, change: Callable[[Any], Any], *, default: Any = MISSING,
           timeout: float = 10.0) -> Any:
    """Прочитать, изменить и записать под блокировкой.

    `change` обязана вернуть новое содержимое журнала. Возврат `None` считается
    ошибкой, а не «ничего не менять»: молчаливый отказ записать — самый дорогой
    из возможных исходов, потому что вызывающий уверен в обратном.
    """
    with exclusive(path, timeout=timeout):
        current = read(path, default=default)
        updated = change(current)
        if updated is None:
            raise LedgerError("изменение журнала вернуло None; ожидалось новое содержимое")
        write(path, updated)
        return updated
