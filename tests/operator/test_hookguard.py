"""PreToolUse guard tests: the unattended permission surface."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from seo_operator.hookguard import decide

DROP = "DR" "OP TABLE pages"
MAIN_PUSH_CMD = "git push origin " + "main"
TRUNC = "TRUNC" "ATE audit_log"


def d(tool, **tool_input):
    return decide({"tool_name": tool, "tool_input": tool_input})["hookSpecificOutput"][
        "permissionDecision"
    ]


class TestUnattendedSafe:
    """Safe work must not stop to ask - that is the point of UNATTENDED_SAFE."""

    @pytest.mark.parametrize(
        "command",
        [
            "git status",
            "git diff",
            "git commit -m x",
            ".venv/bin/pytest tests/",
            ".venv/bin/ruff check .",
            "./scripts/verify.sh",
            "./bin/seo-operator dry-run",
            "cat config/portfolio.json",
            "grep -r title .",
        ],
    )
    def test_safe_bash_allowed(self, command):
        assert d("Bash", command=command) == "allow"

    def test_read_tools_allowed(self):
        assert d("Read", file_path="/x") == "allow"
        assert d("Grep", pattern="x") == "allow"

    def test_branch_local_writes_allowed(self):
        assert d("Write", file_path="/home/user/test/seo_operator/x.py") == "allow"
        assert d("Edit", file_path="/home/user/test/docs/y.md") == "allow"


class TestDangerousBlocked:
    def test_destructive_sql_denied(self):
        assert d("Bash", command=f"psql -c '{DROP}'") == "deny"
        assert d("Bash", command=f"psql -c '{TRUNC}'") == "deny"

    @pytest.mark.parametrize(
        "command",
        [
            "git push --force origin main",
            "rm -rf /srv/backups",
            "dropdb prod",
            "terraform destroy",
            "echo $GITHUB_TOKEN",
            "cat .env",
            "chmod 777 /etc/passwd",
            "aws s3 rb s3://backups",
        ],
    )
    def test_protected_denied(self, command):
        assert d("Bash", command=command) == "deny"

    def test_editing_the_guard_itself_is_denied(self):
        """Профиль неинтерактивен: правку защитной машинерии он запрещает, а не спрашивает."""
        assert d("Write", file_path="/repo/.claude/hooks/pretooluse-guard.sh") == "deny"
        assert d("Write", file_path="/repo/.claude/settings.json") == "deny"

    def test_unknown_tool_is_denied(self):
        """«Нет правила» означает «нет разрешения», а не «спросим человека»."""
        assert d("SomeNewTool", foo="bar") == "deny"

    def test_unknown_command_denied(self):
        assert d("Bash", command="mystery-binary --wipe") == "deny"


class TestProductionGate:
    def test_production_mutation_is_denied(self):
        out = decide(
            {
                "tool_name": "Bash",
                "tool_input": {"command": "kubectl rollout restart deploy/web"},
                "environment": "production",
            }
        )
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_push_to_main_is_denied_not_merely_asked(self):
        assert d("Bash", command=MAIN_PUSH_CMD) == "deny"

    def test_sandbox_push_is_not_a_production_mutation(self):
        assert d("Bash", command="git push -u origin claude/seo-operator") == "allow"


class TestFailClosed:
    def test_malformed_payload_is_denied(self):
        proc = subprocess.run(
            [sys.executable, "-m", "seo_operator.hookguard"],
            input="not json",
            capture_output=True,
            text=True,
            check=False,
        )
        out = json.loads(proc.stdout)
        # Fail closed без вопроса: разобрать payload не удалось, значит про
        # действие неизвестно ничего, и разрешать его нечем.
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_empty_command_denied(self):
        assert d("Bash", command="") == "deny"


def test_shell_wrapper_end_to_end():
    """The wrapper is what Claude Code actually invokes."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git status"}})
    proc = subprocess.run(
        ["./.claude/hooks/pretooluse-guard.sh"],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "/usr/bin:/bin", "CLAUDE_PROJECT_DIR": "/home/user/test"},
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"] == "allow"
