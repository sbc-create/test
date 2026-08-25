"""База панели: passkey'и, recovery-коды, challenge, сессии, счётчики попыток.

Ни одного секрета направления здесь нет и быть не может. Лежат:

* **публичные ключи passkey'ев** — публичные по определению;
* **хеши recovery-кодов** — scrypt, восстановить код нельзя;
* **одноразовые challenge** — короткоживущие случайные строки, каждая
  удаляется в момент использования;
* **сессии** — идентификаторы, не дающие ничего, кроме права спросить хаб;
* **счётчики попыток** — для rate limit.

Файл принадлежит непривилегированной учётной записи панели и закрыт правами
0600. Потеря этой базы означает необходимость заново зарегистрировать passkey
через root-установку — но не утечку credentials направлений.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import stat
import threading
import time
from dataclasses import dataclass
from pathlib import Path

DIR_MODE = 0o700
FILE_MODE = 0o600

#: Сколько живёт challenge. WebAuthn-церемония занимает секунды; минута — с
#: запасом на раздумье владельца у диалога Touch ID.
CHALLENGE_TTL_SECONDS = 120

#: Параметры scrypt для recovery-кодов. Код высокоэнтропийный (>= 80 бит),
#: поэтому цель параметров — не растянуть слабый секрет, а сделать перебор
#: украденной базы бессмысленным.
SCRYPT_N = 2 ** 14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_SALT_BYTES = 16
SCRYPT_KEY_LEN = 32

SCHEMA = """
CREATE TABLE IF NOT EXISTS passkey (
    credential_id   TEXT PRIMARY KEY,
    public_key      BLOB NOT NULL,
    sign_count      INTEGER NOT NULL DEFAULT 0,
    label           TEXT NOT NULL DEFAULT '',
    created_at      REAL NOT NULL,
    last_used_at    REAL
);

CREATE TABLE IF NOT EXISTS recovery_code (
    code_id         TEXT PRIMARY KEY,
    salt            BLOB NOT NULL,
    hash            BLOB NOT NULL,
    created_at      REAL NOT NULL,
    used_at         REAL
);

