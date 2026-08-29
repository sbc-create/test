"""Чтение учётных данных Topvisor. Единственное место в фабрике, где они существуют.

Правила те же, что для OAuth-токена Яндекса, и по той же причине: значение,
попавшее в лог или отчёт, уже утекло, а отозвать его может только владелец.

* значения читаются из файлов вне репозитория;
* ключ регистрируется в :mod:`factory.redaction` сразу после чтения, поэтому
  случайное попадание в чужую строку будет вырезано;
* ключ не появляется в ``repr``, ``str``, тексте исключения и аудите;
* права файла проверяются до чтения.

Про режим ``0440``. Для токена Яндекса разрешены только ``0600``/``0400``:
он нужен единственному процессу от имени владельца. Учётные данные Topvisor
владелец выдал под ``0440 root:ubuntu`` осознанно — файл принадлежит root, а
читает его группа обслуживания. Это не ослабление правила, а другое, тоже
закрытое, распределение доступа: мир не читает файл ни в одном из режимов.
Именно попытка ужесточить права до ``0400`` однажды оставила процесс без
доступа к собственному секрету, поэтому набор задан явно и с объяснением.
"""
from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field
from pathlib import Path

from factory.errors import BlockedSecret
from factory.redaction import register_secret

#: Каталог с учётными данными. Задаётся переменной только ради тестов;
#: значение — путь, никогда не сам ключ.
SECRET_DIR_ENV = "TOPVISOR_SECRET_DIR"
DEFAULT_SECRET_DIR = "/etc/site-factory/secrets/topvisor"

USER_ID_FILE = "user-id"
API_KEY_FILE = "api-key"

#: Права, при которых файл считается секретом. Мир не читает ни в одном из них.
ALLOWED_MODES = frozenset({0o400, 0o440, 0o600, 0o640})

#: Передавать ключ через окружение запрещено: переменные попадают в дампы,
#: в вывод `ps` у части систем и в отчёты об ошибках целиком.
FORBIDDEN_VALUE_ENV = ("TOPVISOR_API_KEY", "TOPVISOR_KEY", "TOPVISOR_TOKEN")


def secret_dir() -> Path:
    return Path(os.environ.get(SECRET_DIR_ENV) or DEFAULT_SECRET_DIR)


@dataclass(frozen=True)
class TopvisorCredentials:
    """Пара «идентификатор пользователя и ключ».

    Идентификатор секретом не является и печатается свободно: он виден в
    интерфейсе Topvisor и нужен в отчётах, чтобы владелец понимал, о каком
    аккаунте речь. Ключ — является, и наружу не отдаётся никогда.
    """

    user_id: str
    _api_key: str = field(repr=False)

    def __repr__(self) -> str:  # pragma: no cover - тривиально, но проверяется тестом
        return f"TopvisorCredentials(user_id={self.user_id!r}, api_key=«скрыт»)"

    __str__ = __repr__

    def authorization_header(self) -> str:
        """Собирается в момент отправки и нигде не сохраняется."""
        return f"bearer {self._api_key}"


def _check_mode(path: Path) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode not in ALLOWED_MODES:
        raise BlockedSecret(
            f"Права {oct(mode)} у {path.name} не подходят: секрет не должен быть доступен миру",
            field="topvisor.credentials",
            required_input=f"chmod 0440 {path}",
            blocks_stage="topvisor",
        )


def _read(path: Path) -> str:
    try:
        missing = not path.exists()
    except PermissionError as exc:
        # `exists()` тоже обращается к файловой системе и тоже может упереться
        # в права: без этой ветки отсутствие доступа выходило сырым traceback
        # вместо понятного блокера с указанием, что делать.
        raise BlockedSecret(
            f"Нет доступа к каталогу с {path.name}: процесс не в группе, которой выдан файл",
            field="topvisor.credentials",
            required_input=f"запустить от учётной записи в группе-владельце {path.parent}",
            blocks_stage="topvisor",
        ) from exc
    if missing:
        raise BlockedSecret(
            f"Нет файла {path.name}: учётные данные Topvisor не введены",
            field="topvisor.credentials",
            required_input=f"sudo python3 -m factory.topvisor.enroll  # скрытый ввод в {path.parent}",
            blocks_stage="topvisor",
        )
    _check_mode(path)
    try:
        value = path.read_text(encoding="utf-8").strip()
    except PermissionError as exc:
        raise BlockedSecret(
            f"Нет доступа к {path.name}: процесс не в группе, которой выдан файл",
            field="topvisor.credentials",
            required_input=f"запустить от учётной записи в группе-владельце {path}",
            blocks_stage="topvisor",
        ) from exc
    if not value:
        # Пустой файл — не разрешение работать без значения.
        raise BlockedSecret(
            f"Файл {path.name} пуст",
            field="topvisor.credentials",
            required_input="ввести значение заново",
            blocks_stage="topvisor",
        )
    return value


def load() -> TopvisorCredentials:
    for name in FORBIDDEN_VALUE_ENV:
        if os.environ.get(name):
            raise BlockedSecret(
                f"{name} передан через окружение: ключ так передавать нельзя",
                field="topvisor.credentials",
                required_input=f"убрать {name} из окружения; значение читается из файла",
                blocks_stage="topvisor",
            )
    directory = secret_dir()
    user_id = _read(directory / USER_ID_FILE)
    api_key = _read(directory / API_KEY_FILE)
    if not user_id.isdigit():
        raise BlockedSecret(
            "Идентификатор пользователя Topvisor должен состоять из цифр",
            field="topvisor.user_id",
            required_input="ввести значение заново",
            blocks_stage="topvisor",
        )
    register_secret(api_key)
    return TopvisorCredentials(user_id=user_id, _api_key=api_key)
