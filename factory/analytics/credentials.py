"""Чтение OAuth-токена Яндекса. Единственное место в фабрике, где он существует.

Правила, которые модуль обязан удержать:

* токен читается только из файла вне репозитория, путь задаётся
  ``YANDEX_OAUTH_TOKEN_FILE`` (значение по умолчанию — :data:`DEFAULT_TOKEN_FILE`);
* значение не попадает в ``repr``, ``str``, сообщение исключения, лог, аудит,
  отчёт, артефакт и тем более в git — за этим следит :class:`OAuthToken`;
* сразу после чтения значение регистрируется в :mod:`factory.redaction`, поэтому
  даже случайная утечка в чужой строке будет вырезана;
* права файла проверяются до чтения: доступный группе или миру секрет
  секретом не является.
"""
from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from factory.errors import BlockedSecret
from factory.redaction import PLACEHOLDER, register_secret

#: Переменная, задающая путь. Значение — путь, никогда не сам токен.
TOKEN_FILE_ENV = "YANDEX_OAUTH_TOKEN_FILE"

#: Каталог секретов хоста. Вне репозитория и закрыт для всех, кроме root.
SECRET_DIR = "/etc/site-factory/secrets"
DEFAULT_TOKEN_FILE = f"{SECRET_DIR}/yandex_oauth_token"

#: Права, при которых файл считается секретом: читает только владелец.
ALLOWED_MODES = frozenset({0o600, 0o400})

#: Переменные, через которые токен передавать запрещено. Проверяются явно:
#: удобный обходной путь появляется ровно тогда, когда его не проверяют.
FORBIDDEN_VALUE_ENV = (
    "YANDEX_OAUTH_TOKEN",
    "YANDEX_METRIKA_TOKEN",
    "YANDEX_WEBMASTER_TOKEN",
    "YANDEX_TOKEN",
)


class OAuthToken:
    """Носитель значения токена, который нельзя случайно напечатать.

    ``str``, ``repr`` и форматирование дают «REDACTED». Значение достаётся
    единственным явным методом :meth:`reveal`, и в фабрике он вызывается ровно
    один раз — при сборке заголовка ``Authorization``.
    """

    __slots__ = ("_value", "source")

    def __init__(self, value: str, source: str) -> None:
        self._value = value
        self.source = source
        register_secret(value)

    def reveal(self) -> str:
        return self._value

    def authorization_header(self) -> str:
        # Формат из официальной документации: `Authorization: OAuth <token>`.
        return f"OAuth {self._value}"

    def fingerprint(self) -> str:
        """Необратимый отпечаток для сравнения «тот же токен или нет».

        Нужен проверке ротации: она обязана заметить смену токена, не увидев ни
        одного его символа. Часть значения — тоже значение, поэтому «хвост
        токена» не показывается никогда.
        """
        return hashlib.sha256(self._value.encode("utf-8")).hexdigest()[:16]

    # --- всё, что может напечатать значение, обезврежено ------------------
    def __repr__(self) -> str:
        return f"<OAuthToken {PLACEHOLDER} source={self.source}>"

    def __str__(self) -> str:
        return PLACEHOLDER

    def __format__(self, spec: str) -> str:
        return PLACEHOLDER

    def __eq__(self, other: object) -> bool:
        return isinstance(other, OAuthToken) and other._value == self._value

    def __hash__(self) -> int:  # набор токенов не должен раскрывать значение
        return hash(("OAuthToken", self.source))

    def __len__(self) -> int:
        return len(self._value)

    def __bool__(self) -> bool:
        return bool(self._value)

    def __reduce__(self):
        # Пикл секрета — это запись секрета на диск. Запрещаем явно.
        raise TypeError("OAuthToken не сериализуется: значение секрета не покидает процесс")


@dataclass(frozen=True)
class TokenFileStatus:
    """Проверяемое состояние файла секрета. Значения токена здесь нет и быть не может."""

    path: str
    exists: bool
    readable: bool
    mode: str | None
    owner_uid: int | None
    owner_is_root: bool
    group_or_world_readable: bool
    problems: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.exists and self.readable and not self.problems

    @property
    def stored_correctly(self) -> bool:
        """Секрет лежит правильно, даже если текущему пользователю он недоступен.

        Недоступность для сессии агента — это не дефект хранения, а его цель.
        """
        return (
            self.exists
            and self.mode is not None      # состояние действительно измерено
            and not self.group_or_world_readable
            and bool(self.owner_is_root)
        )

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "exists": self.exists,
            "readable": self.readable,
            "mode": self.mode,
            "owner_uid": self.owner_uid,
            "owner_is_root": self.owner_is_root,
            "group_or_world_readable": self.group_or_world_readable,
            "stored_correctly": self.stored_correctly,
            "problems": list(self.problems),
            "ok": self.ok,
        }