CREATE TABLE IF NOT EXISTS challenge (
    challenge_id    TEXT PRIMARY KEY,
    value           BLOB NOT NULL,
    purpose         TEXT NOT NULL,
    created_at      REAL NOT NULL,
    expires_at      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS session (
    session_id      TEXT PRIMARY KEY,
    csrf            TEXT NOT NULL,
    created_at      REAL NOT NULL,
    expires_at      REAL NOT NULL,
    label           TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS enrollment (
    enrollment_id   TEXT PRIMARY KEY,
    salt            BLOB NOT NULL,
    hash            BLOB NOT NULL,
    created_at      REAL NOT NULL,
    expires_at      REAL NOT NULL,
    used_at         REAL
);

CREATE TABLE IF NOT EXISTS attempt (
    bucket          TEXT NOT NULL,
    at              REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS attempt_bucket_at ON attempt(bucket, at);

CREATE TABLE IF NOT EXISTS applied_request (
    request_id      TEXT PRIMARY KEY,
    response        TEXT NOT NULL,
    created_at      REAL NOT NULL
);
"""


def hash_code(code: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """scrypt-хеш одноразового кода. Возвращает соль и хеш."""
    salt = salt or os.urandom(SCRYPT_SALT_BYTES)
    digest = hashlib.scrypt(code.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R,
                            p=SCRYPT_P, dklen=SCRYPT_KEY_LEN)
    return salt, digest


def verify_code(code: str, salt: bytes, expected: bytes) -> bool:
    _, digest = hash_code(code, salt)
    return hmac.compare_digest(digest, expected)


def generate_code(groups: int = 4, size: int = 5) -> str:
    """Читаемый код без похожих символов: его вводят глазами с экрана."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "-".join(
        "".join(secrets.choice(alphabet) for _ in range(size)) for _ in range(groups)
    )


@dataclass(frozen=True)
class Passkey:
    credential_id: str
    public_key: bytes
    sign_count: int
    label: str
    created_at: float
    last_used_at: float | None

    def as_dict(self) -> dict:
        return {
            "credential_id": self.credential_id[:12] + "…",
            "label": self.label,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
        }


@dataclass(frozen=True)
class Session:
    session_id: str
    csrf: str
    expires_at: float
    label: str


class PanelStore:
    """База панели. Открывается непривилегированным процессом панели."""

    def __init__(self, db_path: Path, *, enforce_permissions: bool = True) -> None:
        self.db_path = db_path
        self._enforce = enforce_permissions
        self._lock = threading.RLock()
        directory = db_path.parent
        directory.mkdir(parents=True, exist_ok=True, mode=DIR_MODE)
        if enforce_permissions:
            os.chmod(directory, DIR_MODE)
        if not db_path.exists():
            fd = os.open(db_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, FILE_MODE)
            os.close(fd)
        self._conn = sqlite3.connect(str(db_path), isolation_level=None,
                                     check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.executescript(SCHEMA)
        self._enforce_modes()

    def _enforce_modes(self) -> None:
        if not self._enforce:
            return
        for suffix in ("", "-wal", "-shm"):
            path = self.db_path.with_name(self.db_path.name + suffix)
            if path.exists():
                os.chmod(path, FILE_MODE)

    def check_permissions(self) -> list[str]:
        problems: list[str] = []
        try:
            mode = stat.S_IMODE(self.db_path.parent.stat().st_mode)
            if mode & 0o077:
                problems.append(f"каталог панели доступен группе или миру ({mode:04o})")
        except OSError as exc:
            problems.append(f"каталог панели не проверен ({exc.__class__.__name__})")
        for suffix in ("", "-wal", "-shm"):
            path = self.db_path.with_name(self.db_path.name + suffix)
            if path.exists() and stat.S_IMODE(path.stat().st_mode) & 0o077:
                problems.append(f"{path} доступен группе или миру")
        return problems

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> PanelStore:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- passkeys ---------------------------------------------------------
    def add_passkey(self, credential_id: str, public_key: bytes, sign_count: int,
                    label: str = "") -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO passkey (credential_id, public_key, sign_count, label, created_at)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(credential_id) DO UPDATE SET public_key = excluded.public_key,"
                " sign_count = excluded.sign_count, label = excluded.label",
                (credential_id, public_key, sign_count, label, time.time()),
            )
            self._enforce_modes()

    def passkeys(self) -> list[Passkey]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM passkey ORDER BY created_at").fetchall()
        return [Passkey(r["credential_id"], r["public_key"], r["sign_count"], r["label"],
                        r["created_at"], r["last_used_at"]) for r in rows]

    def passkey(self, credential_id: str) -> Passkey | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM passkey WHERE credential_id = ?",
                                     (credential_id,)).fetchone()
        if row is None:
            return None
        return Passkey(row["credential_id"], row["public_key"], row["sign_count"],
                       row["label"], row["created_at"], row["last_used_at"])

    def update_sign_count(self, credential_id: str, sign_count: int) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE passkey SET sign_count = ?, last_used_at = ? WHERE credential_id = ?",
                (sign_count, time.time(), credential_id),
            )

    def has_passkey(self) -> bool:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM passkey").fetchone()
        return bool(row["n"])

    # --- challenge --------------------------------------------------------
    def put_challenge(self, value: bytes, purpose: str) -> str:
        """Сохраняет challenge и возвращает его идентификатор.

        Идентификатор кладётся в cookie, значение остаётся здесь. Так браузер
        не может подсунуть своё значение challenge, а может лишь сослаться на
        выданное.
        """
        challenge_id = secrets.token_urlsafe(24)
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO challenge (challenge_id, value, purpose, created_at, expires_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (challenge_id, value, purpose, now, now + CHALLENGE_TTL_SECONDS),
            )
            self._conn.execute("DELETE FROM challenge WHERE expires_at < ?", (now,))
        return challenge_id

    def take_challenge(self, challenge_id: str, purpose: str) -> bytes | None:
        """Забирает challenge, удаляя его. Повторный вызов вернёт ``None``.

        Одноразовость здесь — не удобство, а требование: challenge, который
        можно предъявить дважды, превращает перехваченный ответ аутентификатора
        в многоразовый пропуск.
        """
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT value, expires_at FROM challenge WHERE challenge_id = ? AND purpose = ?",
                (challenge_id, purpose),
            ).fetchone()
            if row is None:
                return None
            self._conn.execute("DELETE FROM challenge WHERE challenge_id = ?", (challenge_id,))
            if row["expires_at"] < now:
                return None
            return row["value"]

    # --- recovery ---------------------------------------------------------
    def replace_recovery_codes(self, codes: list[str]) -> None:
        """Записывает хеши новых кодов, стирая прежние.

        Сами коды здесь не сохраняются: показать их владельцу — задача
        вызывающего, и ровно один раз.
        """
        now = time.time()
        with self._lock:
            self._conn.execute("DELETE FROM recovery_code")
            for code in codes:
                salt, digest = hash_code(code)
                self._conn.execute(
                    "INSERT INTO recovery_code (code_id, salt, hash, created_at)"
                    " VALUES (?, ?, ?, ?)",
                    (secrets.token_urlsafe(12), salt, digest, now),
                )
            self._enforce_modes()

    def consume_recovery_code(self, code: str) -> bool:
        """Проверяет и гасит код. Один код — одно использование."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT code_id, salt, hash FROM recovery_code WHERE used_at IS NULL"
            ).fetchall()
            for row in rows:
                if verify_code(code, row["salt"], row["hash"]):
                    self._conn.execute(
                        "UPDATE recovery_code SET used_at = ? WHERE code_id = ?",
                        (time.time(), row["code_id"]),
                    )
                    return True
        return False

    def recovery_status(self) -> dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS total, SUM(used_at IS NOT NULL) AS used FROM recovery_code"
            ).fetchone()
        total = row["total"] or 0
        used = row["used"] or 0
        return {"total": total, "used": used, "left": total - used}

    # --- enrollment (первичная регистрация) -------------------------------
    def create_enrollment(self, ttl_seconds: int) -> str:
        """Одноразовый код первичной регистрации. Возвращает сам код.

        Вызывается только root-установкой; код печатается в root-консоль и
        больше нигде не хранится в открытом виде.
        """
        code = generate_code()
        salt, digest = hash_code(code)
        now = time.time()
        with self._lock:
            self._conn.execute("DELETE FROM enrollment")
            self._conn.execute(
                "INSERT INTO enrollment (enrollment_id, salt, hash, created_at, expires_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (secrets.token_urlsafe(12), salt, digest, now, now + ttl_seconds),
            )
            self._enforce_modes()
        return code

    def consume_enrollment(self, code: str) -> bool:
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT enrollment_id, salt, hash, expires_at FROM enrollment"
                " WHERE used_at IS NULL"
            ).fetchone()
            if row is None or row["expires_at"] < now:
                return False
            if not verify_code(code, row["salt"], row["hash"]):
                return False
            self._conn.execute("UPDATE enrollment SET used_at = ? WHERE enrollment_id = ?",
                               (now, row["enrollment_id"]))
        return True

    def enrollment_open(self) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM enrollment WHERE used_at IS NULL AND expires_at > ?",
                (time.time(),),
            ).fetchone()
        return bool(row["n"])

    # --- сессии -----------------------------------------------------------
    def create_session(self, label: str = "") -> Session:
        from factory.secret_hub.panel import SESSION_TTL_SECONDS

        session = Session(secrets.token_urlsafe(32), secrets.token_urlsafe(32),
                          time.time() + SESSION_TTL_SECONDS, label)
        with self._lock:
            self._conn.execute(
                "INSERT INTO session (session_id, csrf, created_at, expires_at, label)"
                " VALUES (?, ?, ?, ?, ?)",
                (session.session_id, session.csrf, time.time(), session.expires_at, label),
            )
            self._conn.execute("DELETE FROM session WHERE expires_at < ?", (time.time(),))
        return session

    def session(self, session_id: str) -> Session | None:
        if not session_id:
            return None
        with self._lock:
            row = self._conn.execute("SELECT * FROM session WHERE session_id = ?",
                                     (session_id,)).fetchone()
        if row is None or row["expires_at"] < time.time():
            return None
        return Session(row["session_id"], row["csrf"], row["expires_at"], row["label"])

    def relabel_session(self, session_id: str, label: str) -> None:
        """Меняет роль сессии, не трогая её идентификатор и CSRF-токен.

        Пересоздание сессии посреди церемонии выдало бы новый CSRF-токен,
        которого у страницы нет: следующий же запрос той же церемонии
        отвергался бы как «форма устарела». Смена роли и смена идентификатора —
        разные вещи, и путать их не нужно.
        """
        with self._lock:
            self._conn.execute("UPDATE session SET label = ? WHERE session_id = ?",
                               (label, session_id))

    def drop_session(self, session_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM session WHERE session_id = ?", (session_id,))

    # --- rate limit -------------------------------------------------------
    def record_attempt(self, bucket: str) -> None:
        with self._lock:
            self._conn.execute("INSERT INTO attempt (bucket, at) VALUES (?, ?)",
                               (bucket, time.time()))

    def attempts_within(self, bucket: str, window_seconds: int) -> int:
        threshold = time.time() - window_seconds
        with self._lock:
            self._conn.execute("DELETE FROM attempt WHERE at < ?", (time.time() - 86400,))
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM attempt WHERE bucket = ? AND at >= ?",
                (bucket, threshold),
            ).fetchone()
        return int(row["n"])

    def clear_attempts(self, bucket: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM attempt WHERE bucket = ?", (bucket,))

    # --- идемпотентность --------------------------------------------------
    def remember_response(self, request_id: str, response: str) -> None:
        """Запоминает ответ на запрос с этим идентификатором.

        Нужно, чтобы повторная отправка формы (двойной клик, обновление
        страницы, повтор из-за разорванного соединения) не создавала вторую
        версию секрета и не перезапускала сайты ещё раз.
        """
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO applied_request (request_id, response, created_at)"
                " VALUES (?, ?, ?)", (request_id, response, time.time()))
            self._conn.execute("DELETE FROM applied_request WHERE created_at < ?",
                               (time.time() - 3600,))

    def recall_response(self, request_id: str) -> str | None:
        if not request_id:
            return None
        with self._lock:
            row = self._conn.execute(
                "SELECT response FROM applied_request WHERE request_id = ?",
                (request_id,)).fetchone()
        return row["response"] if row else None
