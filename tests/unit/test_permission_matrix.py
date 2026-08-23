"""REQ-UNATTENDED-SAFE: матрица разрешений профиля автономной работы.

Проверяется не наличие файла профиля, а его эффект на настоящей цепочке хуков:
команда прогоняется через оба PreToolUse-слоя ровно так, как их вызывает Claude
Code, и решения складываются по правилу «побеждает самое строгое».

Матрица держит два обещания одновременно:

* обычная разработка не останавливается — разрешённые операции получают
  ``allow`` и не спрашивают подтверждения;
* обязательные стоп-сигналы остаются на месте — запрещённые операции получают
  ``deny``, необратимые операции над production получают ``ask``.

Тест намеренно ходит через `decide()` хуков, а не через внутренние функции:
регрессия, при которой правило есть, а хук его не отдаёт, иначе не ловится.
"""

from __future__ import annotations

import importlib.util

import pytest

from factory.paths import PATHS
from seo_operator import hookguard, unattended

HOOKS = PATHS.root / ".claude" / "hooks"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"hook_{name}", HOOKS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard_bash = _load("guard_bash")
guard_write = _load("guard_write")

SEVERITY = {"allow": 0, "pass": 1, "ask": 2, "deny": 3}


def chain(command: str) -> str:
    """Итоговое решение обоих хуков: побеждает самое строгое."""
    factory_layer = guard_bash.decide(command)[0]
    operator_layer = hookguard.decide(
        {"tool_name": "Bash", "tool_input": {"command": command}}
    )["hookSpecificOutput"]["permissionDecision"]
    return max((factory_layer, operator_layer), key=lambda d: SEVERITY[d])


# --------------------------------------------------------------------------
# Разрешено без подтверждения
# --------------------------------------------------------------------------
AUTONOMOUS = [
    "git status",
    "git diff --stat",
    "git log --oneline -5",
    "git fetch origin main",
    "git add -A",
    "git commit -m 'работа профиля'",
    "git checkout -b claude/feature-x",
    "git push -u origin claude/unattended-safe",
    # Составная команда с обёрткой, перенаправлением и pipe — тот самый случай,
    # ради которого профиль разбирает команду, а не сравнивает подстроки.
    "git status; timeout 300 git push origin claude/unattended-safe 2>&1 | tail -3",
    "PYTHONPATH=/home/user/test .venv/bin/python -m pytest tests/unit -q",
    "env FACTORY_CLOSED_WORLD=0 python3 -m factory validate --site pilot-local",
    "python3 -m factory build --site pilot-local",
    "python3 -m factory deploy --site pilot-local --environment staging",
    "bash tests/run-all.sh",
    ".venv/bin/pytest tests/ -q 2>&1 | tail -20",
    ".venv/bin/ruff check seo_operator",
    "npm ci",
    "npm run build 2>&1 | tail -5",
    "npx playwright test --reporter=line",
    "pip3 install -r requirements.txt",
    "php -l blueprints/dle20/index.php",
    "docker compose -f automation/docker-compose.yml up -d",
    "mkdir -p var/tmp && touch var/tmp/probe",
    "sed -n '1,20p' factory/pipeline.py",
    "cp docs/README.md var/tmp/README.md",
    "curl http://127.0.0.1:8110/",
]


@pytest.mark.parametrize("command", AUTONOMOUS, ids=lambda c: c[:48])
def test_routine_work_runs_without_asking(command):
    assert chain(command) == "allow", f"обычная операция требует подтверждения: {command}"


