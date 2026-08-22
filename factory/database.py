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
import tempfile
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
#: Системная роль-владелец кластера; от неё выполняются привилегированные шаги.
CLUSTER_OWNER = "postgres"


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


SCOPE_RE = re.compile(r"^[a-z][a-z0-9_-]{1,62}$")


def credentials_path(scope: str) -> Path:
    if not SCOPE_RE.match(scope or ""):
        raise BlockedInput(
            f"Недопустимое имя набора учётных данных: {scope!r}.",
            field="database_ref",
            required_input="Строчные латинские буквы, цифры, дефис и подчёркивание",
            blocks_stage="VALIDATING")
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
    # Значения из файла попадают в команду, которую исполняет владелец кластера.
    # Проверка при создании базы этого не покрывает: файл мог быть подменён позже.
    for field, value in (("database", credentials.database), ("user", credentials.user)):
        if not IDENT_RE.match(value or ""):
            raise BlockedInput(
                f"В учётных данных «{scope}» недопустимое значение {field}: {value!r}.",
                field=f"var/db/{scope}.json:{field}",
                required_input="Идентификатор PostgreSQL из строчных букв, цифр и подчёркивания",
                blocks_stage="VALIDATING")
    reference = credentials.password_ref
    if not reference.startswith("file:"):
        raise BlockedInput(f"Неподдерживаемая ссылка на секрет: {reference!r}",
                           field=f"var/db/{scope}.json:password_ref", blocks_stage="VALIDATING")
    password_path = Path(reference.split(":", 1)[1])
    if password_path.parent.resolve() != (PATHS.var / "db").resolve():
        raise BlockedInput("Файл пароля обязан лежать в var/db/.",
                           field=f"var/db/{scope}.json:password_ref", blocks_stage="VALIDATING")
    return credentials, password_path.read_text(encoding="utf-8").strip()


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
    workdir = Path(tempfile.mkdtemp(prefix="factory-dump-"))
    os.chmod(workdir, 0o711)  # postgres должен войти в каталог, но не читать соседние
    staging = workdir / "dump.sql"
    # Каталог даёт только вход, без права создавать файлы. Поэтому цель дампа
    # создаётся заранее и передаётся владельцу кластера: писать он может ровно
    # в этот файл и никуда больше.
    staging.touch(mode=0o600)
    shutil.chown(staging, user=CLUSTER_OWNER)
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
    shutil.rmtree(workdir, ignore_errors=True)
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
    workdir = Path(tempfile.mkdtemp(prefix="factory-restore-"))
    os.chmod(workdir, 0o711)
    staging = workdir / "restore.sql"
    shutil.copyfile(source, staging)
    staging.chmod(0o644)
    result = _as_cluster_owner(f"{CLIENT} -v ON_ERROR_STOP=1 -d {credentials.database} -f {staging}",
                              timeout=600)
    staging.unlink(missing_ok=True)
    shutil.rmtree(workdir, ignore_errors=True)
    if result.returncode == 0:
        repair_ownership(scope)
    audit.record(job_id=f"db-restore-{scope}", site_id=scope, environment="staging",
                 action="database.restore", target=credentials.database,
                 exit_code=result.returncode, mutation=True, extra={"file": str(source)})
    return result.returncode == 0