#: Каталог, куда systemd кладёт переданные unit'у credentials. Файл там
#: принадлежит учётной записи сервиса, а не root, и лежит в tmpfs — это штатный
#: способ выдать секрет непривилегированному процессу, а не ослабление правила.
CREDENTIALS_DIR_ENV = "CREDENTIALS_DIRECTORY"


def credentials_directory() -> Path | None:
    raw = os.environ.get(CREDENTIALS_DIR_ENV)
    return Path(raw) if raw else None


def is_systemd_credential(path: Path) -> bool:
    directory = credentials_directory()
    if not directory:
        return False
    try:
        return str(path.resolve()).startswith(str(directory.resolve()) + os.sep)
    except OSError:
        return False


def token_path() -> Path:
    return Path(os.environ.get(TOKEN_FILE_ENV) or DEFAULT_TOKEN_FILE).expanduser()


def inside_repository(path: Path, repo_root: Path | None = None) -> bool:
    """Лежит ли файл секрета внутри репозитория. Должно быть ``False`` всегда."""
    from factory.paths import PATHS

    root = (repo_root or PATHS.root).resolve()
    try:
        candidate = path.resolve()
    except OSError:
        candidate = path
    return candidate == root or str(candidate).startswith(str(root) + os.sep)


def forbidden_env_present() -> list[str]:
    """Имена переменных, в которые кто-то положил само значение токена."""
    return [name for name in FORBIDDEN_VALUE_ENV if os.environ.get(name)]


def inspect_token_file(path: Path | None = None) -> TokenFileStatus:
    """Состояние файла секрета без его чтения.

    Отдельная операция нужна отчёту и проверке ротации: они обязаны уметь
    сказать «секрет на месте и закрыт правильно», ни разу не прикоснувшись к
    содержимому.
    """
    path = path or token_path()
    problems: list[str] = []

    if inside_repository(path):
        problems.append("файл секрета лежит внутри репозитория")

    try:
        info = path.stat()
    except FileNotFoundError:
        return TokenFileStatus(str(path), False, False, None, None, False, False,
                               (*problems, "файл секрета не найден"))
    except PermissionError:
        # Каталог секрета закрыт целиком (`drwx------ root:root`) — так и должно
        # быть. Это не поломка и не «файла нет»: сказать «не найден» здесь значило
        # бы соврать, а упасть с трассировкой — превратить работающую защиту в
        # аварию. Честный ответ: состояние не измерено, причина названа.
        return TokenFileStatus(str(path), True, False, None, None, False, False,
                               (*problems, "каталог секрета недоступен текущему пользователю: "
                                           "состояние файла не измерено"))
    except OSError as exc:
        return TokenFileStatus(str(path), False, False, None, None, False, False,
                               (*problems, f"файл секрета не проверен ({exc.__class__.__name__})"))
    mode_bits = stat.S_IMODE(info.st_mode)
    mode = format(mode_bits, "04o")
    group_or_world = bool(mode_bits & 0o077)

    if mode_bits not in ALLOWED_MODES:
        problems.append(f"права {mode}, ожидается 0600 (или 0400)")
    if group_or_world:
        problems.append("файл читается группой или миром")
    systemd_credential = is_systemd_credential(path)
    if info.st_uid != 0 and not systemd_credential:
        problems.append(f"владелец uid={info.st_uid}, ожидается root")
    if systemd_credential and info.st_uid not in (0, os.geteuid()):
        problems.append(
            f"credential systemd принадлежит uid={info.st_uid}, а сервис работает от {os.geteuid()}")
    readable = os.access(path, os.R_OK)
    if not readable:
        # Не поломка секрета, а факт среды: доступ выдаётся сервисной учётке.
        problems.append("текущему пользователю файл недоступен на чтение")

    return TokenFileStatus(str(path), True, readable, mode, info.st_uid,
                           info.st_uid == 0 or systemd_credential, group_or_world, tuple(problems))


