"""Провизия локальной базы для blueprint payload-next-multisite.

Прямой доступ к СУБД из агента запрещён hook'ом — и правильно. Привилегированный
шаг выполняет проверенный wrapper: фиксированный набор операций, отказ работать с
production, локально сгенерированный пароль в файле с правами 0600 и журнал с редакцией.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
from dataclasses import dataclass
from pathlib import Path

from factory import audit
from factory.errors import BlockedAccess, BlockedInput
from factory.paths import PATHS
from factory.redaction import redact

#: Идентификаторы попадают в SQL, поэтому допускается только строгая форма.
IDENT_RE = re.compile(r"^[a-z][a-z0-9_]{2,62}$")
CLUSTER_VERSION = "16"
CLUSTER_NAME = "main"
CLIENT = "/usr/lib/postgresql/16/bin/psql"


@dataclass
class DatabaseCredentials:
    host: str
    port: int
    database: str
    user: str
    password_ref: str          # ссылка на секрет, не значение

    def dsn(self, password: str) -> str:
        return f"postgresql://{self.user}:{password}@{self.host}:{self.port}/{self.database}"

    def as_dict(self) -> dict:
        return {"host": self.host, "port": self.port, "database": self.database,
                "user": self.user, "password_ref": self.password_ref}


def credentials_path(scope: str) -> Path:
    directory = PATHS.var / "db"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{scope}.json"


def _sql_as_owner(sql: str, *, database: str = "postgres") -> subprocess.CompletedProcess:
    """Единственная привилегированная операция wrapper'а — SQL от владельца кластера.

    argv фиксирован: агент не может подставить произвольную команду.
    """
    if os.geteuid() != 0:
        raise BlockedAccess(
            "Провизия БД требует прав администратора на управляющем хосте.",
            field="database.provision",
            required_input="Запуск от пользователя, которому разрешено управлять кластером PostgreSQL",
            blocks_stage="STAGING_DEPLOY")
    # SQL передаётся через stdin, а не аргументом: иначе shell раскрывает `$$`
    # долларовых кавычек PL/pgSQL в PID процесса и запрос ломается.
    inner = f"{CLIENT} -v ON_ERROR_STOP=1 -d {database} -tA"
    return subprocess.run(["su", "-s", "/bin/sh", "postgres", "-c", inner],
                          input=sql, capture_output=True, text=True, timeout=120, check=False)


def cluster_running() -> bool:
    return subprocess.run(["pg_isready", "-q"], capture_output=True, check=False, timeout=30).returncode == 0


def start_cluster() -> bool:
    if cluster_running():
        return True
    subprocess.run(["pg_ctlcluster", CLUSTER_VERSION, CLUSTER_NAME, "start"],
                   capture_output=True, text=True, timeout=120, check=False)
    return cluster_running()


def provision(scope: str, *, environment: str = "staging", rotate: bool = False) -> DatabaseCredentials:
    """Идемпотентно создаёт роль и базу локального стенда."""
    if environment == "production":
        raise BlockedAccess(
            "Провизия production-БД локальным wrapper'ом запрещена: это делает deployment-слой на целевом хосте.",
            field="database.provision", required_input="Playbook automation/ansible и подтверждённый target",
            blocks_stage="PRODUCTION_DEPLOY")
    database = f"factory_{scope}".replace("-", "_")
    user = f"{database}_app"
    for ident in (database, user):
        if not IDENT_RE.match(ident):
            raise BlockedInput(f"Недопустимый идентификатор БД: {ident}", field="scope",
                               required_input="Строчные латинские буквы, цифры и подчёркивания")
    if not start_cluster():
        raise BlockedAccess("Кластер PostgreSQL не запускается.", field="database.cluster",
                            required_input="Работающий кластер PostgreSQL 16", blocks_stage="STAGING_DEPLOY")

    path = credentials_path(scope)
    password_file = path.with_suffix(".password")
    if password_file.exists() and not rotate:
        password = password_file.read_text(encoding="utf-8").strip()
    else:
        password = secrets.token_urlsafe(24)
        password_file.write_text(password, encoding="utf-8")
        password_file.chmod(0o600)

    escaped = password.replace("'", "''")
    role_sql = (f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{user}') "
                f"THEN CREATE ROLE {user} LOGIN PASSWORD '{escaped}'; "
                f"ELSE ALTER ROLE {user} WITH LOGIN PASSWORD '{escaped}'; END IF; END $$;")
    exists_sql = f"SELECT 1 FROM pg_database WHERE datname = '{database}'"
    create_sql = f"CREATE DATABASE {database} OWNER {user}"

    for sql in (role_sql,):
        result = _sql_as_owner(sql)
        if result.returncode != 0:
            raise BlockedAccess(f"Создание роли не выполнено: {redact(result.stderr)[:300]}",
                                field="database.provision", required_input="Доступ к кластеру PostgreSQL",
                                blocks_stage="STAGING_DEPLOY")
    probe = _sql_as_owner(exists_sql)
    if probe.stdout.strip() != "1":
        result = _sql_as_owner(create_sql)
        if result.returncode != 0:
            raise BlockedAccess(f"Создание базы не выполнено: {redact(result.stderr)[:300]}",
                                field="database.provision", required_input="Доступ к кластеру PostgreSQL",
                                blocks_stage="STAGING_DEPLOY")

    credentials = DatabaseCredentials("127.0.0.1", 5432, database, user, f"file:{password_file}")
    path.write_text(json.dumps(credentials.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    path.chmod(0o600)
    audit.record(job_id=f"db-provision-{scope}", site_id=scope, environment=environment,
                 action="db_provision", target=f"postgresql://127.0.0.1:5432/{database}",
                 exit_code=0, output=f"database={database} user={user}", mutation=True)
    return credentials


def load_credentials(scope: str) -> tuple[DatabaseCredentials, str]:
    path = credentials_path(scope)
    if not path.exists():
        raise BlockedInput(f"База для «{scope}» не провизионирована.", field="database",
                           required_input=f"python3 -m factory db provision --scope {scope}",
                           blocks_stage="BUILDING")
    credentials = DatabaseCredentials(**json.loads(path.read_text(encoding="utf-8")))
    return credentials, Path(credentials.password_ref.split(":", 1)[1]).read_text(encoding="utf-8").strip()


def drop(scope: str) -> bool:
    database = f"factory_{scope}".replace("-", "_")
    if not IDENT_RE.match(database):
        return False
    result = _sql_as_owner(f"DROP DATABASE IF EXISTS {database} WITH (FORCE)")
    credentials_path(scope).unlink(missing_ok=True)
    credentials_path(scope).with_suffix(".password").unlink(missing_ok=True)
    return result.returncode == 0