def restore_probe(scope: str, archive: Path, *, probe_scope: str) -> bool:
    """Проверка восстановимости дампа в ОТДЕЛЬНОЙ базе.

    Рабочую базу трогать нельзя: проверка бэкапа не имеет права ронять
    работающие сайты. Пробная база пересоздаётся каждый раз и удаляется после
    проверки — она нужна только чтобы доказать, что дамп разворачивается.
    """
    if os.geteuid() != 0:
        raise BlockedAccess("Проверка бэкапа требует прав администратора.",
                            field="database.restore_probe", blocks_stage="STAGING_DEPLOY")
    if not archive.exists():
        raise BlockedInput(f"Дамп «{archive}» не найден.", field="database.restore_probe",
                           blocks_stage="STAGING_DEPLOY")
    probe = f"factory_{probe_scope}".replace("-", "_")
    if not IDENT_RE.match(probe):
        raise BlockedInput(f"Недопустимое имя пробной базы: {probe}",
                           field="database.restore_probe", blocks_stage="STAGING_DEPLOY")

    credentials, _ = load_credentials(scope)
    _sql_as_owner(f"DROP DATABASE IF EXISTS {probe} WITH (FORCE)")
    created = _sql_as_owner(f"CREATE DATABASE {probe} OWNER {credentials.user}")
    if created.returncode != 0:
        raise BlockedAccess(f"Пробная база не создана: {redact(created.stderr)[:300]}",
                            field="database.restore_probe", blocks_stage="STAGING_DEPLOY")

    workdir = Path(tempfile.mkdtemp(prefix="factory-probe-"))
    os.chmod(workdir, 0o711)
    staging = workdir / "probe.sql"
    shutil.copyfile(archive, staging)
    staging.chmod(0o644)
    # ON_ERROR_STOP не ставим: дамп с --clean начинается с DROP отсутствующих
    # объектов в пустой базе, и это не ошибка восстановления.
    result = _as_cluster_owner(f"{CLIENT} -d {probe} -f {staging}", timeout=900)
    staging.unlink(missing_ok=True)
    shutil.rmtree(workdir, ignore_errors=True)

    # SQL идёт через stdin: в аргументе кавычки пришлось бы экранировать дважды,
    # и это ровно то место, где ломается тихо.
    count_sql = ("select count(*) from information_schema.tables "
                 "where table_schema = 'public'")
    restored_tables = int((_sql_as_owner(count_sql, database=probe).stdout or "0").strip() or 0)
    live_tables = int((_sql_as_owner(count_sql, database=credentials.database).stdout or "0").strip() or 0)

    _sql_as_owner(f"DROP DATABASE IF EXISTS {probe} WITH (FORCE)")

    ok = result.returncode == 0 and restored_tables > 0 and restored_tables == live_tables
    audit.record(job_id=f"db-restore-probe-{scope}", site_id=scope, environment="staging",
                 action="database.restore_probe", target=credentials.database,
                 exit_code=0 if ok else 1, mutation=False,
                 extra={"archive": str(archive), "restored_tables": restored_tables,
                        "live_tables": live_tables})
    return ok


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
        # Типы — не декоративная мелочь: enum'ы Payload меняются при каждом
        # расширении статуса (ALTER TYPE ... ADD VALUE), и владелец кластера,
        # выполнявший restore, оставляет их за собой. Приложение после этого
        # поднимается, но падает на первой же миграции схемы.
        "FOR r IN SELECT t.typname FROM pg_type t "
        "JOIN pg_namespace n ON n.oid = t.typnamespace "
        "WHERE n.nspname = 'public' AND t.typtype IN ('e', 'd') LOOP "
        f"EXECUTE format('ALTER TYPE public.%I OWNER TO {credentials.user}', r.typname); "
        "END LOOP; "
        "END $$;"
    )
    result = _sql_as_owner(sql, database=credentials.database)
    return result.returncode == 0


def misowned_objects(scope: str) -> list[str]:
    """Объекты схемы public, которые принадлежат не роли приложения.

    Данные могут восстановиться до последней записи и всё равно оставить базу
    нерабочей: приложению нужно не только читать таблицы, но и менять типы при
    миграции схемы. Поэтому владение проверяется отдельно от содержимого.
    """
    credentials, _ = load_credentials(scope)
    sql = (
        "SELECT 'table ' || tablename FROM pg_tables "
        f"WHERE schemaname = 'public' AND tableowner <> '{credentials.user}' "
        "UNION ALL SELECT 'sequence ' || sequencename FROM pg_sequences "
        f"WHERE schemaname = 'public' AND sequenceowner <> '{credentials.user}' "
        "UNION ALL SELECT 'type ' || t.typname FROM pg_type t "
        "JOIN pg_namespace n ON n.oid = t.typnamespace "
        "JOIN pg_roles r ON r.oid = t.typowner "
        "WHERE n.nspname = 'public' AND t.typtype IN ('e', 'd') "
        f"AND r.rolname <> '{credentials.user}' "
        "UNION ALL SELECT 'schema public' FROM pg_namespace n "
        "JOIN pg_roles r ON r.oid = n.nspowner "
        f"WHERE n.nspname = 'public' AND r.rolname <> '{credentials.user}'"
    )
    result = _sql_as_owner(sql, database=credentials.database)
    if result.returncode != 0:
        raise BlockedAccess(f"Проверка владения не выполнена: {redact(result.stderr)[:300]}",
                            field="database.misowned_objects", blocks_stage="STAGING_DEPLOY")
    return [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]


def drop(scope: str) -> bool:
    database = f"factory_{scope}".replace("-", "_")
    if not IDENT_RE.match(database):
        return False
    result = _sql_as_owner(f"DROP DATABASE IF EXISTS {database} WITH (FORCE)")
    credentials_path(scope).unlink(missing_ok=True)
    credentials_path(scope).with_suffix(".password").unlink(missing_ok=True)
    return result.returncode == 0
