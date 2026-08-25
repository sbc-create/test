"""Зашифрованное хранилище направлений.

Метаданные лежат в SQLite, значения — в том же файле, но только шифртекстом.
Мастер-ключа в базе нет: он приходит процессу отдельно (``crypto.load_master_key``),
поэтому украденный файл базы без ключа не является утечкой секрета.

Три свойства, ради которых модуль написан именно так:

* **версии.** Запись значения не перетирает предыдущее: создаётся новая версия,
  прежняя остаётся `superseded`. Откат — это переключение указателя, а не
  восстановление из бэкапа, и последняя рабочая версия не удаляется никогда.
* **атомарность.** Файл базы создаётся с правами 0600 до первой записи; сама
  запись идёт одной транзакцией, а выгрузка бэкапа — через временный файл в том
  же каталоге и ``os.replace``. Прерванная запись оставляет предыдущее
  состояние целым, а не половину нового.
* **никакого чтения наружу.** У модуля есть ``reveal_for_apply``, и это
  единственная функция, возвращающая значение. Она вызывается только внутри
  root-процесса сервиса; ни одна операция API её не проксирует.
"""
from __future__ import annotations

import os
import sqlite3
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from factory.errors import BlockedInput, BlockedSecret
from factory.secret_hub import SECRET_FIELDS
from factory.secret_hub.crypto import Envelope, MasterKey, Secret, decrypt, encrypt

#: Права каталога и файла хранилища. Проверяются при каждом открытии.
DIR_MODE = 0o700
FILE_MODE = 0o600

STATUS_ACTIVE = "active"
STATUS_SUPERSEDED = "superseded"
STATUS_REVOKED = "revoked"

SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolio (
    portfolio     TEXT PRIMARY KEY,
    provider      TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    verified_at   TEXT,
    status        TEXT NOT NULL,
    active_version INTEGER
);

