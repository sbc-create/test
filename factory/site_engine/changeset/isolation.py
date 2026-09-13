"""Защита от работы испытаний по общему хранилищу.

Путь к базе берётся из `CHANGESET_DB`, а при отсутствии переменной
подставляется общий. Тихое значение по умолчанию удобно в рабочем контуре и
опасно в испытаниях: прогон, забывший задать переменную, пишет в общее
хранилище и выглядит при этом совершенно исправным. Именно так в общей базе
оказались двенадцать строк прогона SEO R4.

Здесь проверка закрытая: совпадение по DSN, по разрешённому пути и по inode.
Последнее важно отдельно — жёсткая ссылка или связка символических ссылок
дают разные имена одного и того же файла, и сравнение строк их не различает.
"""
from __future__ import annotations

import os
from pathlib import Path

#: Каноническое общее хранилище. Испытание не вправе его открывать.
ОБЩЕЕ = "/srv/site-factory/changeset-store/changesets.sqlite3"


class SharedStoreRefused(RuntimeError):
    """Испытание попыталось работать по общему хранилищу."""

    def __init__(self, detail: str, *, признак: str):
        super().__init__(detail)
        self.error_code = "SHARED_STORE_REFUSED"
        self.detail, self.признак = detail, признак


def _inode(путь: str) -> tuple[int, int] | None:
    try:
        с = os.stat(путь)
    except OSError:
        return None
    return (с.st_dev, с.st_ino)


def требовать_эфемерное(путь: str | Path | None = None, *,
                        общее: str = ОБЩЕЕ) -> str:
    """Вернуть путь, убедившись, что это не общее хранилище.

    Отсутствие явного пути — тоже отказ: молчаливый возврат к значению по
    умолчанию и есть та ошибка, ради которой функция написана.
    """
    сырой = str(путь) if путь is not None else os.environ.get("CHANGESET_DB", "")
    if not сырой.strip():
        raise SharedStoreRefused(
            "путь к хранилищу не задан явно: подстановка общего значения по "
            "умолчанию в испытаниях запрещена",
            признак="unset")

    if сырой == общее:
        raise SharedStoreRefused(
            f"указано общее хранилище {общее}", признак="dsn")

    разрешённый = os.path.realpath(сырой)
    if разрешённый == os.path.realpath(общее):
        raise SharedStoreRefused(
            f"путь {сырой} разрешается в общее хранилище {разрешённый}",
            признак="realpath")

    свой, чужой = _inode(разрешённый), _inode(общее)
    if свой is not None and свой == чужой:
        raise SharedStoreRefused(
            f"путь {сырой} указывает на тот же файл, что и общее хранилище "
            f"(устройство и inode совпали)", признак="inode")

    # Каталог общего хранилища целиком: соседние файлы там тоже не наши.
    if Path(разрешённый).parent == Path(os.path.realpath(общее)).parent:
        raise SharedStoreRefused(
            f"путь {сырой} ведёт в каталог общего хранилища",
            признак="directory")
    return разрешённый


def эфемерное_окружение(каталог: str | Path) -> dict[str, str]:
    """Набор переменных для изолированного прогона.

    Возвращает именно словарь, а не правит окружение процесса: правка на
    месте переживает прогон и однажды достаётся следующему.
    """
    к = Path(каталог)
    к.mkdir(parents=True, exist_ok=True)
    пути = {
        "CHANGESET_DB": str(к / "changesets.sqlite3"),
        "AUDIT_LEDGER_DB": str(к / "ledger.sqlite3"),
        "AUDIT_FEED": str(к / "feed.jsonl"),
        "SEO_SURFACE_DB": str(к / "seo-surface.sqlite3"),
        "FAKE_ADAPTER_DB": str(к / "fake.sqlite3"),
        "CHANGESET_BACKUP_DIR": str(к / "backups"),
        "CHANGESET_WORKER_LOCK": str(к / "worker.lock"),
    }
    требовать_эфемерное(пути["CHANGESET_DB"])
    return пути
