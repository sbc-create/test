"""Цель развёртывания для blueprint payload-next-multisite.

Особенность blueprint: одно приложение обслуживает три сайта. Поэтому релиз
(собранное приложение) общий, а «деплой сайта» — это применение конфигурации
его тенанта к CMS плюс переключение на релиз, в котором эта конфигурация
работает. Инварианты базового контракта соблюдаются полностью: план ничего не
меняет, мутация начинается после бэкапа, `current` переключается только после
успешной проверки нового процесса, предыдущий релиз остаётся для отката.
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
from factory.errors import BlockedAccess, DeployFailed
from factory.paths import PATHS
from factory.targets.base import DeployPlan, DeployResult, now

APP = PATHS.root / "blueprints" / "payload-next-multisite" / "app"
RELEASES = APP / ".releases"
LAUNCHER = PATHS.root / "tests" / "tools" / "with_app_env.py"


class PayloadMultisiteTarget:
    """Локальный стенд: сборка Next, применение тенанта, атомарное переключение."""

    adapter = "payload_multisite"

    def __init__(self, conf: dict, package: dict) -> None:
        self.conf = conf
        self.package = package
        self.site_id = package["site_id"]
        self.environment = package["environment"]
        self.domain = package["domain"]
        self.database_scope = package.get("database_ref") or "anime"
        self.root = PATHS.root / conf.get("root", "var/targets/payload-local")
        self.root.mkdir(parents=True, exist_ok=True)
        self.bind_host = conf.get("bind_host", "127.0.0.1")
        self.port_range = tuple(conf.get("port_range", [8110, 8129]))
        if self.environment == "production":
            # Production для этого blueprint не разрешён ни одной записью inventory.
            raise BlockedAccess(
                "Цель payload-local не пригодна для production.",
                field="inventory/targets.yaml",
                required_input="Цель с production_capable: true и подтверждённым доменом",
                blocks_stage="PRODUCTION_DEPLOY",
            )

    # ------------------------------------------------------------------ состояние
    @property
    def _state_path(self) -> Path:
        return self.root / "state.json"

    def _state(self) -> dict:
        if self._state_path.exists():
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        return {}

    def _save_state(self, **kwargs) -> dict:
        state = self._state()
        state.update(kwargs)
        self._state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return state

    def base_url(self) -> str:
        port = self._state().get("port")
        return f"http://{self.bind_host}:{port}/" if port else ""

    def releases(self) -> list[str]:
        if not RELEASES.exists():
            return []
        return sorted(p.name for p in RELEASES.iterdir() if p.is_dir() and p.name != "current")

    def current_release(self) -> str | None:
        link = RELEASES / "current"
        return link.resolve().name if link.is_symlink() and link.exists() else None

    # ------------------------------------------------------------------ план
    def plan(self, build_dir: Path, build_id: str) -> DeployPlan:
        applied = self.current_release() == build_id
        steps = [
            {"id": "prepare_dirs", "detail": f"{RELEASES}", "mutation": True},
            {"id": "backup", "detail": "pg_dump базы и архив медиафайлов", "mutation": False},
            {"id": "build_app", "detail": f"next build → .releases/{build_id}/dist",
             "mutation": True, "noop": applied},
            {"id": "apply_tenant", "detail": f"конфигурация тенанта {self.site_id} в CMS", "mutation": True},
            {"id": "start_candidate", "detail": "next start на свободном порту", "mutation": True},
            {"id": "health_check", "detail": f"GET /robots.txt с Host: {self.domain}", "mutation": False},
            {"id": "switch_current", "detail": f"current → {build_id}", "mutation": True, "noop": applied},
            {"id": "stop_previous", "detail": "остановка прежнего процесса", "mutation": True},
            {"id": "post_switch_health", "detail": "повторная проверка после переключения", "mutation": False},
            {"id": "prune_releases", "detail": f"хранить {self.package['rollback_policy']['keep_releases']} релизов",
             "mutation": True},
        ]
        return DeployPlan(self.site_id, self.environment, build_id, self.conf.get("ref", ""), steps)

    # ------------------------------------------------------------------ бэкап
    def backup(self) -> dict:
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        directory = PATHS.root / "var" / "backups" / "payload-local"
        directory.mkdir(parents=True, exist_ok=True)
        dump = directory / f"{self.database_scope}-{stamp}.sql"
        database.dump(self.database_scope, dump)
        media = directory / f"media-{stamp}.tar"
        media_dir = PATHS.root / "var" / "media"
        if media_dir.exists():
            subprocess.run(["tar", "-cf", str(media), "-C", str(media_dir.parent), media_dir.name],
                           check=True, timeout=300)
        record = {"taken": True, "ref": str(dump.relative_to(PATHS.root)),
                  "restore_verified": False, "verified_at": None}
        self._save_state(last_backup=str(dump.relative_to(PATHS.root)),
                         last_backup_media=str(media.relative_to(PATHS.root)) if media.exists() else None,
                         last_backup_bytes=dump.stat().st_size)
        audit.record(job_id=f"backup-{self.site_id}-{stamp}", site_id=self.site_id,
                     environment=self.environment, action="backup",
                     target=self.conf.get("ref", ""), exit_code=0, mutation=False,
                     extra={"file": record["ref"], "bytes": dump.stat().st_size})
        return record

    # ------------------------------------------------------------------ запуск
    def _free_port(self, exclude: set[int]) -> int:
        for port in range(int(self.port_range[0]), int(self.port_range[1]) + 1):
            if port in exclude:
                continue
            with socket.socket() as probe:
                if probe.connect_ex((self.bind_host, port)) != 0:
                    return port
        raise DeployFailed(f"Свободный порт в диапазоне {self.port_range} не найден.",
                           field="inventory/targets.yaml", blocks_stage="STAGING_DEPLOY")

    def _run_app(self, args: list[str], *, env_extra: dict | None = None,
                 timeout: int = 900) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.update(env_extra or {})
        command = [sys.executable, str(LAUNCHER), "--scope", self.database_scope,
                   "--cwd", str(APP), "--", *args]
        return subprocess.run(command, cwd=PATHS.root, env=env, capture_output=True, text=True,
                              timeout=timeout, check=False)

    def _spawn_server(self, port: int, dist: str) -> int:
        env = dict(os.environ)
        env.update({"NEXT_DIST_DIR": dist, "FACTORY_ENVIRONMENT": self.environment})
        log = self.root / f"server-{port}.log"
        handle = log.open("ab")
        process = subprocess.Popen(
            [sys.executable, str(LAUNCHER), "--scope", self.database_scope, "--cwd", str(APP), "--",
             str(APP / "node_modules" / ".bin" / "next"), "start", "-p", str(port), "-H", self.bind_host],
            cwd=PATHS.root, env=env, stdout=handle, stderr=subprocess.STDOUT,
        )
        return process.pid

    def _stop(self, pid: int | None) -> None:
        if not pid:
            return
        try:
            os.kill(pid, 15)
        except ProcessLookupError:
            return
        for _ in range(60):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.5)
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            pass

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
                                self.current_release(), self.base_url(), plan.steps, [], None, True)

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
                mutations.append({"target": f"{self.conf.get('ref', '')}:{step_id}", "kind": kind,
                                  "detail": detail, "at": now()})

        RELEASES.mkdir(parents=True, exist_ok=True)
        record("prepare_dirs", str(RELEASES), mutation=True)

        backup = self.backup()
        record("backup", backup["ref"])

        release_dir = RELEASES / build_id
        dist_rel = f".releases/{build_id}/dist"
        if (release_dir / "dist" / "BUILD_ID").exists():
            record("build_app", "релиз уже собран", mutation=False, status="noop")
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

        config_path = build_dir / "tenant-config.json"
        applied = self._run_app([str(APP / "node_modules" / ".bin" / "tsx"),
                                 str(APP / "scripts" / "apply-tenant.ts"), str(config_path)])
        if applied.returncode != 0:
            raise DeployFailed(
                f"Конфигурация тенанта не применена: {(applied.stdout + applied.stderr).strip()[-600:]}",
                field="tenant", blocks_stage="STAGING_DEPLOY")
        record("apply_tenant", applied.stdout.strip().splitlines()[-1] if applied.stdout.strip() else "ok",
               mutation=True, kind="database")

        state = self._state()
        previous_pid = state.get("pid")
        previous_port = state.get("port")
        previous_release = self.current_release()

        port = self._free_port({previous_port} if previous_port else set())
        pid = self._spawn_server(port, dist_rel)
        record("start_candidate", f"pid={pid} port={port}", mutation=True, kind="service")

        healthy, detail = self._wait_healthy(port)
        if not healthy:
            self._stop(pid)
            raise DeployFailed(f"Новый процесс не прошёл health check: {detail}",
                               field="health", blocks_stage="STAGING_DEPLOY")
        record("health_check", detail)

        link = RELEASES / "current"
        temporary = RELEASES / "current.new"
        if temporary.is_symlink() or temporary.exists():
            temporary.unlink()
        temporary.symlink_to(release_dir, target_is_directory=True)
        temporary.replace(link)
        record("switch_current", build_id, mutation=True, kind="symlink")

        if previous_pid and previous_pid != pid:
            self._stop(previous_pid)
        record("stop_previous", f"pid={previous_pid}", mutation=True, kind="service")

        self._save_state(pid=pid, port=port, release=build_id, previous_release=previous_release,
                         backup=backup, updated_at=now())

        healthy, detail = self._probe(port)
        record("post_switch_health", detail, status="ok" if healthy else "failed")
        if not healthy:
            raise DeployFailed(f"Проверка после переключения провалена: {detail}",
                               field="health", blocks_stage="STAGING_DEPLOY")

        pruned = self._prune(int(self.package["rollback_policy"]["keep_releases"]),
                             protect={build_id, previous_release or ""})
        record("prune_releases", ", ".join(pruned) or "нечего удалять", mutation=bool(pruned))

        audit.record(job_id=f"deploy-{self.site_id}-{build_id}", site_id=self.site_id,
                     environment=self.environment, action="deploy",
                     target=self.conf.get("ref", ""), exit_code=0, mutation=True,
                     extra={"build_id": build_id, "release": build_id, "port": port})

        return DeployResult(self.site_id, self.environment, build_id, build_id, previous_release,
                            self.base_url(), steps, mutations, backup, False)

    def _prune(self, keep: int, protect: set[str]) -> list[str]:
        releases = self.releases()
        removed: list[str] = []
        for name in releases[: max(0, len(releases) - keep)]:
            if name in protect:
                continue
            shutil.rmtree(RELEASES / name, ignore_errors=True)
            removed.append(name)
        return removed

    # ------------------------------------------------------------------ здоровье и откат
    def health(self) -> tuple[bool, str]:
        port = self._state().get("port")
        if not port:
            return False, "сервер не запускался"
        return self._probe(int(port))

    def rollback(self) -> DeployResult:
        state = self._state()
        previous = state.get("previous_release")
        current = self.current_release()
        if not previous or previous == current:
            raise DeployFailed(
                "Откат невозможен: предыдущий релиз не зафиксирован или совпадает с текущим.",
                field="rollback", blocks_stage="ROLLED_BACK")
        release_dir = RELEASES / previous
        if not (release_dir / "dist" / "BUILD_ID").exists():
            raise DeployFailed(f"Каталог релиза {previous} отсутствует: откатывать не на что.",
                               field="rollback", blocks_stage="ROLLED_BACK")

        steps: list[dict] = []
        port = self._free_port({state.get("port")} if state.get("port") else set())
        pid = self._spawn_server(port, f".releases/{previous}/dist")
        healthy, detail = self._wait_healthy(port)
        if not healthy:
            self._stop(pid)
            raise DeployFailed(f"Прежний релиз не поднялся: {detail}", field="rollback",
                               blocks_stage="ROLLED_BACK")
        steps.append({"id": "start_previous", "detail": f"pid={pid} port={port}", "mutation": True,
                      "status": "ok", "started_at": now(), "finished_at": now(), "exit_code": 0})
        rollback_mutations = [{"target": f"{self.conf.get('ref', '')}:start_previous", "kind": "service",
                               "detail": f"pid={pid} port={port}", "at": now()}]

        link = RELEASES / "current"
        temporary = RELEASES / "current.new"
        if temporary.is_symlink() or temporary.exists():
            temporary.unlink()
        temporary.symlink_to(release_dir, target_is_directory=True)
        temporary.replace(link)
        steps.append({"id": "switch_current", "detail": previous, "mutation": True,
                      "status": "ok", "started_at": now(), "finished_at": now(), "exit_code": 0})
        rollback_mutations.append({"target": f"{self.conf.get('ref', '')}:switch_current",
                                   "kind": "symlink", "detail": f"current → {previous}", "at": now()})

        self._stop(state.get("pid"))
        self._save_state(pid=pid, port=port, release=previous, previous_release=current,
                         updated_at=now())
        steps.append({"id": "post_switch_health", "detail": self._probe(port)[1], "mutation": False,
                      "status": "ok", "started_at": now(), "finished_at": now(), "exit_code": 0})

        audit.record(job_id=f"rollback-{self.site_id}-{previous}", site_id=self.site_id,
                     environment=self.environment, action="rollback",
                     target=self.conf.get("ref", ""), exit_code=0, mutation=True,
                     extra={"from": current, "to": previous})
        return DeployResult(self.site_id, self.environment, previous, previous, current,
                            self.base_url(), steps, rollback_mutations, None, False)

    def stop(self) -> None:
        self._stop(self._state().get("pid"))
        self._save_state(pid=None)