CREATE TABLE IF NOT EXISTS secret_version (
    portfolio     TEXT NOT NULL,
    version       INTEGER NOT NULL,
    created_at    TEXT NOT NULL,
    verified_at   TEXT,
    status        TEXT NOT NULL,
    fingerprint   TEXT NOT NULL,
    key_id        TEXT NOT NULL,
    scheme        TEXT NOT NULL,
    PRIMARY KEY (portfolio, version),
    FOREIGN KEY (portfolio) REFERENCES portfolio(portfolio) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS secret_value (
    portfolio     TEXT NOT NULL,
    version       INTEGER NOT NULL,
    field         TEXT NOT NULL,
    salt          BLOB NOT NULL,
    nonce         BLOB NOT NULL,
    ciphertext    BLOB NOT NULL,
    fingerprint   TEXT NOT NULL,
    PRIMARY KEY (portfolio, version, field),
    FOREIGN KEY (portfolio, version)
        REFERENCES secret_version(portfolio, version) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS deployment (
    portfolio     TEXT NOT NULL,
    consumer      TEXT NOT NULL,
    version       INTEGER,
    applied_at    TEXT,
    status        TEXT NOT NULL,
    detail        TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (portfolio, consumer)
);
"""


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class VersionRow:
    portfolio: str
    version: int
    created_at: str
    verified_at: str | None
    status: str
    fingerprint: str
    key_id: str

    def as_dict(self) -> dict:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "verified_at": self.verified_at,
            "status": self.status,
            "fingerprint": self.fingerprint,
            "key_id": self.key_id,
        }


@dataclass(frozen=True)
class DeploymentRow:
    portfolio: str
    consumer: str
    version: int | None
    applied_at: str | None
    status: str
    detail: str

    def as_dict(self) -> dict:
        return {
            "consumer": self.consumer,
            "version": self.version,
            "applied_at": self.applied_at,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class PortfolioState:
    """Публичное состояние направления. Значений здесь нет по построению."""

    portfolio: str
    provider: str
    configured: bool
    created_at: str | None
    updated_at: str | None
    verified_at: str | None
    status: str
    active_version: int | None
    fingerprint: str | None
    versions: tuple[VersionRow, ...]
    deployments: tuple[DeploymentRow, ...]

    @property
    def verified(self) -> bool:
        return bool(self.verified_at)

    def as_dict(self) -> dict:
        return {
            "portfolio": self.portfolio,
            "provider": self.provider,
            "configured": self.configured,
            "verified": self.verified,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "verified_at": self.verified_at,
            "status": self.status,
            "version": self.active_version,
            "fingerprint": self.fingerprint,
            "versions": [v.as_dict() for v in self.versions],
            "deployments": [d.as_dict() for d in self.deployments],
        }


def _aad(portfolio: str, field: str, version: int) -> bytes:
    """Связывает шифртекст с его местом. См. ``crypto.encrypt``."""
    return f"secret-hub/v1|{portfolio}|{field}|{version}".encode()


class Store:
    """Хранилище. Открывается только процессом, у которого есть мастер-ключ."""

    def __init__(self, db_path: Path, master: MasterKey, *, enforce_permissions: bool = True) -> None:
        self.db_path = db_path
        self.master = master
        self._enforce = enforce_permissions
        self._prepare_paths()
        self._conn = sqlite3.connect(str(db_path), isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.executescript(SCHEMA)
        self._enforce_file_mode()

    # --- права и создание ------------------------------------------------
    def _prepare_paths(self) -> None:
        directory = self.db_path.parent
        directory.mkdir(parents=True, exist_ok=True, mode=DIR_MODE)
        if self._enforce:
            # mkdir применяет umask, поэтому права выставляются явно: каталог,
            # созданный при umask 022, оказался бы 0755.
            os.chmod(directory, DIR_MODE)
        if not self.db_path.exists():
            # Файл создаётся заранее и сразу с 0600. Если отдать создание
            # sqlite3, между созданием и chmod существует окно, в котором база
            # читается миром.
            fd = os.open(self.db_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, FILE_MODE)
            os.close(fd)

    def _enforce_file_mode(self) -> None:
        if not self._enforce:
            return
        for path in (self.db_path, self.db_path.with_name(self.db_path.name + "-wal"),
                     self.db_path.with_name(self.db_path.name + "-shm")):
            if path.exists():
                os.chmod(path, FILE_MODE)

    def check_permissions(self) -> list[str]:
        """Проблемы прав. Пустой список — права такие, как заявлено."""
        problems: list[str] = []
        directory = self.db_path.parent
        try:
            dir_mode = stat.S_IMODE(directory.stat().st_mode)
            if dir_mode & 0o077:
                problems.append(f"каталог {directory} доступен группе или миру ({dir_mode:04o})")
        except OSError as exc:
            problems.append(f"каталог {directory} не проверен ({exc.__class__.__name__})")
        for path in (self.db_path,
                     self.db_path.with_name(self.db_path.name + "-wal"),
                     self.db_path.with_name(self.db_path.name + "-shm")):
            if not path.exists():
                continue
            mode = stat.S_IMODE(path.stat().st_mode)
            if mode & 0o077:
                problems.append(f"файл {path} доступен группе или миру ({mode:04o})")
        return problems

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @contextmanager
    def _transaction(self):
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        else:
            self._conn.execute("COMMIT")
            self._enforce_file_mode()

    # --- запись ----------------------------------------------------------
    def put(self, portfolio: str, values: dict[str, Secret], *, provider: str,
            verified_at: str | None) -> int:
        """Новая версия секрета направления. Предыдущая остаётся `superseded`.

        ``verified_at`` заполняется только после успешной живой проверки:
        непроверенное значение записывается лишь тем путём, который явно
        разрешил это сделать, и в статусе это видно.
        """
        missing = [f for f in SECRET_FIELDS if f not in values]
        if missing:
            raise BlockedInput(
                f"Не переданы поля секрета: {', '.join(missing)}.",
                field="secret",
                required_input=", ".join(SECRET_FIELDS),
                blocks_stage="VALIDATING",
            )
        for name, secret in values.items():
            if not secret.reveal().strip():
                raise BlockedInput(
                    f"Поле «{name}» пустое. Пустое поле — не разрешение работать без значения.",
                    field=name,
                    required_input=f"Непустое значение {name}",
                    blocks_stage="VALIDATING",
                )

        now = _now()
        with self._transaction():
            row = self._conn.execute(
                "SELECT created_at FROM portfolio WHERE portfolio = ?", (portfolio,)
            ).fetchone()
            created_at = row["created_at"] if row else now
            version = self._next_version(portfolio)

            # Родительская строка идёт первой: `secret_version` ссылается на
            # `portfolio` внешним ключом, и обратный порядок падает на
            # IntegrityError ещё до того, как что-либо будет зашифровано.
            self._conn.execute(
                "INSERT INTO portfolio (portfolio, provider, created_at, updated_at, verified_at,"
                " status, active_version) VALUES (?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(portfolio) DO UPDATE SET provider = excluded.provider,"
                " updated_at = excluded.updated_at, verified_at = excluded.verified_at,"
                " status = excluded.status, active_version = excluded.active_version",
                (portfolio, provider, created_at, now, verified_at, STATUS_ACTIVE, version),
            )
            self._conn.execute(
                "UPDATE secret_version SET status = ? WHERE portfolio = ? AND status = ?",
                (STATUS_SUPERSEDED, portfolio, STATUS_ACTIVE),
            )
            combined = _combined_fingerprint(values)
            self._conn.execute(
                "INSERT INTO secret_version (portfolio, version, created_at, verified_at, status,"
                " fingerprint, key_id, scheme) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (portfolio, version, now, verified_at, STATUS_ACTIVE, combined,
                 self.master.key_id(), _scheme()),
            )
            for name in SECRET_FIELDS:
                material = values[name]
                envelope = encrypt(self.master, material, aad=_aad(portfolio, name, version))
                self._conn.execute(
                    "INSERT INTO secret_value (portfolio, version, field, salt, nonce, ciphertext,"
                    " fingerprint) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (portfolio, version, name, envelope.salt, envelope.nonce,
                     envelope.ciphertext, material.fingerprint()),
                )
        return version

    def mark_verified(self, portfolio: str, version: int, *, when: str | None = None) -> None:
        stamp = when or _now()
        with self._transaction():
            self._conn.execute(
                "UPDATE secret_version SET verified_at = ? WHERE portfolio = ? AND version = ?",
                (stamp, portfolio, version),
            )
            self._conn.execute(
                "UPDATE portfolio SET verified_at = ?, updated_at = ? WHERE portfolio = ?",
                (stamp, stamp, portfolio),
            )

    def revoke(self, portfolio: str) -> int:
        """Отзывает активную версию, не удаляя её.

        Значение остаётся в базе намеренно: «не удалять последнюю рабочую версию
        секрета» — требование задания, и отзыв не должен делать откат
        невозможным. Отозванная версия перестаёт применяться, но существует.
        """
        state = self.state(portfolio)
        if not state.configured or state.active_version is None:
            raise BlockedInput(
                f"Направление «{portfolio}» не настроено: отзывать нечего.",
                field=portfolio,
                required_input="Настроенное направление",
                blocks_stage="VALIDATING",
            )
        version = state.active_version
        now = _now()
        with self._transaction():
            self._conn.execute(
                "UPDATE secret_version SET status = ? WHERE portfolio = ? AND version = ?",
                (STATUS_REVOKED, portfolio, version),
            )
            self._conn.execute(
                "UPDATE portfolio SET status = ?, updated_at = ?, verified_at = NULL,"
                " active_version = NULL WHERE portfolio = ?",
                (STATUS_REVOKED, now, portfolio),
            )
        return version

    def rollback(self, portfolio: str) -> int:
        """Возвращает предыдущую версию как активную.

        Ищется старшая версия, которая не является текущей активной и не
        отозвана. Если такой нет — отказ, а не «откатились в никуда».
        """
        rows = self._versions(portfolio)
        active = self.state(portfolio).active_version
        candidates = [r for r in rows if r.version != active and r.status != STATUS_REVOKED]
        if not candidates:
            raise BlockedInput(
                f"У направления «{portfolio}» нет предыдущей версии для отката.",
                field=portfolio,
                required_input="Как минимум две версии секрета",
                blocks_stage="VALIDATING",
            )
        target = max(candidates, key=lambda r: r.version)
        now = _now()
        with self._transaction():
            self._conn.execute(
                "UPDATE secret_version SET status = ? WHERE portfolio = ? AND status = ?",
                (STATUS_SUPERSEDED, portfolio, STATUS_ACTIVE),
            )
            self._conn.execute(
                "UPDATE secret_version SET status = ? WHERE portfolio = ? AND version = ?",
                (STATUS_ACTIVE, portfolio, target.version),
            )
            self._conn.execute(
                "UPDATE portfolio SET active_version = ?, status = ?, updated_at = ?,"
                " verified_at = ? WHERE portfolio = ?",
                (target.version, STATUS_ACTIVE, now, target.verified_at, portfolio),
            )
        return target.version

    def record_deployment(self, portfolio: str, consumer: str, *, version: int | None,
                          status: str, detail: str = "") -> None:
        with self._transaction():
            self._conn.execute(
                "INSERT INTO deployment (portfolio, consumer, version, applied_at, status, detail)"
                " VALUES (?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(portfolio, consumer) DO UPDATE SET version = excluded.version,"
                " applied_at = excluded.applied_at, status = excluded.status,"
                " detail = excluded.detail",
                (portfolio, consumer, version, _now() if status == "applied" else None,
                 status, detail),
            )

    # --- чтение ----------------------------------------------------------
    def state(self, portfolio: str) -> PortfolioState:
        row = self._conn.execute(
            "SELECT * FROM portfolio WHERE portfolio = ?", (portfolio,)
        ).fetchone()
        versions = self._versions(portfolio)
        deployments = self._deployments(portfolio)
        if row is None:
            return PortfolioState(portfolio, "", False, None, None, None, "not_configured",
                                  None, None, versions, deployments)
        active = row["active_version"]
        fingerprint = next((v.fingerprint for v in versions if v.version == active), None)
        return PortfolioState(
            portfolio=portfolio,
            provider=row["provider"],
            configured=active is not None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            verified_at=row["verified_at"],
            status=row["status"],
            active_version=active,
            fingerprint=fingerprint,
            versions=versions,
            deployments=deployments,
        )

    def _versions(self, portfolio: str) -> tuple[VersionRow, ...]:
        rows = self._conn.execute(
            "SELECT * FROM secret_version WHERE portfolio = ? ORDER BY version", (portfolio,)
        ).fetchall()
        return tuple(
            VersionRow(portfolio, r["version"], r["created_at"], r["verified_at"], r["status"],
                       r["fingerprint"], r["key_id"])
            for r in rows
        )

    def _deployments(self, portfolio: str) -> tuple[DeploymentRow, ...]:
        rows = self._conn.execute(
            "SELECT * FROM deployment WHERE portfolio = ? ORDER BY consumer", (portfolio,)
        ).fetchall()
        return tuple(
            DeploymentRow(portfolio, r["consumer"], r["version"], r["applied_at"], r["status"],
                          r["detail"])
            for r in rows
        )

    def _next_version(self, portfolio: str) -> int:
        row = self._conn.execute(
            "SELECT MAX(version) AS m FROM secret_version WHERE portfolio = ?", (portfolio,)
        ).fetchone()
        return int(row["m"] or 0) + 1

    def reveal_for_apply(self, portfolio: str, version: int | None = None) -> dict[str, Secret]:
        """Единственное место, возвращающее значения.

        Вызывается только внутри root-процесса — сервисом при применении и
        проверкой перед записью. Ни один обработчик запроса её результат наружу
        не отдаёт: ответы собираются из :class:`PortfolioState`, где значений
        нет по построению.
        """
        state = self.state(portfolio)
        target = version if version is not None else state.active_version
        if target is None:
            raise BlockedSecret(
                f"Направление «{portfolio}» не настроено: значения нет.",
                field=portfolio,
                required_input="Ввод credentials через одноразовую форму или root-импорт",
                blocks_stage="VALIDATING",
            )
        rows = self._conn.execute(
            "SELECT field, salt, nonce, ciphertext FROM secret_value"
            " WHERE portfolio = ? AND version = ?",
            (portfolio, target),
        ).fetchall()
        if len(rows) != len(SECRET_FIELDS):
            raise BlockedSecret(
                f"Версия {target} направления «{portfolio}» неполна: "
                f"{len(rows)} из {len(SECRET_FIELDS)} полей.",
                field=portfolio,
                required_input="Целая версия секрета",
                blocks_stage="VALIDATING",
            )
        version_row = self._conn.execute(
            "SELECT scheme, key_id FROM secret_version WHERE portfolio = ? AND version = ?",
            (portfolio, target),
        ).fetchone()
        out: dict[str, Secret] = {}
        for row in rows:
            envelope = Envelope(version_row["scheme"], row["salt"], row["nonce"],
                                row["ciphertext"], version_row["key_id"])
            out[row["field"]] = decrypt(self.master, envelope,
                                        aad=_aad(portfolio, row["field"], target),
                                        label=f"{portfolio}/{row['field']}")
        return out

    # --- бэкап -----------------------------------------------------------
    def backup(self, directory: Path, *, tag: str) -> Path:
        """Копия зашифрованного хранилища перед изменением.

        Копируется через ``sqlite3.backup``, а не ``cp``: файл в WAL-режиме
        может не содержать последних транзакций, и «бэкап» оказался бы старее
        того, что откатывают. Права выставляются до наполнения файла.
        """
        directory.mkdir(parents=True, exist_ok=True, mode=DIR_MODE)
        if self._enforce:
            os.chmod(directory, DIR_MODE)
        stamp = _now().replace(":", "").replace("-", "")
        target = directory / f"store-{stamp}-{tag}.sqlite3"
        tmp = directory / f".{target.name}.tmp"
        if tmp.exists():
            tmp.unlink()
        fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, FILE_MODE)
        os.close(fd)
        destination = sqlite3.connect(str(tmp))
        try:
            self._conn.backup(destination)
        finally:
            destination.close()
        os.replace(tmp, target)
        if self._enforce:
            os.chmod(target, FILE_MODE)
        return target

    def restore(self, backup_path: Path) -> None:
        """Возвращает хранилище к состоянию бэкапа.

        Применяется, когда откат версии невозможен — например, повреждена сама
        база. Текущий файл заменяется целиком через временную копию.
        """
        if not backup_path.exists():
            raise BlockedInput(
                f"Бэкап {backup_path} не найден.",
                field=str(backup_path),
                required_input="Существующий файл бэкапа",
                blocks_stage="VALIDATING",
            )
        source = sqlite3.connect(str(backup_path))
        try:
            with self._transaction():
                pass  # проверка, что база не занята другой транзакцией
            source.backup(self._conn)
        finally:
            source.close()
        self._enforce_file_mode()


def _scheme() -> str:
    from factory.secret_hub.crypto import SCHEME

    return SCHEME


def _combined_fingerprint(values: dict[str, Secret]) -> str:
    """Отпечаток набора: меняется, если изменилось хотя бы одно поле.

    Считается из отпечатков полей, а не из значений: собирать значения в одну
    строку ради хеша значило бы создать ещё одну копию секрета в памяти.
    """
    import hashlib

    digest = hashlib.sha256(b"secret-hub/combined")
    for name in SECRET_FIELDS:
        digest.update(b"\x00" + name.encode("utf-8") + b"=" + values[name].fingerprint().encode())
    return "sha256:" + digest.hexdigest()[:16]