# --------------------------------------------------------------------------
# Заблокировано всегда
# --------------------------------------------------------------------------
BLOCKED = [
    "git push --force origin claude/unattended-safe",
    "git push -f origin claude/unattended-safe",
    "git push origin main",
    "git push origin HEAD:main",
    "git branch -D claude/unattended-safe",
    "git reset --hard HEAD~1",
    "git clean -fdx",
    "git filter-branch --tree-filter true HEAD",
    "rm -rf /var/www",
    "rm -rf sites/site-d-series",
    "rm -rf var/backups",
    "dropdb factory_production",
    "psql -c 'DROP DATABASE factory'",
    "cat .env",
    "cat secrets/deploy.key",
    "echo $CDNVIDEOHUB_API_TOKEN",
    "printenv",
    "ssh root@203.0.113.10 uptime",
    "scp artifacts/site.tar.gz deploy@203.0.113.10:/var/www/",
    "rsync -a build/ deploy@unknown.example/",
    "terraform destroy -auto-approve",
    "aws s3 rb s3://factory-backups --force",
    "chmod 777 /var/www",
    "nsupdate -k /etc/dns.key",
    "aws route53domains register-domain --domain-name example.tld",
    "curl -X POST https://api.example.tld/v1/pay",
    "claude --dangerously-skip-permissions",
    "git commit --no-verify -m x",
]


@pytest.mark.parametrize("command", BLOCKED, ids=lambda c: c[:48])
def test_forbidden_operations_are_blocked(command):
    assert chain(command) == "deny", f"запрещённая операция не заблокирована: {command}"


# --------------------------------------------------------------------------
# Требует подтверждения человека
# --------------------------------------------------------------------------
NEEDS_CONFIRMATION = [
    "python3 -m factory deploy --site site-a --environment production",
    "python3 -m factory rollback --site site-a --environment production",
]


@pytest.mark.parametrize("command", NEEDS_CONFIRMATION, ids=lambda c: c[:48])
def test_production_operations_still_stop_for_a_human(command):
    assert chain(command) == "ask", f"необратимая операция прошла без подтверждения: {command}"


# --------------------------------------------------------------------------
# Свойства профиля, а не отдельные команды
# --------------------------------------------------------------------------
class TestProfileProperties:
    def test_profile_never_denies_on_its_own(self):
        """Профиль умеет только разрешать: запреты принадлежат другим слоям."""
        for command in AUTONOMOUS + BLOCKED + NEEDS_CONFIRMATION:
            assert unattended.evaluate(command).decision in (unattended.ALLOW, unattended.PASS)

    def test_one_unknown_segment_disqualifies_the_whole_command(self):
        """Безопасная команда не ручается за то, что к ней приписали."""
        assert unattended.evaluate("git status && /usr/local/bin/unknown-binary").decision == (
            unattended.PASS
        )

    def test_remote_access_follows_the_inventory_not_the_command(self):
        """Разрешение на хост даёт inventory. Пустой inventory — доступа нет."""
        assert unattended.inventory_hosts() == set() or unattended.inventory_hosts()
        for host in ("stage-1", "203.0.113.10"):
            if host not in unattended.inventory_hosts():
                assert unattended.evaluate(f"ssh {host} uptime").decision == unattended.PASS

    def test_dns_follows_the_zone_inventory(self):
        for zone in ("example.tld",):
            if zone not in unattended.inventory_zones():
                assert unattended.evaluate(f"nsupdate -d {zone}").decision == unattended.PASS

    def test_external_hosts_need_a_supplied_contract(self):
        """Пустой network-allowlist означает BLOCKED_INPUT, а не «разрешено всё»."""
        if not unattended.network_hosts():
            assert unattended.evaluate("curl https://api.example.tld/v1/titles").decision == (
                unattended.PASS
            )


class TestWritePaths:
    def test_repository_files_are_written_without_asking(self):
        for path in ("factory/pipeline.py", "sites/site-d-series/package.yaml", "docs/README.md"):
            assert guard_write.decide(str(PATHS.root / path))[0] == "allow", path

    def test_protected_paths_stay_denied(self):
        for path in (".claude/settings.json", ".claude/hooks/guard_rules.py", "secrets/x.yaml",
                     "inventory/ssh-hosts.yaml", "knowledge/KNOWLEDGE_FREEZE.yaml", "deploy.pem"):
            assert guard_write.decide(str(PATHS.root / path))[0] == "deny", path

    def test_paths_outside_the_repository_are_not_auto_allowed(self):
        for path in ("/etc/nginx/nginx.conf", "/var/www/html/index.php"):
            assert guard_write.decide(path)[0] != "allow", path
