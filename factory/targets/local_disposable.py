"""Одноразовая локальная цель: PHP built-in server поверх атомарных релизов.

Назначение — доказать работоспособность конвейера и SEO-ворот на реальном HTTP,
когда staging-хост не передан. Цель помечена production_capable: false и не может
быть выбрана для production (проверяется валидатором).
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from factory.errors import BlockedAccess, DeployFailed
from factory.paths import PATHS
from factory.targets.base import DeployPlan, DeployResult, now


class LocalDisposableTarget:
    adapter = "local_disposable"

    def __init__(self, conf: dict, package: dict) -> None:
        self.conf = conf
        self.pkg = package
        self.site_id = package["site_id"]
        self.environment = package["environment"]
        root = conf.get("root") or f"var/targets/{conf.get('ref', 'local-disposable')}"
        self.root = (PATHS.root / root / self.site_id).resolve()
        self.releases_dir = self.root / "releases"
        self.shared_dir = self.root / "shared"
        self.current = self.root / "current"
        self.state_file = self.root / "target-state.json"
        self.bind = conf.get("bind_host", "127.0.0.1")
        self.port_range = conf.get("port_range", [8081, 8099])

    # ---------------------------------------------------------------- служебное
    def _state(self) -> dict:
        if self.state_file.exists():
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        return {}

    def _save_state(self, **kwargs) -> dict:
        state = self._state()
        state.update(kwargs)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return state

    def _pick_port(self) -> int:
        existing = self._state().get("port")
        if existing and self._port_free(int(existing)):
            return int(existing)
        for port in range(int(self.port_range[0]), int(self.port_range[1]) + 1):
            if self._port_free(port):
                return port
        raise BlockedAccess(
            f"Свободный порт в диапазоне {self.port_range} не найден: вероятно, остались "
            "незакрытые стенды. Освободи их командой `python3 -m factory decommission --site <id>`.",
            field="inventory/targets.yaml",
            required_input="Расширь port_range или останови неиспользуемые стенды",
            blocks_stage="STAGING_DEPLOY")

    def _port_free(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((self.bind, port))
                return True
            except OSError:
                return False

    def base_url(self) -> str:
        state = self._state()
        port = state.get("port") or self.port_range[0]
        return f"http://{self.bind}:{port}"

    def releases(self) -> list[str]:
        if not self.releases_dir.exists():
            return []
        return sorted(p.name for p in self.releases_dir.iterdir() if p.is_dir())

    def current_release(self) -> str | None:
        if self.current.is_symlink():
            return Path(os.readlink(self.current)).name
        return None

    def staging_credentials(self) -> str:
        """Учётные данные стенда генерируются локально и не попадают ни в git, ни в отчёт."""
        auth_file = self.root / "staging-auth"
        if auth_file.exists():
            return auth_file.read_text(encoding="utf-8").strip()
        self.root.mkdir(parents=True, exist_ok=True)
        value = f"factory:{secrets.token_urlsafe(18)}"
        auth_file.write_text(value, encoding="utf-8")
        auth_file.chmod(0o600)
        return value

    # ---------------------------------------------------------------- контракт
    def plan(self, build_dir: Path, build_id: str) -> DeployPlan:
        already = build_id in self.releases() and self.current_release() == build_id
        steps = [
            {"id": "prepare_dirs", "detail": f"releases/, shared/ в {self.root}", "mutation": not self.root.exists()},
            {"id": "backup", "detail": "tar shared/ и текущего состояния цели", "mutation": False},
            {"id": "upload_release", "detail": f"releases/{build_id}", "mutation": not already},
            {"id": "link_shared", "detail": "симлинки на shared-данные", "mutation": not already},
            {"id": "start_server", "detail": f"php -S {self.bind}:<port>", "mutation": True},
            {"id": "health_check", "detail": "GET / до переключения current", "mutation": False},
            {"id": "switch_current", "detail": f"current → releases/{build_id}", "mutation": not already},
            {"id": "post_switch_health", "detail": "повторный health после переключения", "mutation": False},
            {"id": "prune_releases", "detail": f"хранить {self.pkg['rollback_policy']['keep_releases']} релизов", "mutation": not already},
        ]
        if already:
            for step in steps:
                step["idempotent_noop"] = True
        return DeployPlan(self.site_id, self.environment, build_id, self.conf.get("ref", "local-disposable"), steps)

    def backup(self) -> dict:
        """Бэкап изменяемых данных цели. Восстановимость проверяется отдельно."""
        PATHS.backups.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        archive = PATHS.backups / f"{self.site_id}-{self.environment}-{stamp}.tar.gz"
        self.shared_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(self.shared_dir, arcname="shared")
            if self.state_file.exists():
                tar.add(self.state_file, arcname="target-state.json")
        return {"taken": True, "ref": str(archive.relative_to(PATHS.root)), "restore_verified": False, "verified_at": None}

    @staticmethod
    def _tree_digest(root: Path) -> dict[str, str]:
        """SHA-256 каждого файла дерева. Логи исключены: они меняются постоянно."""
        out: dict[str, str] = {}
        if not root.exists():
            return out
        for file in sorted(root.rglob("*")):
            if file.is_file() and "logs" not in file.relative_to(root).parts:
                out[str(file.relative_to(root))] = hashlib.sha256(file.read_bytes()).hexdigest()
        return out

    def shared_digest(self) -> dict[str, str]:
        """Слепок текущих изменяемых данных цели — для сравнения с восстановленным."""
        return self._tree_digest(self.shared_dir)

    def restore(self, archive_ref: str, destination: Path) -> bool:
        """Разворачивает бэкап и доказывает целостность: извлечено ровно то, что в архиве.

        Проверяется не факт распаковки, а совпадение состава и размеров с описью
        архива — усечённый или повреждённый архив этим отсеивается. Совпадение с
        живыми данными сравнивает вызывающий (см. pipeline: probe сразу после backup).
        """
        archive = PATHS.root / archive_ref
        if not archive.exists():
            return False
        shutil.rmtree(destination, ignore_errors=True)
        destination.mkdir(parents=True, exist_ok=True)
        try:
            with tarfile.open(archive, "r:gz") as tar:
                members = [m for m in tar.getmembers() if m.isfile()]
                tar.extractall(destination, filter="data")
        except (tarfile.TarError, EOFError, OSError):
            # Повреждённый или усечённый архив — это неподтверждённое восстановление,
            # а не исключение, вылетающее из конвейера.
            return False
        # Пустой shared/ — валидное состояние нового сайта: в архиве тогда нет
        # обычных файлов, только каталог, и это не признак повреждения.
        for member in members:
            extracted = destination / member.name
            if not extracted.is_file() or extracted.stat().st_size != member.size:
                return False
        return (destination / "shared").exists()

    def deploy(self, build_dir: Path, build_id: str, *, dry_run: bool = False) -> DeployResult:
        plan = self.plan(build_dir, build_id)
        if dry_run:
            return DeployResult(self.site_id, self.environment, build_id, build_id, self.current_release(),
                                self.base_url(), steps=plan.steps, mutations=[], backup=None,
                                idempotent_noop=all(s.get("idempotent_noop") for s in plan.steps))
        steps: list[dict] = []
        mutations: list[dict] = []
        previous = self.current_release()
        #: Менялось ли фактическое содержимое релиза. Перезапуск процесса сервера
        #: содержимым не является и на идемпотентность не влияет.
        content_changed = False

        def step(step_id: str, detail: str, mutation: bool = False, noop: bool = False) -> None:
            steps.append({"id": step_id, "status": "ok", "started_at": now(), "finished_at": now(),
                          "exit_code": 0, "detail": detail, "mutation": mutation})
            if mutation:
                mutations.append({"target": str(self.root), "kind": "filesystem", "detail": detail,
                                  "at": now(), "idempotent_noop": noop})

        self.releases_dir.mkdir(parents=True, exist_ok=True)
        self.shared_dir.mkdir(parents=True, exist_ok=True)
        (self.shared_dir / "logs").mkdir(exist_ok=True)
        step("prepare_dirs", f"Каталоги цели готовы: {self.root}")

        backup = self.backup()
        step("backup", f"Бэкап изменяемых данных: {backup['ref']}")

        release_dir = self.releases_dir / build_id
        # Готовым считается только релиз с маркером: прерванный copytree оставлял
        # полурелиз, который навсегда выглядел выгруженным.
        already_present = release_dir.exists() and (release_dir / ".complete").exists()
        if not already_present:
            staging_dir = self.releases_dir / f".{build_id}.tmp"
            shutil.rmtree(staging_dir, ignore_errors=True)
            shutil.rmtree(release_dir, ignore_errors=True)
            shutil.copytree(build_dir, staging_dir)
            (staging_dir / ".complete").write_text(now(), encoding="utf-8")
            os.replace(staging_dir, release_dir)      # атомарная публикация каталога
            content_changed = True
            step("upload_release", f"Релиз {build_id} размещён", mutation=True)
        else:
            step("upload_release", f"Релиз {build_id} уже присутствует — повторная выгрузка не выполнялась", mutation=True, noop=True)

        # C: кандидат проверяется на отдельном порту, а рабочий сервер продолжает
        # обслуживать текущий релиз — простоя между остановкой и стартом больше нет.
        candidate_port = self._pick_free_port(exclude={self._state().get("port")})
        self._save_state(pending_build_id=build_id, pending_at=now())   # intent до мутации
        auth = self.staging_credentials() if self.environment != "production" else ""
        candidate_pid = self._spawn(candidate_port, release_dir / "public", auth)
        try:
            ok, detail = self._probe(f"http://{self.bind}:{candidate_port}/", auth)
        finally:
            self._kill(candidate_pid)
        if not ok:
            # Рабочий сервер не останавливался, сайт всё это время доступен.
            raise DeployFailed(f"Health check релиза не пройден: {detail}", field="deploy.health",
                               required_input="Работоспособная сборка", blocks_stage="STAGING_DEPLOY")
        step("health_check", f"Проверка кандидата на отдельном порту {candidate_port}: {detail}")

        if self.current_release() == build_id:
            step("switch_current", f"current уже указывает на {build_id}", mutation=True, noop=True)
        else:
            tmp = self.root / ".current.new"
            if tmp.exists() or tmp.is_symlink():
                tmp.unlink()
            tmp.symlink_to(release_dir)
            os.replace(tmp, self.current)      # атомарная замена симлинка
            content_changed = True
            step("switch_current", f"current → releases/{build_id}", mutation=True)

        # Рабочий сервер всегда обслуживает симлинк current, поэтому переключение
        # релиза видно ему сразу; процесс перезапускается только если он не жив.
        port = self._ensure_server(auth)
        step("start_server", f"PHP-сервер обслуживает current на {self.bind}:{port}", mutation=True)
        ok, detail = self._probe(f"http://{self.bind}:{port}/", auth)
        if not ok:
            raise DeployFailed(f"Health после переключения не пройден: {detail}", field="deploy.health",
                               required_input="Работоспособная сборка", blocks_stage="STAGING_DEPLOY")
        step("post_switch_health", f"Проверка после переключения: {detail}")

        keep = int(self.pkg["rollback_policy"]["keep_releases"])
        # Защищаем и сохранённую точку отката: иначе очистка может удалить релиз,
        # на который ссылается состояние, и откат окажется невозможен.
        protected = {build_id, previous or "", self._state().get("previous_release_id") or ""}
        pruned = self._prune(keep, protect=protected)
        content_changed = content_changed or bool(pruned)
        step("prune_releases", f"Удалено устаревших релизов: {len(pruned)}; хранится {keep} плюс защищённые (текущий и предыдущий)", mutation=bool(pruned), noop=not pruned)

        # previous_release_id меняется только когда current действительно переключился:
        # иначе повторный деплой затирает точку отката самим собой.
        stored_previous = self._state().get("previous_release_id")
        effective_previous = previous if (previous and previous != build_id) else stored_previous
        self._save_state(port=port, build_id=build_id, previous_release_id=effective_previous,
                         deployed_at=now(), docroot="current", pending_build_id=None, pending_at=None)
        return DeployResult(self.site_id, self.environment, build_id, build_id, previous,
                            f"http://{self.bind}:{port}", steps=steps, mutations=mutations, backup=backup,
                            idempotent_noop=not content_changed)

    def _prune(self, keep: int, protect: set[str]) -> list[str]:
        # Сортировка по времени, а не по имени: имя — хеш, и лексикографический
        # порядок удалял бы случайный релиз вместо самого старого.
        candidates = [p for p in self.releases_dir.iterdir() if p.is_dir() and p.name not in protect]
        releases = [p.name for p in sorted(candidates, key=lambda p: p.stat().st_mtime)]
        excess = releases[:-keep] if len(releases) > keep else []
        for name in excess:
            shutil.rmtree(self.releases_dir / name, ignore_errors=True)
        return excess

    # ---------------------------------------------------------------- сервер
    def _pid_file(self) -> Path:
        return self.root / "server.pid"

    def _pick_free_port(self, exclude: set) -> int:
        """Свободный порт для проверки релиза-кандидата, отличный от рабочего."""
        blocked = {int(p) for p in exclude if p}
        for port in range(int(self.port_range[0]), int(self.port_range[1]) + 1):
            if port not in blocked and self._port_free(port):
                return port
        raise BlockedAccess("Нет свободного порта для проверки релиза-кандидата.",
                            field="inventory/targets.yaml",
                            required_input="Расширь port_range или останови неиспользуемые стенды",
                            blocks_stage="STAGING_DEPLOY")

    def _spawn(self, port: int, docroot: Path, auth: str) -> int:
        """Поднимает временный процесс сервера и возвращает его pid."""
        router = PATHS.automation / "local" / "router.php"
        env = dict(os.environ)
        env["FACTORY_ENVIRONMENT"] = self.environment
        if auth:
            env["FACTORY_STAGING_AUTH"] = auth
        log = self.shared_dir / "logs" / "php-candidate.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("ab") as fh:
            proc = subprocess.Popen(["php", "-S", f"{self.bind}:{port}", "-t", str(docroot), str(router)],
                                    stdout=fh, stderr=fh, env=env, start_new_session=True)
        for _ in range(50):
            if not self._port_free(port):
                break
            time.sleep(0.1)
        return proc.pid

    def _kill(self, pid: int) -> None:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            pass

    def _server_alive(self) -> bool:
        pid_file = self._pid_file()
        if not pid_file.exists():
            return False
        try:
            os.kill(int(pid_file.read_text(encoding="utf-8").strip()), 0)
            return True
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            return False

    def _ensure_server(self, auth: str) -> int:
        """Гарантирует работающий сервер поверх симлинка current.

        Docroot — `current/public`, поэтому переключение релиза видно процессу
        мгновенно, а перезапуск нужен только если процесс не жив.
        """
        state = self._state()
        state_port = state.get("port")
        # Процесс, поднятый с docroot конкретного релиза, не увидит переключения
        # симлинка — такой сервер обязателен к перезапуску.
        serves_current = state.get("docroot") == "current"
        if serves_current and self._server_alive() and state_port and not self._port_free(int(state_port)):
            return int(state_port)
        self._stop_server()
        port = int(state_port) if state_port and self._port_free(int(state_port)) else self._pick_port()
        self._start_server(port, self.current, auth)
        self._save_state(port=port, docroot="current")
        return port

    def _start_server(self, port: int, release_dir: Path, auth: str) -> None:
        self._stop_server()
        docroot = release_dir / "public"
        router = PATHS.automation / "local" / "router.php"
        env = dict(os.environ)
        env["FACTORY_ENVIRONMENT"] = self.environment
        if auth:
            env["FACTORY_STAGING_AUTH"] = auth
        log = self.shared_dir / "logs" / "php-server.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("ab") as fh:
            proc = subprocess.Popen(
                ["php", "-S", f"{self.bind}:{port}", "-t", str(docroot), str(router)],
                stdout=fh, stderr=fh, env=env, start_new_session=True,
            )
        self._pid_file().write_text(str(proc.pid), encoding="utf-8")
        for _ in range(50):
            if not self._port_free(port):
                return
            time.sleep(0.1)

    def _stop_server(self) -> None:
        pid_file = self._pid_file()
        if not pid_file.exists():
            return
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            time.sleep(0.3)
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            pass
        finally:
            pid_file.unlink(missing_ok=True)

    def stop(self) -> None:
        self._stop_server()

    def _probe(self, url: str, auth: str = "") -> tuple[bool, str]:
        request = urllib.request.Request(url, headers={"User-Agent": "factory-health/1.0"})
        if auth:
            import base64
            request.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = response.read(2048)
                ok = response.status == 200 and b"<html" in body.lower()
                return ok, f"HTTP {response.status}, {len(body)} байт"
        except urllib.error.HTTPError as exc:
            return False, f"HTTP {exc.code}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return False, f"нет ответа: {exc}"

    def health(self) -> tuple[bool, str]:
        state = self._state()
        if not state.get("port"):
            return False, "цель ещё не разворачивалась"
        auth = self.staging_credentials() if self.environment != "production" else ""
        return self._probe(f"http://{self.bind}:{state['port']}/", auth)

    def rollback(self) -> DeployResult:
        state = self._state()
        previous = state.get("previous_release_id")
        current = self.current_release()
        if not previous or not (self.releases_dir / previous).exists():
            raise DeployFailed(
                "Предыдущий рабочий релиз отсутствует — откат невозможен.",
                field="rollback", required_input="Как минимум два релиза в releases/", blocks_stage="ROLLED_BACK",
            )
        if previous == current:
            # Переключение на самого себя выглядело бы успешным откатом, которого не было.
            raise DeployFailed(
                f"Точка отката совпадает с текущим релизом ({current}) — откатываться некуда.",
                field="rollback", required_input="Предыдущий отличный релиз в releases/",
                blocks_stage="ROLLED_BACK",
            )
        steps: list[dict] = []
        tmp = self.root / ".current.new"
        if tmp.exists() or tmp.is_symlink():
            tmp.unlink()
        tmp.symlink_to(self.releases_dir / previous)
        os.replace(tmp, self.current)
        steps.append({"id": "switch_current", "status": "ok", "started_at": now(), "finished_at": now(),
                      "exit_code": 0, "detail": f"current → releases/{previous}", "mutation": True})
        auth = self.staging_credentials() if self.environment != "production" else ""
        self._stop_server()                      # docroot остаётся симлинком current
        port = self._ensure_server(auth)
        ok, detail = self._probe(f"http://{self.bind}:{port}/", auth)
        steps.append({"id": "post_rollback_health", "status": "ok" if ok else "failed", "started_at": now(),
                      "finished_at": now(), "exit_code": 0 if ok else 1, "detail": detail, "mutation": False})
        if not ok:
            raise DeployFailed(f"Health после отката не пройден: {detail}", field="rollback", required_input="Рабочий предыдущий релиз", blocks_stage="ROLLED_BACK")
        self._save_state(build_id=previous, previous_release_id=current, rolled_back_at=now())
        return DeployResult(self.site_id, self.environment, previous, previous, current,
                            f"http://{self.bind}:{port}", steps=steps,
                            mutations=[{"target": str(self.root), "kind": "symlink", "detail": f"current → {previous}", "at": now()}])
