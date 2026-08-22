"""Цель развёртывания для blueprint payload-next-multisite.

Особенность blueprint: одно приложение обслуживает три сайта, и всё, что их
различает, лежит в общей базе, а не в каталоге релиза. Отсюда следуют границы,
которые здесь соблюдаются явно, а не подразумеваются:

* Каталог релиза общий для сайтов цели, поэтому состояние хранится по сайтам, а
  доступ к цели сериализуется отдельной блокировкой: лок задания берётся по
  `site+environment` и от гонки между сайтами не защищает.
* Схема базы НЕ синхронизируется при старте процесса. Это отдельный шаг выката,
  выполняемый после бэкапа: иначе кандидат менял бы схему под работающим
  релизом, а откат возвращал бы старую схему и удалял колонки новой.
* Cutover — это переключение процесса на новом порту; симлинк `current` хранит
  указатель на текущий релиз для отката и prune. Стабильной точки входа
  (reverse proxy) у локального стенда нет, и заявлять её нельзя.
* Мутации базы (конфигурация тенанта) выполняются после бэкапа, и при их отказе
  база восстанавливается из этого бэкапа, а задание не ретраится.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from factory import audit, database
from factory.errors import BlockedAccess, DeployFailed, FactoryError
from factory.locks import site_lock
from factory.paths import PATHS
from factory.targets.base import DeployPlan, DeployResult, now

APP = PATHS.root / "blueprints" / "payload-next-multisite" / "app"
RELEASES = APP / ".releases"
LAUNCHER = PATHS.root / "tests" / "tools" / "with_app_env.py"
#: Отдельная база для проверки восстановимости дампа. Живую базу стенда трогать
#: нельзя: проверка бэкапа не должна ронять три работающих сайта.
PROBE_SUFFIX = "_restoreprobe"


class RestoreFailed(FactoryError):
    """Восстановление из бэкапа не выполнено. Ретраить нечего — нужен человек."""

    status = "QUARANTINED"


class PayloadMultisiteTarget:
    """Локальный стенд: сборка Next, миграция схемы, конфигурация тенанта, cutover."""

    adapter = "payload_multisite"

    def __init__(self, conf: dict, package: dict) -> None:
        self.conf = conf
        self.package = package
        self.ref = conf.get("ref", "payload-local")
        self.site_id = package["site_id"]
        self.environment = package["environment"]
        self.domain = package["domain"]
        self.database_scope = package.get("database_ref") or "anime"
        self.root = PATHS.root / conf.get("root", "var/targets/payload-local")
        self.bind_host = conf.get("bind_host", "127.0.0.1")
        self.port_range = tuple(conf.get("port_range", [8110, 8129]))
        if self.environment == "production":
            raise BlockedAccess(
                "Цель payload-local не пригодна для production.",
                field="inventory/targets.yaml",
                required_input="Цель с production_capable: true и подтверждённым доменом",
                blocks_stage="PRODUCTION_DEPLOY")

    # --------------------------------------------------------------- состояние
    @property
    def _state_path(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root / "state.json"

    def _state(self) -> dict:
        path = self.root / "state.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            data.setdefault("sites", {})
            return data
        return {"sites": {}}

    def _write_state(self, state: dict) -> None:
        """Атомарная запись: обычный write_text рвёт состояние при падении между сайтами."""
        path = self._state_path
        temporary = path.with_suffix(".json.new")
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    def _save_process(self, **kwargs) -> dict:
        state = self._state()
        state.update(kwargs)
        self._write_state(state)
        return state

    def _site_state(self, site_id: str | None = None) -> dict:
        return self._state()["sites"].get(site_id or self.site_id, {})

    def _save_site(self, **kwargs) -> dict:
        state = self._state()
        site = state["sites"].setdefault(self.site_id, {})
        site.update(kwargs)
        self._write_state(state)
        return site

    def _target_lock(self):
        """Сериализация доступа к цели: лок задания берётся по сайту и три сайта не разводит."""
        return site_lock(f"target-{self.ref}", self.environment, timeout=900)

    def base_url(self) -> str:
        port = self._state().get("port")
        return f"http://{self.bind_host}:{port}/" if port else ""

    def releases(self) -> list[str]:
        if not RELEASES.exists():
            return []
        return [p.name for p in RELEASES.iterdir()
                if p.is_dir() and not p.is_symlink() and p.name != "current"]

    def current_release(self) -> str | None:
        link = RELEASES / "current"
        return link.resolve().name if link.is_symlink() and link.exists() else None

    # ------------------------------------------------------------------- план
    def plan(self, build_dir: Path, build_id: str) -> DeployPlan:
        applied = self.current_release() == build_id
        steps = [
            {"id": "prepare_dirs", "detail": str(RELEASES), "mutation": True},
            {"id": "backup", "detail": "pg_dump базы и архив медиафайлов", "mutation": False},
            {"id": "restore_test", "detail": "восстановление дампа в пробную базу и сверка", "mutation": False},
            {"id": "build_app", "detail": f"next build → .releases/{build_id}/dist",
             "mutation": True, "noop": applied},
            {"id": "migrate_schema", "detail": "синхронизация схемы отдельным шагом после бэкапа",
             "mutation": True},
            {"id": "apply_tenant", "detail": f"конфигурация тенанта {self.site_id} в CMS", "mutation": True},
            {"id": "start_candidate", "detail": "next start на свободном порту", "mutation": True},
            {"id": "health_check", "detail": f"GET /robots.txt с Host: {self.domain}", "mutation": False},
            {"id": "switch_current", "detail": f"current → {build_id}", "mutation": True, "noop": applied},
            {"id": "stop_previous", "detail": "остановка прежнего процесса", "mutation": True},
            {"id": "post_switch_health", "detail": "повторная проверка после переключения", "mutation": False},
            {"id": "prune_releases",
             "detail": f"хранить {self.package['rollback_policy']['keep_releases']} релизов", "mutation": True},
        ]
        return DeployPlan(self.site_id, self.environment, build_id, self.ref, steps)

    # ------------------------------------------------------------ бэкап/restore
    def backup(self) -> dict:
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        directory = PATHS.root / "var" / "backups" / "payload-local"
        directory.mkdir(parents=True, exist_ok=True)
        dump = directory / f"{self.database_scope}-{stamp}.sql"
        database.dump(self.database_scope, dump)

        media_ref = None
        media_dir = PATHS.root / "var" / "media"
        if media_dir.exists():
            media = directory / f"media-{stamp}.tar"
            subprocess.run(["tar", "-cf", str(media), "-C", str(media_dir.parent), media_dir.name],
                           check=True, timeout=300)
            media_ref = str(media.relative_to(PATHS.root))

        record = {"taken": True, "ref": str(dump.relative_to(PATHS.root)),
                  "restore_verified": False, "verified_at": None}
        self._save_site(backup=record["ref"], backup_media=media_ref,
                        backup_bytes=dump.stat().st_size, backup_at=now())
        audit.record(job_id=f"backup-{self.site_id}-{stamp}", site_id=self.site_id,
                     environment=self.environment, action="backup", target=self.ref,
                     exit_code=0, mutation=False,
                     extra={"file": record["ref"], "media": media_ref, "bytes": dump.stat().st_size})
        return record

    def shared_digest(self) -> dict[str, str]:
        """Отпечаток состояния: счётчики коллекций. Сравнивается до и после restore-теста."""
        code, output = self._node_script("db-snapshot.ts")
        if code != 0:
            raise RestoreFailed(f"Снимок состояния не снят: {output[-400:]}",
                                field="database", blocks_stage="STAGING_DEPLOY")
        return {key: str(value) for key, value in json.loads(output.splitlines()[-1]).items()}

    def restore(self, archive_ref: str, destination: Path | None = None) -> bool:
        """Проверка восстановимости дампа в ОТДЕЛЬНОЙ базе.

        Живая база при этом не трогается: проверка бэкапа не имеет права ронять
        три работающих сайта. Возвращает True, только если дамп развернулся и
        содержит те же таблицы, что и рабочая база.
        """
        archive = PATHS.root / archive_ref
        if not archive.exists():
            return False
        probe = f"{self.database_scope}{PROBE_SUFFIX}"
        try:
            return database.restore_probe(self.database_scope, archive, probe_scope=probe)
        except FactoryError:
            return False

    # ---------------------------------------------------------------- процессы
    def _free_port(self, exclude: set[int]) -> tuple[int, socket.socket]:
        """Резервирует порт удержанием сокета: connect_ex даёт гонку между заданиями."""
        for port in range(int(self.port_range[0]), int(self.port_range[1]) + 1):
            if port in exclude:
                continue
            holder = socket.socket()
            holder.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                holder.bind((self.bind_host, port))
                return port, holder
            except OSError:
                holder.close()
        raise DeployFailed(f"Свободный порт в диапазоне {self.port_range} не найден.",
                           field="inventory/targets.yaml", blocks_stage="STAGING_DEPLOY")

    def _launcher(self, args: list[str], *, push: bool = False) -> list[str]:
        command = [sys.executable, str(LAUNCHER), "--scope", self.database_scope, "--cwd", str(APP)]
        if push:
            command.append("--push")
        return [*command, "--", *args]

    def _run_app(self, args: list[str], *, env_extra: dict | None = None,
                 push: bool = False, timeout: int = 1800) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.update(env_extra or {})
        return subprocess.run(self._launcher(args, push=push), cwd=PATHS.root, env=env,
                              capture_output=True, text=True, timeout=timeout, check=False)

    def _node_script(self, script: str, *args: str) -> tuple[int, str]:
        result = self._run_app([str(APP / "node_modules" / ".bin" / "tsx"),
                                str(APP / "scripts" / script), *args], timeout=900)
        return result.returncode, (result.stdout + result.stderr).strip()

    @staticmethod
    def _process_signature(pid: int) -> str | None:
        try:
            return (Path("/proc") / str(pid) / "cmdline").read_bytes().decode("utf-8", "replace")
        except OSError:
            return None

    def _spawn_server(self, port: int, dist: str, holder: socket.socket) -> tuple[int, str]:
        env = dict(os.environ)
        env.update({"NEXT_DIST_DIR": dist, "FACTORY_ENVIRONMENT": self.environment})
        log = self.root / f"server-{port}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        handle = log.open("ab")
        # Резерв снимается непосредственно перед стартом: окно гонки — миллисекунды,
        # и оно закрыто локом цели.
        holder.close()
        process = subprocess.Popen(
            self._launcher([str(APP / "node_modules" / ".bin" / "next"), "start",
                            "-p", str(port), "-H", self.bind_host]),
            cwd=PATHS.root, env=env, stdout=handle, stderr=subprocess.STDOUT,
        )
        # Запись в состояние сразу после запуска: иначе прерывание до health check
        # оставляет живой процесс, о котором никто не знает.
        signature = self._process_signature(process.pid) or ""
        self._save_process(candidate_pid=process.pid, candidate_port=port,
                           candidate_signature=signature)
        return process.pid, signature

    def _stop(self, pid: int | None, signature: str | None = None) -> str:
        if not pid:
            return "нечего останавливать"
        current = self._process_signature(pid)
        if current is None:
            return f"процесс {pid} уже не существует"
        if signature and current != signature:
            # PID переиспользуется после перезагрузки: убивать чужой процесс нельзя.
            return f"процесс {pid} принадлежит другой команде — не трогаем"
        try:
            os.kill(pid, 15)
        except ProcessLookupError:
            return f"процесс {pid} уже завершился"
        for _ in range(60):
            if self._process_signature(pid) is None:
                return f"процесс {pid} остановлен"
            time.sleep(0.5)
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            pass
        return f"процесс {pid} остановлен принудительно"

    def _probe(self, port: int, path: str = "/robots.txt") -> tuple[bool, str]:
        request = urllib.request.Request(f"http://{self.bind_host}:{port}{path}",
                                         headers={"Host": self.domain})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(request, timeout=30) as response:
                return response.status == 200, f"HTTP {response.status}"
        except urllib.error.HTTPError as error:
            return False, f"HTTP {error.code}"
        except Exception as error:  # noqa: BLE001 — любая ошибка транспорта = health провален
            return False, f"{type(error).__name__}: {error}"

    def _wait_healthy(self, port: int, deadline_seconds: int = 180) -> tuple[bool, str]:
        deadline = time.time() + deadline_seconds
        detail = "не запускался"
        while time.time() < deadline:
            ok, detail = self._probe(port)
            if ok:
                return True, detail
            time.sleep(1)
        return False, detail

    # ------------------------------------------------------------------ деплой
    def deploy(self, build_dir: Path, build_id: str, *, dry_run: bool = False) -> DeployResult:
        plan = self.plan(build_dir, build_id)
        if dry_run:
            return DeployResult(self.site_id, self.environment, build_id, build_id,
                                self._site_state().get("previous_release"), self.base_url(),
                                plan.steps, [], None, True)
        with self._target_lock():
            return self._deploy_locked(build_dir, build_id)

    def _deploy_locked(self, build_dir: Path, build_id: str) -> DeployResult:
        steps: list[dict] = []
        mutations: list[dict] = []
        started = {"value": now()}

        def record(step_id: str, detail: str, mutation: bool = False, status: str = "ok",
                   kind: str = "filesystem") -> None:
            finished = now()
            steps.append({"id": step_id, "detail": detail, "mutation": mutation, "status": status,
                          "started_at": started["value"], "finished_at": finished, "exit_code": 0})
            started["value"] = finished
            if mutation:
                mutations.append({"target": f"{self.ref}:{step_id}", "kind": kind,
                                  "detail": detail, "at": finished})

        release_dir = RELEASES / build_id
        dist_rel = f".releases/{build_id}/dist"
        previous_release = self.current_release()
        site_state = self._site_state()

        # Повторный выкат того же релиза — no-op. Прежде он выполнял полный цикл
        # мутаций и делал previous_release равным текущему, лишая сайт отката.
        if previous_release == build_id and (release_dir / "dist" / "BUILD_ID").exists():
            healthy, detail = self._probe(int(self._state().get("port") or 0)) if self._state().get("port") \
                else (False, "сервер не запускался")
            if healthy:
                record("prepare_dirs", "релиз уже развёрнут", status="skipped")
                record("post_switch_health", detail)
                return DeployResult(self.site_id, self.environment, build_id, build_id,
                                    site_state.get("previous_release"), self.base_url(),
                                    steps, [], None, True)

        RELEASES.mkdir(parents=True, exist_ok=True)
        record("prepare_dirs", str(RELEASES), mutation=True)

        backup = self.backup()
        record("backup", backup["ref"])

        # Восстановимость дампа проверяется здесь же, в отдельной базе: наличие
        # файла бэкапом не является, и job не имеет права дойти до DONE без этого.
        before = self.shared_digest()
        if not self.restore(backup["ref"]):
            raise RestoreFailed(
                f"Дамп {backup['ref']} не восстанавливается в пробную базу — бэкап недействителен.",
                field="backup", blocks_stage="STAGING_DEPLOY")
        after = self.shared_digest()
        if before != after:
            raise RestoreFailed("Проверка восстановления изменила рабочую базу.",
                                field="backup", blocks_stage="STAGING_DEPLOY")
        backup["restore_verified"] = True
        backup["verified_at"] = now()
        record("restore_test", f"пробная база развёрнута, состояние рабочей не изменилось: {len(before)} коллекций")

        if (release_dir / "dist" / "BUILD_ID").exists():
            record("build_app", "релиз уже собран", status="skipped")
        else:
            release_dir.mkdir(parents=True, exist_ok=True)
            built = self._run_app([str(APP / "node_modules" / ".bin" / "next"), "build"],
                                  env_extra={"NEXT_DIST_DIR": dist_rel})
            if built.returncode != 0:
                raise DeployFailed(
                    f"next build завершился с кодом {built.returncode}: "
                    f"{(built.stdout + built.stderr).strip()[-600:]}",
                    field="blueprints/payload-next-multisite", blocks_stage="STAGING_DEPLOY")
            record("build_app", dist_rel, mutation=True)

        # --- мутации базы: всё, что ниже, компенсируется восстановлением ------
        def rollback_database(reason: str) -> None:
            restored = database.restore(self.database_scope, PATHS.root / backup["ref"])
            audit.record(job_id=f"deploy-{self.site_id}-{build_id}", site_id=self.site_id,
                         environment=self.environment, action="database.rollback", target=self.ref,
                         exit_code=0 if restored else 1, mutation=True,
                         extra={"reason": reason, "backup": backup["ref"], "restored": restored})
            if not restored:
                raise RestoreFailed(
                    f"{reason}. Восстановление из {backup['ref']} тоже не удалось — база в неизвестном состоянии.",
                    field="database", blocks_stage="STAGING_DEPLOY")

        try:
            migrated = self._run_app([str(APP / "node_modules" / ".bin" / "tsx"),
                                      str(APP / "scripts" / "migrate.ts")], push=True, timeout=900)
            if migrated.returncode != 0:
                raise DeployFailed(
                    f"Миграция схемы не выполнена: {(migrated.stdout + migrated.stderr).strip()[-600:]}",
                    field="database", blocks_stage="STAGING_DEPLOY")
            record("migrate_schema", migrated.stdout.strip().splitlines()[-1] if migrated.stdout.strip()
                   else "схема синхронизирована", mutation=True, kind="database")

            config_path = build_dir / "tenant-config.json"
            applied = self._run_app([str(APP / "node_modules" / ".bin" / "tsx"),
                                     str(APP / "scripts" / "apply-tenant.ts"), str(config_path)])
            if applied.returncode != 0:
                raise DeployFailed(
                    f"Конфигурация тенанта не применена: {(applied.stdout + applied.stderr).strip()[-600:]}",
                    field="tenant", blocks_stage="STAGING_DEPLOY")
            record("apply_tenant",
                   applied.stdout.strip().splitlines()[-1] if applied.stdout.strip() else "ok",
                   mutation=True, kind="database")
        except FactoryError as error:
            rollback_database(f"Шаг выката провалился: {error}")
            raise DeployFailed(
                f"{error} База восстановлена из {backup['ref']}.",
                field="database", blocks_stage="STAGING_DEPLOY") from error

        state = self._state()
        previous_pid = state.get("pid")
        previous_port = state.get("port")
        previous_signature = state.get("signature")

        port, holder = self._free_port({previous_port} if previous_port else set())
        pid, signature = self._spawn_server(port, dist_rel, holder)
        record("start_candidate", f"pid={pid} port={port}", mutation=True, kind="service")

        healthy, detail = self._wait_healthy(port)
        if not healthy:
            self._stop(pid, signature)
            rollback_database(f"Новый процесс не прошёл health check: {detail}")
            raise DeployFailed(f"Новый процесс не прошёл health check: {detail}. "
                               f"База восстановлена из {backup['ref']}.",
                               field="health", blocks_stage="STAGING_DEPLOY")
        record("health_check", detail)

        # previous_release фиксируется ДО переключения и никогда не становится
        # равным текущему релизу: иначе retry после провала лишает сайт отката.
        recorded_previous = previous_release if previous_release != build_id \
            else site_state.get("previous_release")
        self._save_site(previous_release=recorded_previous, backup=backup["ref"],
                        restore_verified=True, updated_at=now())

        link = RELEASES / "current"
        temporary = RELEASES / "current.new"
        if temporary.is_symlink() or temporary.exists():
            temporary.unlink()
        temporary.symlink_to(release_dir, target_is_directory=True)
        temporary.replace(link)
        record("switch_current", build_id, mutation=True, kind="symlink")

        stop_detail = self._stop(previous_pid, previous_signature) if previous_pid != pid \
            else "прежний процесс совпадает с текущим"
        record("stop_previous", stop_detail, mutation=True, kind="service")

        self._save_process(pid=pid, port=port, signature=signature, release=build_id,
                           candidate_pid=None, candidate_port=None, candidate_signature=None,
                           updated_at=now())

        healthy, detail = self._probe(port)
        record("post_switch_health", detail, status="ok" if healthy else "failed")
        if not healthy:
            raise DeployFailed(f"Проверка после переключения провалена: {detail}",
                               field="health", blocks_stage="STAGING_DEPLOY")

        pruned = self._prune(int(self.package["rollback_policy"]["keep_releases"]))
        record("prune_releases", ", ".join(pruned) or "нечего удалять", mutation=bool(pruned))

        audit.record(job_id=f"deploy-{self.site_id}-{build_id}", site_id=self.site_id,
                     environment=self.environment, action="deploy", target=self.ref,
                     exit_code=0, mutation=True,
                     extra={"build_id": build_id, "release": build_id, "port": port,
                            "previous_release": recorded_previous})

        return DeployResult(self.site_id, self.environment, build_id, build_id, recorded_previous,
                            self.base_url(), steps, mutations, backup, False)

    def _prune(self, keep: int) -> list[str]:
        """Удаляет самые старые релизы по времени, сохраняя точки отката всех сайтов."""
        protect = {self.current_release() or ""}
        for site in self._state()["sites"].values():
            protect.add(site.get("previous_release") or "")
        directories = sorted((RELEASES / name for name in self.releases()),
                             key=lambda path: path.stat().st_mtime)
        removed: list[str] = []
        for path in directories[: max(0, len(directories) - keep)]:
            if path.name in protect:
                continue
            shutil.rmtree(path, ignore_errors=True)
            removed.append(path.name)
        return removed

    # -------------------------------------------------------- здоровье и откат
    def health(self) -> tuple[bool, str]:
        port = self._state().get("port")
        if not port:
            return False, "сервер не запускался"
        return self._probe(int(port))

    def rollback(self) -> DeployResult:
        with self._target_lock():
            return self._rollback_locked()

    def _rollback_locked(self) -> DeployResult:
        state = self._state()
        site_state = self._site_state()
        previous = site_state.get("previous_release")
        current = self.current_release()
        if not previous or previous == current:
            raise DeployFailed(
                "Откат невозможен: предыдущий релиз не зафиксирован или совпадает с текущим.",
                field="rollback", blocks_stage="ROLLED_BACK")

        release_dir = RELEASES / previous
        if not (release_dir / "dist" / "BUILD_ID").exists():
            raise DeployFailed(f"Каталог релиза {previous} отсутствует: откатывать не на что.",
                               field="rollback", blocks_stage="ROLLED_BACK")

        # Всё, что различает сайты этого blueprint, лежит в базе. Откат только кода
        # вернул бы прежний код с новой конфигурацией и отрапортовал бы успех.
        backup_ref = site_state.get("backup")
        if not backup_ref or not (PATHS.root / backup_ref).exists():
            raise DeployFailed(
                "Откат невозможен: бэкап базы для этого сайта не зафиксирован, а конфигурация "
                "сайтов живёт в базе. Восстановите базу вручную и повторите.",
                field="rollback", blocks_stage="ROLLED_BACK")

        steps: list[dict] = []
        mutations: list[dict] = []

        def record(step_id: str, detail: str, mutation: bool = False, kind: str = "filesystem") -> None:
            moment = now()
            steps.append({"id": step_id, "detail": detail, "mutation": mutation, "status": "ok",
                          "started_at": moment, "finished_at": moment, "exit_code": 0})
            if mutation:
                mutations.append({"target": f"{self.ref}:{step_id}", "kind": kind,
                                  "detail": detail, "at": moment})

        # Сначала база: если восстановление не удалось, код трогать нельзя.
        restored = database.restore(self.database_scope, PATHS.root / backup_ref)
        if not restored:
            raise RestoreFailed(
                f"Восстановление базы из {backup_ref} не выполнено — откат прерван до смены кода.",
                field="database", blocks_stage="ROLLED_BACK")
        record("restore_database", backup_ref, mutation=True, kind="database")

        port, holder = self._free_port({state.get("port")} if state.get("port") else set())
        pid, signature = self._spawn_server(port, f".releases/{previous}/dist", holder)
        healthy, detail = self._wait_healthy(port)
        if not healthy:
            self._stop(pid, signature)
            raise DeployFailed(f"Прежний релиз не поднялся: {detail}",
                               field="rollback", blocks_stage="ROLLED_BACK")
        record("start_previous", f"pid={pid} port={port}", mutation=True, kind="service")

        link = RELEASES / "current"
        temporary = RELEASES / "current.new"
        if temporary.is_symlink() or temporary.exists():
            temporary.unlink()
        temporary.symlink_to(release_dir, target_is_directory=True)
        temporary.replace(link)
        record("switch_current", f"current → {previous}", mutation=True, kind="symlink")

        record("stop_previous", self._stop(state.get("pid"), state.get("signature")),
               mutation=True, kind="service")

        self._save_process(pid=pid, port=port, signature=signature, release=previous,
                           candidate_pid=None, candidate_port=None, candidate_signature=None,
                           updated_at=now())
        # Точка отката не «переворачивается»: откат из отката требует нового бэкапа.
        self._save_site(previous_release=None, rolled_back_from=current, updated_at=now())
        record("post_switch_health", self._probe(port)[1])

        audit.record(job_id=f"rollback-{self.site_id}-{previous}", site_id=self.site_id,
                     environment=self.environment, action="rollback", target=self.ref,
                     exit_code=0, mutation=True,
                     extra={"from": current, "to": previous, "database_backup": backup_ref})

        return DeployResult(self.site_id, self.environment, previous, previous, current,
                            self.base_url(), steps, mutations, None, False)

    def stop(self) -> None:
        with self._target_lock():
            state = self._state()
            self._stop(state.get("pid"), state.get("signature"))
            self._stop(state.get("candidate_pid"), state.get("candidate_signature"))
            self._save_process(pid=None, candidate_pid=None, updated_at=now())

    def sites_on_target(self) -> list[str]:
        """Сайты, состояние которых лежит на этой цели. Нужен командам, останавливающим цель."""
        return sorted(self._state()["sites"])
