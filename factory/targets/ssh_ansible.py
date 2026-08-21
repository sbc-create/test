"""SSH-цель через декларативный Ansible-слой.

Claude никогда не выполняет произвольный ssh: этот адаптер вызывает проверенный
playbook с параметрами из manifest и inventory. Хост, пользователь, sudo-allowlist
и отпечаток host key берутся только из inventory/ssh-hosts.yaml.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from factory import blueprint, inventory
from factory.errors import BlockedAccess, BlockedInput, BlockedSecret, DeployFailed
from factory.paths import PATHS
from factory.redaction import redact
from factory.targets.base import DeployPlan, DeployResult, now

PLAYBOOKS = {
    "deploy": "deploy-site.yml",
    "rollback": "rollback-site.yml",
    "backup": "backup-site.yml",
}


class SshAnsibleTarget:
    adapter = "ssh_ansible"

    def __init__(self, conf: dict, package: dict) -> None:
        self.conf = conf
        self.pkg = package
        self.site_id = package["site_id"]
        self.environment = package["environment"]
        self.host = inventory.ssh_host(conf.get("ssh_host_ref") or package.get("ssh_host_ref") or "")
        self.playbook_dir = PATHS.automation / "ansible"

    # ------------------------------------------------------------------ проверки
    def _require_ansible(self) -> str:
        binary = shutil.which("ansible-playbook")
        if not binary:
            raise BlockedAccess(
                "ansible-playbook не установлен на управляющем хосте.",
                field="control_host.toolchain",
                required_input="Установи Ansible на машину, с которой запускается фабрика",
                blocks_stage="STAGING_DEPLOY",
            )
        return binary

    def _require_known_hosts(self) -> Path:
        ref = self.host.get("known_hosts_entry_ref")
        path = PATHS.root / ref if ref else None
        if not path or not path.exists():
            raise BlockedAccess(
                f"Отпечаток host key не найден: {ref}. Отключать strict host key checking запрещено.",
                field="inventory/ssh-hosts.yaml: known_hosts_entry_ref",
                required_input="Файл known_hosts с проверенным отпечатком целевого хоста",
                blocks_stage="STAGING_DEPLOY",
            )
        return path

    def _require_key(self) -> str:
        ref = self.host.get("ssh_key_secret_ref") or ""
        if ref.startswith("env:"):
            name = ref.split(":", 1)[1]
            if not os.environ.get(name):
                raise BlockedSecret(
                    f"Переменная {name} с приватным ключом деплоя не задана.",
                    field="inventory/ssh-hosts.yaml: ssh_key_secret_ref",
                    required_input=f"Экспортируй {name} перед запуском; значение в git и логи не попадает",
                    blocks_stage="STAGING_DEPLOY",
                )
            return name
        if ref.startswith("file:"):
            path = Path(ref.split(":", 1)[1]).expanduser()
            if not path.exists():
                raise BlockedSecret(f"Файл ключа {path} не найден.", field="ssh_key_secret_ref",
                                    required_input="Путь к приватному ключу деплоя", blocks_stage="STAGING_DEPLOY")
            return str(path)
        raise BlockedSecret(
            "ssh_key_secret_ref не задан или имеет неизвестную схему.",
            field="inventory/ssh-hosts.yaml: ssh_key_secret_ref",
            required_input="env:NAME или file:/path", blocks_stage="STAGING_DEPLOY",
        )

    def base_url(self) -> str:
        scheme = "https"
        return f"{scheme}://{self.pkg['domain']}"

    def releases(self) -> list[str]:
        return []

    def staging_credentials(self) -> str:
        ref = f"env:FACTORY_STAGING_AUTH_{self.site_id.upper().replace('-', '_')}"
        name = ref.split(":", 1)[1]
        value = os.environ.get(name, "")
        if not value and self.environment != "production":
            raise BlockedSecret(
                f"Учётные данные staging не заданы ({ref}).",
                field="staging_auth", required_input=f"Экспортируй {name} в формате user:password",
                blocks_stage="STAGING_DEPLOY",
            )
        return value

    # ------------------------------------------------------------------ контракт
    #: sudo-команды исполняются на целевом хосте с повышенными правами, поэтому
    #: принимаются только абсолютные пути к системным бинарям с безопасными аргументами.
    SUDO_ALLOWED_RE = re.compile(
        r"^(?:/usr/sbin/nginx -t|/usr/sbin/apache2ctl configtest|"
        r"/bin/systemctl reload [a-z0-9@._-]+|/usr/bin/systemctl reload [a-z0-9@._-]+|"
        r"/bin/systemctl (?:status|is-active) [a-z0-9@._-]+|/usr/bin/systemctl (?:status|is-active) [a-z0-9@._-]+)$"
    )

    def _validate_sudo_allowlist(self) -> list[str]:
        entries = self.host.get("sudo_allowlist") or []
        for entry in entries:
            if not self.SUDO_ALLOWED_RE.match(str(entry).strip()):
                raise BlockedAccess(
                    f"Команда sudo_allowlist «{entry}» не входит в утверждённый набор: "
                    "разрешены только config-test и reload конкретного сервиса по абсолютному пути.",
                    field="inventory/ssh-hosts.yaml: sudo_allowlist",
                    required_input="Например: /usr/sbin/nginx -t, /bin/systemctl reload nginx",
                    blocks_stage="STAGING_DEPLOY",
                )
        return entries

    def _extra_vars(self, build_id: str, build_dir: Path) -> dict:
        # Всё, что описывает структуру DLE и хоста, берётся из профиля blueprint.
        # Пустые значения по умолчанию раньше приводили к тому, что установщик не
        # удалялся, cron не ставился, а deny-правила веб-сервера не создавались — молча.
        profile = blueprint.require_ready("dle20")
        layout = profile.get("layout") or {}
        required = {
            "installer_entrypoints": profile.get("installer_entrypoints"),
            "public_deny_paths": profile.get("public_deny_paths"),
            "shared_paths": profile.get("shared_paths"),
            "writable_mode": (profile.get("permissions") or {}).get("writable_mode"),
            "site_root_template": layout.get("site_root_template"),
            "backup_root_template": layout.get("backup_root_template"),
            "webserver_config_dir": layout.get("webserver_config_dir"),
            "fpm_socket_template": layout.get("fpm_socket_template"),
            "content_security_policy": (profile.get("webserver") or {}).get("content_security_policy"),
            "fastcgi_include": (profile.get("webserver") or {}).get("fastcgi_include"),
        }
        missing = sorted(key for key, value in required.items() if not value)
        if missing:
            raise BlockedInput(
                f"В профиле blueprint не заполнено: {', '.join(missing)}.",
                field="blueprints/dle20/profiles/paths.yaml",
                required_input="Значения из официальной документации DLE 20.0 и регламента хостинга",
                blocks_stage="STAGING_DEPLOY",
            )
        return {
            "site_id": self.site_id,
            "environment": self.environment,
            "domain": self.pkg["domain"],
            "aliases": self.pkg.get("aliases") or [],
            "build_id": build_id,
            "build_dir": str(build_dir),
            "keep_releases": self.pkg["rollback_policy"]["keep_releases"],
            "deploy_user": self.host["deploy_user"],
            "sudo_allowlist": self._validate_sudo_allowlist(),
            "php_version": self.pkg["runtime"]["php"]["version"],
            "database_engine": self.pkg["runtime"]["database"]["engine"],
            "installer_entrypoints": required["installer_entrypoints"],
            "public_deny_paths": required["public_deny_paths"],
            "shared_link_paths": required["shared_paths"],
            "writable_mode": required["writable_mode"],
            "cron_jobs": blueprint.cron_jobs("dle20"),
            "site_root": str(required["site_root_template"]).format(site_id=self.site_id, environment=self.environment),
            "backup_root": str(required["backup_root_template"]).format(site_id=self.site_id, environment=self.environment),
            "webserver_config_dir": required["webserver_config_dir"],
            "fpm_socket": str(required["fpm_socket_template"]).format(
                site_id=self.site_id, php_version=self.pkg["runtime"]["php"]["version"]),
            "content_security_policy": required["content_security_policy"],
            "fastcgi_include": required["fastcgi_include"],
        }

    def preflight(self) -> None:
        """Всё, что должно упасть ДО мутации, падает здесь."""
        self._require_ansible()
        self._require_known_hosts()
        self._require_key()
        self._validate_sudo_allowlist()

    def plan(self, build_dir: Path, build_id: str) -> DeployPlan:
        steps = [
            {"id": "preflight", "detail": "проверка ansible, known_hosts, ключа и allowlist целей", "mutation": False},
            {"id": "backup", "detail": "backup БД и mutable data на целевом хосте", "mutation": True},
            {"id": "upload_release", "detail": f"releases/{build_id}", "mutation": True},
            {"id": "link_shared", "detail": "симлинки shared → релиз", "mutation": True},
            {"id": "config_test", "detail": "nginx -t / php-fpm config test (из sudo_allowlist)", "mutation": False},
            {"id": "health_check", "detail": "health релиза до переключения", "mutation": False},
            {"id": "switch_current", "detail": "атомарное переключение current", "mutation": True},
            {"id": "reload_services", "detail": "reload сервисов из sudo_allowlist", "mutation": True},
            {"id": "post_switch_health", "detail": "health после переключения", "mutation": False},
            {"id": "prune_releases", "detail": "удаление устаревших релизов", "mutation": True},
        ]
        return DeployPlan(self.site_id, self.environment, build_id, self.conf.get("ref", "ssh"), steps)

    def _run_playbook(self, name: str, extra_vars: dict, *, check_mode: bool = False) -> subprocess.CompletedProcess:
        binary = self._require_ansible()
        known_hosts = self._require_known_hosts()
        self._require_key()
        playbook = self.playbook_dir / PLAYBOOKS[name]
        if not playbook.exists():
            raise BlockedAccess(f"Playbook {playbook} не найден.", field="automation/ansible",
                                required_input="Playbook в automation/ansible/", blocks_stage="STAGING_DEPLOY")
        cmd = [
            binary, str(playbook),
            "-i", str(self.playbook_dir / "inventory" / "hosts.yml"),
            "--limit", self.host["ref"],
            "--extra-vars", json.dumps(extra_vars, ensure_ascii=False),
        ]
        if check_mode:
            cmd.append("--check")
        env = dict(os.environ)
        env["ANSIBLE_HOST_KEY_CHECKING"] = "True"          # отключать запрещено
        env["ANSIBLE_SSH_ARGS"] = f"-o UserKnownHostsFile={known_hosts} -o StrictHostKeyChecking=yes"
        return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=1800, check=False)

    def backup(self) -> dict:
        self.preflight()
        proc = self._run_playbook("backup", {"site_id": self.site_id, "environment": self.environment})
        if proc.returncode != 0:
            raise DeployFailed(f"Backup не выполнен: {redact(proc.stderr)[:400]}", field="backup",
                               required_input="Работоспособный доступ к целевому хосту", blocks_stage="STAGING_DEPLOY")
        return {"taken": True, "ref": f"remote:{self.site_id}/{self.environment}", "restore_verified": False, "verified_at": None}

    def deploy(self, build_dir: Path, build_id: str, *, dry_run: bool = False) -> DeployResult:
        extra = self._extra_vars(build_id, build_dir)
        # Бэкап до мутации — инвариант контракта целей, а не опция конкретного адаптера.
        backup = None if dry_run else self.backup()
        proc = self._run_playbook("deploy", extra, check_mode=dry_run)
        steps = [{"id": "ansible", "status": "ok" if proc.returncode == 0 else "failed",
                  "started_at": now(), "finished_at": now(), "exit_code": proc.returncode,
                  "detail": redact(proc.stdout)[-2000:], "mutation": not dry_run}]
        if proc.returncode != 0:
            raise DeployFailed(f"Playbook deploy завершился с кодом {proc.returncode}: {redact(proc.stderr)[:400]}",
                               field="deploy", required_input="Исправление ошибки playbook или доступа",
                               blocks_stage="PRODUCTION_DEPLOY" if self.environment == "production" else "STAGING_DEPLOY")
        return DeployResult(self.site_id, self.environment, build_id, build_id, None, self.base_url(),
                            steps=steps, backup=backup,
                            mutations=[] if dry_run else [{"target": self.host["hostname"], "kind": "filesystem",
                                                           "detail": f"release {build_id}", "at": now()}])

    def restore(self, archive_ref: str, destination: Path) -> bool:
        """Проверка восстановимости на целевом хосте через playbook backup-site.

        Возвращает результат фактической проверки; заглушки «всё хорошо» здесь нет.
        """
        proc = self._run_playbook("backup", {"site_id": self.site_id, "environment": self.environment,
                                             "verify_restore": True, "archive_ref": archive_ref,
                                             "restore_destination": str(destination)})
        return proc.returncode == 0

    def health(self) -> tuple[bool, str]:
        """Реальный HTTP-опрос health-endpoint целевого сайта."""
        import urllib.error
        import urllib.request

        endpoint = self.pkg["monitoring_policy"]["health_endpoint"]
        url = f"{self.base_url()}{endpoint}"
        request = urllib.request.Request(url, headers={"User-Agent": "factory-health/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.status == 200, f"HTTP {response.status} на {url}"
        except urllib.error.HTTPError as exc:
            return False, f"HTTP {exc.code} на {url}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return False, f"нет ответа от {url}: {exc}"

    def rollback(self) -> DeployResult:
        proc = self._run_playbook("rollback", {"site_id": self.site_id, "environment": self.environment})
        if proc.returncode != 0:
            raise DeployFailed(f"Rollback не выполнен: {redact(proc.stderr)[:400]}", field="rollback",
                               required_input="Наличие предыдущего релиза на хосте", blocks_stage="ROLLED_BACK")
        return DeployResult(self.site_id, self.environment, "", "previous", None, self.base_url(),
                            steps=[{"id": "ansible-rollback", "status": "ok", "started_at": now(),
                                    "finished_at": now(), "exit_code": 0, "detail": redact(proc.stdout)[-1000:], "mutation": True}],
                            mutations=[{"target": self.host["hostname"], "kind": "symlink", "detail": "current → previous", "at": now()}])
