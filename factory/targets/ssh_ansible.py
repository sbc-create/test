"""SSH-цель через декларативный Ansible-слой.

Claude никогда не выполняет произвольный ssh: этот адаптер вызывает проверенный
playbook с параметрами из manifest и inventory. Хост, пользователь, sudo-allowlist
и отпечаток host key берутся только из inventory/ssh-hosts.yaml.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from factory import inventory
from factory.errors import BlockedAccess, BlockedSecret, DeployFailed
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
    def _extra_vars(self, build_id: str, build_dir: Path) -> dict:
        return {
            "site_id": self.site_id,
            "environment": self.environment,
            "domain": self.pkg["domain"],
            "aliases": self.pkg.get("aliases") or [],
            "build_id": build_id,
            "build_dir": str(build_dir),
            "keep_releases": self.pkg["rollback_policy"]["keep_releases"],
            "deploy_user": self.host["deploy_user"],
            "sudo_allowlist": self.host.get("sudo_allowlist") or [],
            "php_version": self.pkg["runtime"]["php"]["version"],
            "database_engine": self.pkg["runtime"]["database"]["engine"],
            "public_deny_paths": [],
        }

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
        proc = self._run_playbook("backup", {"site_id": self.site_id, "environment": self.environment})
        if proc.returncode != 0:
            raise DeployFailed(f"Backup не выполнен: {redact(proc.stderr)[:400]}", field="backup",
                               required_input="Работоспособный доступ к целевому хосту", blocks_stage="STAGING_DEPLOY")
        return {"taken": True, "ref": f"remote:{self.site_id}/{self.environment}", "restore_verified": False, "verified_at": None}

    def deploy(self, build_dir: Path, build_id: str, *, dry_run: bool = False) -> DeployResult:
        extra = self._extra_vars(build_id, build_dir)
        proc = self._run_playbook("deploy", extra, check_mode=dry_run)
        steps = [{"id": "ansible", "status": "ok" if proc.returncode == 0 else "failed",
                  "started_at": now(), "finished_at": now(), "exit_code": proc.returncode,
                  "detail": redact(proc.stdout)[-2000:], "mutation": not dry_run}]
        if proc.returncode != 0:
            raise DeployFailed(f"Playbook deploy завершился с кодом {proc.returncode}: {redact(proc.stderr)[:400]}",
                               field="deploy", required_input="Исправление ошибки playbook или доступа",
                               blocks_stage="PRODUCTION_DEPLOY" if self.environment == "production" else "STAGING_DEPLOY")
        return DeployResult(self.site_id, self.environment, build_id, build_id, None, self.base_url(),
                            steps=steps, mutations=[] if dry_run else [{"target": self.host["hostname"], "kind": "filesystem",
                                                                        "detail": f"release {build_id}", "at": now()}])

    def health(self) -> tuple[bool, str]:
        endpoint = self.pkg["monitoring_policy"]["health_endpoint"]
        return False, (f"Health-проверка {self.base_url()}{endpoint} требует доступа к целевому хосту; "
                       "в этой среде цель не сконфигурирована.")

    def rollback(self) -> DeployResult:
        proc = self._run_playbook("rollback", {"site_id": self.site_id, "environment": self.environment})
        if proc.returncode != 0:
            raise DeployFailed(f"Rollback не выполнен: {redact(proc.stderr)[:400]}", field="rollback",
                               required_input="Наличие предыдущего релиза на хосте", blocks_stage="ROLLED_BACK")
        return DeployResult(self.site_id, self.environment, "", "previous", None, self.base_url(),
                            steps=[{"id": "ansible-rollback", "status": "ok", "started_at": now(),
                                    "finished_at": now(), "exit_code": 0, "detail": redact(proc.stdout)[-1000:], "mutation": True}],
                            mutations=[{"target": self.host["hostname"], "kind": "symlink", "detail": "current → previous", "at": now()}])
