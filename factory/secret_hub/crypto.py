"""Мастер-ключ и шифрование значений.

Правила, которые модуль обязан удержать:

* мастер-ключ лежит в файле `root:root 0600` вне репозитория и не хранится в
  SQLite; сервису он выдаётся через systemd ``LoadCredential``;
* ключ и открытые значения не попадают в ``repr``, ``str``, сообщение
  исключения, лог, отчёт и argv — за этим следит :class:`Secret`;
* шифрование — AES-256-GCM: без аутентификации подмена шифртекста в SQLite
  осталась бы незамеченной, а «расшифровалось во что-то» превратилось бы в
  «применили мусор к сайту»;
* неправильный мастер-ключ обязан давать явный отказ, а не пустое значение.

Ключ шифрования записи не равен мастер-ключу: он выводится HKDF-SHA256 из
мастер-ключа и соли записи. Одна скомпрометированная запись не раскрывает
остальные, а смена соли при ротации даёт новый ключ без смены мастер-ключа.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from factory.errors import BlockedSecret
from factory.redaction import PLACEHOLDER, register_secret

#: Переменная, задающая путь к мастер-ключу. Значение — путь, никогда не ключ.
KEY_FILE_ENV = "SECRET_HUB_MASTER_KEY_FILE"
DEFAULT_KEY_FILE = "/etc/site-factory/secrets/secret-hub-master.key"

#: Имя credential'а systemd, под которым ключ приходит сервису.
CREDENTIAL_NAME = "secret_hub_master_key"
CREDENTIALS_DIR_ENV = "CREDENTIALS_DIRECTORY"

#: Права, при которых файл считается секретом.
ALLOWED_MODES = frozenset({0o600, 0o400})

#: Переменные, через которые ключ передавать запрещено. Проверяются явно:
#: удобный обходной путь появляется ровно тогда, когда его не проверяют.
FORBIDDEN_VALUE_ENV = (
    "SECRET_HUB_MASTER_KEY",
    "SECRET_HUB_KEY",
    "CDNVIDEOHUB_API_TOKEN",
    "CDNVIDEOHUB_PUBLISHER_ID",
)

KEY_BYTES = 32
SALT_BYTES = 16
NONCE_BYTES = 12
#: Версия схемы шифрования. Меняется вместе с алгоритмом, чтобы старые записи
#: расшифровывались тем же способом, каким были записаны.
SCHEME = "aes-256-gcm+hkdf-sha256/1"


class MasterKeyError(BlockedSecret):
    """Мастер-ключ отсутствует, испорчен или не подходит к шифртексту."""


class Secret:
    """Значение, которое нельзя случайно напечатать.

    ``str``, ``repr`` и форматирование дают «REDACTED». Значение достаётся
    единственным явным методом :meth:`reveal`, и вызывается он только внутри
    root-процесса сервиса — при записи файла потребителю и при сборке заголовка
    ``Authorization`` для проверки.
    """

    __slots__ = ("_value", "label")

    def __init__(self, value: str, label: str = "secret") -> None:
        self._value = value
        self.label = label
        register_secret(value)

    def reveal(self) -> str:
        return self._value

    def as_bytes(self) -> bytes:
        return self._value.encode("utf-8")

    def fingerprint(self) -> str:
        """Необратимый отпечаток «то же значение или нет».

        Отпечаток нужен ротации и отчёту: они обязаны замечать смену значения,
        не увидев ни одного его символа. Часть значения — тоже значение, поэтому
        «хвост токена» не показывается никогда. Соль фиксированная и публичная:
        отпечатки должны совпадать между запусками, иначе сравнивать нечего.
        """
        digest = hashlib.sha256(b"site-factory/secret-hub/fingerprint\x00" + self.as_bytes())
        return "sha256:" + digest.hexdigest()[:16]

    def __repr__(self) -> str:
        return f"<Secret {PLACEHOLDER} label={self.label}>"

    def __str__(self) -> str:
        return PLACEHOLDER

    def __format__(self, spec: str) -> str:
        return PLACEHOLDER

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Secret) and hmac.compare_digest(other._value, self._value)

    def __hash__(self) -> int:
        return hash(("Secret", self.label))

    def __len__(self) -> int:
        return len(self._value)

    def __bool__(self) -> bool:
        return bool(self._value)

    def __reduce__(self):
        raise TypeError("Secret не сериализуется: значение не покидает процесс")


@dataclass(frozen=True)
class KeyFileStatus:
    """Проверяемое состояние файла ключа. Самого ключа здесь нет и быть не может."""

    path: str
    exists: bool
    readable: bool
    mode: str | None
    owner_uid: int | None
    owner_is_root: bool
    group_or_world_readable: bool
    problems: tuple[str, ...]

    @property
    def stored_correctly(self) -> bool:
        """Ключ лежит правильно, даже если текущему пользователю он недоступен.

        Недоступность для сессии агента — не дефект хранения, а его цель.
        """
        return (
            self.exists
            and self.mode is not None
            and not self.group_or_world_readable
            and bool(self.owner_is_root)
        )

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "exists": self.exists,
            "readable": self.readable,
            "mode": self.mode,
            "owner_is_root": self.owner_is_root,
            "group_or_world_readable": self.group_or_world_readable,
            "stored_correctly": self.stored_correctly,
            "problems": list(self.problems),
        }


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


def key_path() -> Path:
    """Путь к мастер-ключу: явная переменная → credential systemd → умолчание.

    Путь вычисляется в коде, а не специфером ``%d`` в unit-файле: в systemd 249
    (Ubuntu 22.04) этого специфера нет, строка молча осталась бы literal-ом, и
    сервис падал бы на «файл не найден». ``CREDENTIALS_DIRECTORY`` systemd
    выставляет сам с той же версии, что и сам ``LoadCredential``.
    """
    configured = os.environ.get(KEY_FILE_ENV)
    if configured:
        return Path(configured).expanduser()
    directory = credentials_directory()
    if directory:
        candidate = directory / CREDENTIAL_NAME
        if candidate.exists():
            return candidate
    return Path(DEFAULT_KEY_FILE)


def forbidden_env_present() -> list[str]:
    """Имена переменных, в которые кто-то положил само значение."""
    return [name for name in FORBIDDEN_VALUE_ENV if os.environ.get(name)]


def inspect_key_file(path: Path | None = None) -> KeyFileStatus:
    """Состояние файла ключа без его чтения.

    Отдельная операция нужна `status` и отчёту: они обязаны уметь сказать «ключ
    на месте и закрыт правильно», ни разу не прикоснувшись к содержимому.
    """
    path = path or key_path()
    problems: list[str] = []
    try:
        info = path.stat()
    except FileNotFoundError:
        return KeyFileStatus(str(path), False, False, None, None, False, False,
                             ("файл мастер-ключа не найден",))
    except PermissionError:
        # Каталог секретов закрыт целиком (`drwx------ root:root`) — так и
        # должно быть. Сказать «не найден» здесь значило бы соврать, а упасть с
        # трассировкой — превратить работающую защиту в аварию.
        return KeyFileStatus(str(path), True, False, None, None, False, False,
                             ("каталог ключа недоступен текущей учётной записи: "
                              "состояние не измерено",))
    except OSError as exc:
        return KeyFileStatus(str(path), False, False, None, None, False, False,
                             (f"файл мастер-ключа не проверен ({exc.__class__.__name__})",))

    mode_bits = stat.S_IMODE(info.st_mode)
    mode = format(mode_bits, "04o")
    group_or_world = bool(mode_bits & 0o077)
    if mode_bits not in ALLOWED_MODES:
        problems.append(f"права {mode}, ожидается 0600 (или 0400)")
    if group_or_world:
        problems.append("файл читается группой или миром")
    credential = is_systemd_credential(path)
    if info.st_uid != 0 and not credential:
        problems.append(f"владелец uid={info.st_uid}, ожидается root")
    readable = os.access(path, os.R_OK)
    if not readable:
        problems.append("текущему пользователю файл недоступен на чтение")
    return KeyFileStatus(str(path), True, readable, mode, info.st_uid,
                         info.st_uid == 0 or credential, group_or_world, tuple(problems))


class MasterKey:
    """Мастер-ключ в памяти root-процесса. Наружу не выходит никогда."""

    __slots__ = ("_key", "source")

    def __init__(self, key: bytes, source: str) -> None:
        if len(key) != KEY_BYTES:
            raise MasterKeyError(
                f"Мастер-ключ имеет длину {len(key)} байт, ожидается {KEY_BYTES}.",
                field=KEY_FILE_ENV,
                required_input=f"{KEY_BYTES} случайных байт в hex или base64",
                blocks_stage="VALIDATING",
            )
        self._key = key
        self.source = source
        register_secret(key.hex())

    def derive(self, salt: bytes, info: bytes) -> bytes:
        """HKDF-SHA256: ключ записи из мастер-ключа и соли записи."""
        prk = hmac.new(salt, self._key, hashlib.sha256).digest()
        return hmac.new(prk, info + b"\x01", hashlib.sha256).digest()

    def key_id(self) -> str:
        """Публичный идентификатор ключа: сравнить «тот же ключ» без ключа."""
        return "sha256:" + hashlib.sha256(b"secret-hub/key-id\x00" + self._key).hexdigest()[:16]

    def __repr__(self) -> str:
        return f"<MasterKey {PLACEHOLDER} source={self.source}>"

    def __str__(self) -> str:
        return PLACEHOLDER

    def __format__(self, spec: str) -> str:
        return PLACEHOLDER

    def __reduce__(self):
        raise TypeError("MasterKey не сериализуется")


def _decode_key(raw: str, path: Path) -> bytes:
    """Ключ принимается в hex или base64 — но только правильной длины.

    Строка неверной длины — не «короткий ключ», а другой файл. Молча дополнять
    или обрезать её значило бы шифровать не тем, что задумано.
    """
    import base64
    import binascii

    text = raw.strip()
    if not text:
        raise MasterKeyError(
            f"Файл мастер-ключа {path} пуст. Пустое поле — не разрешение работать без ключа.",
            field=KEY_FILE_ENV,
            required_input=f"{KEY_BYTES} случайных байт в hex или base64",
            blocks_stage="VALIDATING",
        )
    if "\n" in text:
        raise MasterKeyError(
            f"Файл мастер-ключа {path} содержит несколько строк — формат не распознан.",
            field=KEY_FILE_ENV,
            required_input="Ровно одна строка: сам ключ",
            blocks_stage="VALIDATING",
        )
    for decoder in (lambda s: binascii.unhexlify(s), lambda s: base64.b64decode(s, validate=True)):
        try:
            candidate = decoder(text)
        except (binascii.Error, ValueError):
            continue
        if len(candidate) == KEY_BYTES:
            return candidate
    raise MasterKeyError(
        f"Файл мастер-ключа {path} не разобран: ожидается {KEY_BYTES} байт в hex или base64.",
        field=KEY_FILE_ENV,
        required_input=f"{KEY_BYTES} случайных байт в hex или base64, одной строкой",
        blocks_stage="VALIDATING",
    )


def load_master_key(path: Path | None = None, *, require_root_owner: bool = True) -> MasterKey:
    """Читает мастер-ключ. Любая проблема — ``BLOCKED_SECRET`` без содержимого файла.

    ``require_root_owner=False`` существует только для тестов на временных
    файлах, которыми не владеет root; на боевом пути значение по умолчанию.
    Права 0600 требуются всегда, в том числе в тестах.
    """
    leaked = forbidden_env_present()
    if leaked:
        raise MasterKeyError(
            f"Значение секрета передано переменной окружения ({', '.join(leaked)}). "
            f"Разрешён только файловый путь через {KEY_FILE_ENV}.",
            field=KEY_FILE_ENV,
            required_input=f"Убрать значение из окружения; путь задать через {KEY_FILE_ENV}",
            blocks_stage="VALIDATING",
        )

    path = path or key_path()
    if _inside_repository(path):
        raise MasterKeyError(
            f"Путь мастер-ключа {path} указывает внутрь репозитория. Ключ живёт только снаружи.",
            field=KEY_FILE_ENV,
            required_input=f"Путь вне репозитория, например {DEFAULT_KEY_FILE}",
            blocks_stage="VALIDATING",
        )

    status = inspect_key_file(path)
    if not status.exists:
        raise MasterKeyError(
            f"Файл мастер-ключа {path} не найден.",
            field=KEY_FILE_ENV,
            required_input=f"Мастер-ключ в {path}, владелец root:root, права 0600",
            blocks_stage="VALIDATING",
        )
    if status.group_or_world_readable:
        raise MasterKeyError(
            f"Файл мастер-ключа {path} доступен группе или миру (права {status.mode}).",
            field=KEY_FILE_ENV,
            required_input="chown root:root и chmod 0600 на файле ключа",
            blocks_stage="VALIDATING",
        )
    if status.mode is None:
        raise MasterKeyError(
            f"Состояние файла мастер-ключа {path} не проверено: каталог закрыт для текущей "
            "учётной записи. Ключ читает сервис, а не сессия агента.",
            field=KEY_FILE_ENV,
            required_input="Запуск от root-owned unit'а или через systemd LoadCredential",
            blocks_stage="VALIDATING",
        )
    if require_root_owner and not status.owner_is_root:
        raise MasterKeyError(
            f"Файл мастер-ключа {path} принадлежит uid={status.owner_uid}, ожидается root.",
            field=KEY_FILE_ENV,
            required_input="chown root:root на файле ключа",
            blocks_stage="VALIDATING",
        )
    if not status.readable:
        raise MasterKeyError(
            f"Файл мастер-ключа {path} недоступен на чтение текущему пользователю. "
            "Так и задумано: ключ читает сервис, а не сессия агента.",
            field=KEY_FILE_ENV,
            required_input="Запуск от учётной записи сервиса (systemd LoadCredential)",
            blocks_stage="VALIDATING",
        )

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        # В текст исключения попадает только класс ошибки: содержимое файла не
        # добавляется в сообщение ни при каком исходе.
        raise MasterKeyError(
            f"Файл мастер-ключа {path} не прочитан ({exc.__class__.__name__}).",
            field=KEY_FILE_ENV,
            required_input="Доступ на чтение файла ключа для учётной записи сервиса",
            blocks_stage="VALIDATING",
        ) from None
    return MasterKey(_decode_key(raw, path), source=str(path))


def _inside_repository(path: Path) -> bool:
    from factory.paths import PATHS

    root = PATHS.root.resolve()
    try:
        candidate = path.resolve()
    except OSError:
        candidate = path
    return candidate == root or str(candidate).startswith(str(root) + os.sep)


# --- собственно шифрование ------------------------------------------------
#
# AES-256-GCM берётся из `cryptography`: собственная реализация блочного шифра
# здесь была бы худшим решением в файле. Модуль импортируется лениво, чтобы
# отсутствие зависимости давало внятный BLOCKED_SECRET, а не ImportError в
# середине применения.


def _aesgcm():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ModuleNotFoundError:
        raise MasterKeyError(
            "Пакет cryptography не установлен: шифровать нечем. "
            "Хранить значения в открытом виде вместо этого запрещено.",
            field="requirements.txt",
            required_input="pip install -r requirements.txt (cryptography)",
            blocks_stage="VALIDATING",
        ) from None
    return AESGCM


@dataclass(frozen=True)
class Envelope:
    """Зашифрованное значение в том виде, в каком оно ложится в SQLite."""

    scheme: str
    salt: bytes
    nonce: bytes
    ciphertext: bytes
    key_id: str

    def __repr__(self) -> str:  # шифртекст в лог тоже не нужен
        return f"<Envelope scheme={self.scheme} key_id={self.key_id} bytes={len(self.ciphertext)}>"


def encrypt(master: MasterKey, secret: Secret, *, aad: bytes) -> Envelope:
    """Шифрует значение. ``aad`` связывает шифртекст с его местом в хранилище.

    В ``aad`` уходят направление, имя поля и версия: перенос шифртекста из
    записи `lords/api_token` в `yami/api_token` перестаёт расшифровываться, а не
    подменяет чужой секрет молча.
    """
    salt = os.urandom(SALT_BYTES)
    nonce = os.urandom(NONCE_BYTES)
    key = master.derive(salt, b"secret-hub/record")
    ciphertext = _aesgcm()(key).encrypt(nonce, secret.as_bytes(), aad)
    return Envelope(SCHEME, salt, nonce, ciphertext, master.key_id())


def decrypt(master: MasterKey, envelope: Envelope, *, aad: bytes, label: str = "secret") -> Secret:
    """Расшифровывает значение. Неверный ключ — явный отказ, а не пустая строка."""
    if envelope.scheme != SCHEME:
        raise MasterKeyError(
            f"Запись зашифрована схемой «{envelope.scheme}», процесс умеет «{SCHEME}».",
            field="store.sqlite3",
            required_input="Хранилище, записанное поддерживаемой версией Secret Hub",
            blocks_stage="VALIDATING",
        )
    key = master.derive(envelope.salt, b"secret-hub/record")
    try:
        plaintext = _aesgcm()(key).decrypt(envelope.nonce, envelope.ciphertext, aad)
    except Exception:
        # Сюда приходят и «не тот ключ», и «шифртекст подменили»: GCM их не
        # различает, и различать их не нужно — оба означают «не расшифровано».
        # Текст исключения библиотеки не пробрасывается: он ничего не добавляет,
        # а в лог попадает.
        raise MasterKeyError(
            "Значение не расшифровано: мастер-ключ не подходит либо запись повреждена. "
            f"Ожидался ключ {envelope.key_id}, процесс работает с {master.key_id()}.",
            field=KEY_FILE_ENV,
            required_input="Тот мастер-ключ, которым запись была зашифрована",
            blocks_stage="VALIDATING",
        ) from None
    return Secret(plaintext.decode("utf-8"), label=label)


def generate_master_key() -> str:
    """Новый мастер-ключ в hex. Вызывается только root-командой установки."""
    return os.urandom(KEY_BYTES).hex()