def load_token(path: Path | None = None, *, require_root_owner: bool = True) -> OAuthToken:
    """Читает токен. Любая проблема — ``BLOCKED_SECRET`` без содержимого файла.

    ``require_root_owner=False`` существует только для тестов на временных
    файлах, которыми не владеет root; на боевом пути значение по умолчанию.
    Права 0600 требуются всегда, в том числе в тестах.
    """
    leaked = forbidden_env_present()
    if leaked:
        raise BlockedSecret(
            "Значение OAuth-токена передано переменной окружения "
            f"({', '.join(leaked)}). Разрешён только файловый путь через {TOKEN_FILE_ENV}.",
            field=TOKEN_FILE_ENV,
            required_input=f"Убрать значение из окружения; путь к файлу задать через {TOKEN_FILE_ENV}",
            blocks_stage="VALIDATING",
        )

    path = path or token_path()
    status = inspect_token_file(path)

    if inside_repository(path):
        raise BlockedSecret(
            f"Путь секрета {path} указывает внутрь репозитория. Секрет хранится только снаружи.",
            field=TOKEN_FILE_ENV,
            required_input=f"Путь вне репозитория, например {DEFAULT_TOKEN_FILE}",
            blocks_stage="VALIDATING",
        )
    if not status.exists:
        raise BlockedSecret(
            f"Файл секрета {path} не найден.",
            field=TOKEN_FILE_ENV,
            required_input=f"OAuth-токен Яндекса в файле {path} с владельцем root:root и правами 0600",
            blocks_stage="VALIDATING",
        )
    if status.group_or_world_readable:
        raise BlockedSecret(
            f"Файл секрета {path} доступен группе или миру (права {status.mode}).",
            field=TOKEN_FILE_ENV,
            required_input="chown root:root и chmod 0600 на файле секрета",
            blocks_stage="VALIDATING",
        )
    if status.mode is None:
        # Состояние файла не измерено: каталог секрета закрыт целиком. Говорить
        # «владелец не root» здесь неправильно — владелец неизвестен, и назвать
        # причиной непроверенное условие значит отправить оператора чинить
        # исправное.
        raise BlockedSecret(
            f"Состояние файла секрета {path} не проверено: каталог закрыт для текущей "
            "учётной записи. Токен читает сервис, а не сессия агента.",
            field=TOKEN_FILE_ENV,
            required_input=(
                "Запуск от учётной записи с доступом к секрету "
                "(root-owned systemd unit или systemd LoadCredential)"
            ),
            blocks_stage="VALIDATING",
        )
    if require_root_owner and not status.owner_is_root and not is_systemd_credential(path):
        raise BlockedSecret(
            f"Файл секрета {path} принадлежит uid={status.owner_uid}, ожидается root.",
            field=TOKEN_FILE_ENV,
            required_input="chown root:root на файле секрета",
            blocks_stage="VALIDATING",
        )
    if not status.readable:
        raise BlockedSecret(
            f"Файл секрета {path} недоступен на чтение текущему пользователю. "
            "Так и задумано: токен читает сервисная учётная запись, а не сессия агента.",
            field=TOKEN_FILE_ENV,
            required_input=(
                "Запуск от учётной записи, которой владелец выдал доступ "
                "(systemd LoadCredential или root-owned unit)"
            ),
            blocks_stage="VALIDATING",
        )

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        # В текст исключения попадает только класс ошибки: содержимое файла
        # не добавляется в сообщение ни при каком исходе.
        raise BlockedSecret(
            f"Файл секрета {path} не прочитан ({exc.__class__.__name__}).",
            field=TOKEN_FILE_ENV,
            required_input="Доступ на чтение файла секрета для учётной записи сервиса",
            blocks_stage="VALIDATING",
        ) from None

    value = raw.strip()
    if not value:
        raise BlockedSecret(
            f"Файл секрета {path} пуст. Пустое поле — не разрешение работать без токена.",
            field=TOKEN_FILE_ENV,
            required_input="Непустой OAuth-токен Яндекса в файле секрета",
            blocks_stage="VALIDATING",
        )
    if "\n" in value:
        raise BlockedSecret(
            f"Файл секрета {path} содержит несколько строк — формат не распознан.",
            field=TOKEN_FILE_ENV,
            required_input="Ровно одна строка: сам токен",
            blocks_stage="VALIDATING",
        )
    return OAuthToken(value, source=str(path))
