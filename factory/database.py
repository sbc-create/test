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
import shutil
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
DUMP_CLIENT = "/usr/lib/postgresql/16/bin/pg_dump"


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


def _as_cluster_owner(inner: str, *, timeout: int = 120, stdin: str | None = None):
    """Запуск фиксированной команды кластера от его владельца.

    argv не собирается из пользовательского ввода: подставляется только заранее
    известный клиент и имя базы, прошедшее проверку IDENT_RE.
    """
    return subprocess.run(["su", "-s", "/bin/sh", "postgres", "-c", inner],
                          input=stdin, capture_output=True, text=True, timeout=timeout, check=False)


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
    return _as_cluster_owner(inner, stdin=sql)


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


def dump(scope: str, destination: Path) -> Path:
    """Логический дамп базы сайта перед мутацией.

    Дамп создаётся владельцем кластера во временном каталоге и затем переносится
    в var/: пароль приложения при этом не участвует и в командную строку не попадает.
    """
    credentials, _ = load_credentials(scope)
    if os.geteuid() != 0:
        raise BlockedAccess(
            "Бэкап базы требует прав администратора на управляющем хосте.",
            field="database.dump",
            required_input="Запуск от пользователя, которому разрешено управлять кластером PostgreSQL",
            blocks_stage="STAGING_DEPLOY")

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path("/tmp") / f"factory-dump-{credentials.database}.sql"
    # --clean --if-exists: дамп обязан восстанавливаться в НЕПУСТУЮ базу.
    # Без этого восстановление падает на уже существующих объектах, и
    # «бэкап есть» перестаёт означать «восстановление проверено».
    # --clean --if-exists: дамп обязан восстанавливаться в НЕПУСТУЮ базу, иначе
    # «бэкап есть» не означает «восстановление проверено».
    # Владелец и права СОХРАНЯЮТСЯ: база принадлежит роли приложения, и дамп без
    # владельца восстанавливается объектами postgres — приложение теряет доступ.
    inner = f"{DUMP_CLIENT} --clean --if-exists -d {credentials.database} -f {staging}"
    result = _as_cluster_owner(inner, timeout=600)
    if result.returncode != 0:
        raise BlockedAccess(f"pg_dump завершился с кодом {result.returncode}: {result.stderr.strip()[:300]}",
                            field="database.dump", blocks_stage="STAGING_DEPLOY")
    shutil.move(str(staging), str(destination))
    destination.chmod(0o600)
    audit.record(job_id=f"db-dump-{scope}", site_id=scope, environment="staging",
                 action="database.dump", target=credentials.database, exit_code=0, mutation=False,
                 extra={"file": str(destination), "bytes": destination.stat().st_size})
    return destination


def restore(scope: str, source: Path) -> bool:
    """Восстановление базы из дампа. Используется проверкой отката, а не «на всякий случай»."""
    credentials, _ = load_credentials(scope)
    if os.geteuid() != 0:
        raise BlockedAccess("Восстановление базы требует прав администратора.",
                            field="database.restore", blocks_stage="ROLLED_BACK")
    if not source.exists():
        raise BlockedInput(f"Дамп «{source}» не найден.", field="database.restore",
                           blocks_stage="ROLLED_BACK")
    staging = Path("/tmp") / f"factory-restore-{credentials.database}.sql"
    shutil.copyfile(source, staging)
    staging.chmod(0o644)
    result = _as_cluster_owner(f"{CLIENT} -v ON_ERROR_STOP=1 -d {credentials.database} -f {staging}",
                              timeout=600)
    staging.unlink(missing_ok=True)
    if result.returncode == 0:
        repair_ownership(scope)
    audit.record(job_id=f"db-restore-{scope}", site_id=scope, environment="staging",
                 action="database.restore", target=credentials.database,
                 exit_code=result.returncode, mutation=True, extra={"file": str(source)})
    return result.returncode == 0


def repair_ownership(scope: str) -> bool:
    """Возвращает владение схемой роли приложения.

    После восстановления объекты могут принадлежать владельцу кластера: он и
    выполнял restore. Приложение при этом теряет доступ, и «восстановление
    прошло» оказывается неправдой на первом же запросе. Поэтому владение
    восстанавливается явным шагом, а не предположением.
    """
    credentials, _ = load_credentials(scope)
    sql = (
        "DO $$ DECLARE r record; BEGIN "
        f"EXECUTE 'ALTER SCHEMA public OWNER TO {credentials.user}'; "
        "FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP "
        f"EXECUTE format('ALTER TABLE public.%I OWNER TO {credentials.user}', r.tablename); "
        "END LOOP; "
        "FOR r IN SELECT sequencename FROM pg_sequences WHERE schemaname = 'public' LOOP "
        f"EXECUTE format('ALTER SEQUENCE public.%I OWNER TO {credentials.user}', r.sequencename); "
        "END LOOP; "
        "FOR r IN SELECT table_name FROM information_schema.views WHERE table_schema = 'public' LOOP "
        f"EXECUTE format('ALTER VIEW public.%I OWNER TO {credentials.user}', r.table_name); "
        "END LOOP; "
        "END $$;"
    )
    result = _sql_as_owner(sql, database=credentials.database)
    return result.returncode == 0


def drop(scope: str) -> bool:
    database = f"factory_{scope}".replace("-", "_")
    if not IDENT_RE.match(database):
        return False
    result = _sql_as_owner(f"DROP DATABASE IF EXISTS {database} WITH (FORCE)")
    credentials_path(scope).unlink(missing_ok=True)
    credentials_path(scope).with_suffix(".password").unlink(missing_ok=True)
    return result.returncode == 0
