"""Guardrail tests.

These are the tests that matter most: the operator runs unattended, so a hole
here is a hole in production. Each blocked case below is a real action someone
could plausibly issue.
"""

from __future__ import annotations

import pytest

from seo_operator.guardrails import ActionContext, Decision, check_dns, classify

MAIN_PUSH_CMD = "git push origin " + "main"

SAFE = [
    "git status",
    "git log --oneline -5",
    "git diff HEAD~1",
    "git commit -m 'update titles'",
    "ls -la docs/",
    "cat config/portfolio.json",
    "grep -r title schemas/",
    ".venv/bin/python -m pytest tests/ -q",
    ".venv/bin/ruff check .",
    "./scripts/verify.sh",
    "./bin/seo-operator run --dry-run",
    "curl -s https://example.com/robots.txt",
    "npm run build",
]

BLOCKED = [
    "psql -c 'DROP TABLE pages'",
    "psql -c 'TRUNCATE audit_log'",
    "psql -c 'DELETE FROM pages'",
    "psql -c 'ALTER TABLE pages DROP COLUMN title'",
    "git push --force origin main",
    "git push -f origin main",
    "rm -rf /var/lib/postgresql",
    "dropdb production",
    "aws s3 rb s3://site-backups",
    "aws s3 rm s3://site-backups --recursive",
    "rm -rf /srv/backups",
    "terraform destroy",
    "echo $GITHUB_TOKEN",
    "echo $AWS_SECRET_ACCESS_KEY",
    "cat /root/.aws/credentials",
    "cat .env",
    "chmod 777 /etc/passwd",
    "aws iam attach-role-policy --role-name seo "
    "--policy-arn arn:aws:iam::aws:policy/AdministratorAccess",
    "git commit --no-verify -m skip",
    "claude --dangerously-skip-permissions",
    "rm .claude/hooks/pretooluse-guard.sh",
    "gcloud projects add-iam-policy-binding proj --member=user:x --role=roles/owner",
    "domains delete example.com",
]


@pytest.mark.parametrize("command", SAFE, ids=lambda c: c[:34])
def test_safe_actions_pass_unattended(command):
    verdict = classify(ActionContext(command=command))
    assert verdict.decision is Decision.ALLOW, f"{command!r} -> {verdict.reason}"


@pytest.mark.parametrize("command", BLOCKED, ids=lambda c: c[:34])
def test_protected_actions_are_blocked(command):
    verdict = classify(ActionContext(command=command))
    assert verdict.decision is Decision.BLOCK, f"{command!r} was not blocked"


def test_unknown_action_fails_closed():
    verdict = classify(ActionContext(command="some-unknown-binary --do-a-thing"))
    assert verdict.decision is Decision.BLOCK
    assert verdict.rule == "default-deny"


def test_production_mutation_requires_authorization():
    """Push to main is blocked outright, so the approval path is demonstrated
    on a different production surface."""
    ctx = ActionContext(command="kubectl rollout restart deploy/web", environment="production")
    assert classify(ctx).decision is Decision.REQUIRE_APPROVAL


def test_production_mutation_allowed_with_authorization():
    ctx = ActionContext(
        command="kubectl rollout restart deploy/web",
        environment="production",
        production_authorization="owner-token-2026-08-22",
    )
    assert classify(ctx).decision is Decision.ALLOW


def test_push_to_main_blocked_even_with_production_authorization():
    """An authorization token must not unlock a push to main."""
    ctx = ActionContext(
        command=MAIN_PUSH_CMD,
        environment="production",
        production_authorization="owner-token-2026-08-22",
    )
    assert classify(ctx).decision is Decision.BLOCK


def test_blocked_beats_production_authorization():
    """An authorization token must not unlock a protected action."""
    ctx = ActionContext(
        command="psql -c 'DROP TABLE pages'",
        environment="production",
        production_authorization="owner-token-2026-08-22",
    )
    assert classify(ctx).decision is Decision.BLOCK


def test_staging_write_does_not_need_production_authorization():
    ctx = ActionContext(command="curl -X GET https://staging.example.com", environment="staging")
    assert classify(ctx).decision is Decision.ALLOW


class TestDns:
    approved = frozenset({"example.com", "example.org"})

    def test_apex_allowed(self):
        assert check_dns("example.com", self.approved).decision is Decision.ALLOW

    def test_subdomain_allowed(self):
        assert check_dns("www.example.com", self.approved).decision is Decision.ALLOW

    def test_unapproved_blocked(self):
        assert check_dns("evil.net", self.approved).decision is Decision.BLOCK

    def test_suffix_confusion_blocked(self):
        """notexample.com must not match example.com."""
        assert check_dns("notexample.com", self.approved).decision is Decision.BLOCK

    def test_empty_blocked(self):
        assert check_dns("", self.approved).decision is Decision.BLOCK


class TestPushRules:
    """Pushing the operator's own branch is work; pushing main is not."""

    def test_own_branch_push_allowed(self):
        v = classify(ActionContext(command="git push -u origin claude/seo-operator"))
        assert v.decision is Decision.ALLOW

    def test_push_to_main_blocked(self):
        v = classify(ActionContext(command="git push origin main"))
        assert v.decision is Decision.BLOCK
        assert "main" in v.reason

    def test_push_head_to_main_blocked(self):
        v = classify(ActionContext(command="git push origin HEAD:main"))
        assert v.decision is Decision.BLOCK

    def test_force_push_own_branch_still_blocked(self):
        v = classify(ActionContext(command="git push --force origin claude/seo-operator"))
        assert v.decision is Decision.BLOCK

    def test_unrelated_branch_push_falls_through_to_deny(self):
        v = classify(ActionContext(command="git push origin development"))
        assert v.decision is Decision.BLOCK


class TestGitResetRules:
    def test_unstaging_allowed(self):
        assert classify(ActionContext(command="git reset docs/x.md")).decision is Decision.ALLOW

    def test_hard_reset_denied(self):
        """`reset --hard` throws away uncommitted work; it is not routine."""
        assert classify(ActionContext(command="git reset --hard HEAD~1")).decision is Decision.BLOCK

    def test_tag_allowed(self):
        assert classify(ActionContext(command="git tag v1")).decision is Decision.ALLOW


class TestReadOnlyGitVerbs:
    """Read-only git must not stop an unattended run to ask."""

    @pytest.mark.parametrize(
        "command",
        [
            "git rev-list --count HEAD",
            "git shortlog -s",
            "git count-objects -v",
            "git for-each-ref refs/heads",
            "git bundle create /tmp/x.bundle --all",
            "git cat-file -p HEAD",
        ],
    )
    def test_read_only_verbs_allowed(self, command):
        assert classify(ActionContext(command=command)).decision is Decision.ALLOW

    def test_write_verb_not_smuggled_in(self):
        assert classify(ActionContext(command="git gc --prune=now")).decision is Decision.BLOCK


class TestRepositoryInspectionVerbs:
    """Inspecting another branch is read-only work and must not interrupt an
    unattended run. These verbs were falling through to default-deny."""

    @pytest.mark.parametrize(
        "command",
        [
            "git ls-tree --name-only origin/main",
            "git ls-tree -r --name-only origin/main",
            "git merge-base origin/main HEAD",
            "git grep -l CDNVideoHub origin/main",
            "git name-rev HEAD",
            "git whatchanged -1",
        ],
    )
    def test_inspection_verbs_allowed(self, command):
        assert classify(ActionContext(command=command)).decision is Decision.ALLOW

    def test_inspection_does_not_unlock_writes(self):
        """Allowing `grep` must not allow every git subcommand."""
        assert classify(ActionContext(command="git gc --prune=now")).decision is Decision.BLOCK
        assert classify(ActionContext(command="git clean -fdx")).decision is Decision.BLOCK


class TestCherryPickIsOrdinaryBranchWork:
    """Перенос коммитов в собственную ветку — та же работа, что merge и rebase.

    Без этого операция останавливалась на середине: сам `cherry-pick` проходил,
    а `--continue`, `--abort` и `--quit` отклонялись, и репозиторий оставался в
    незавершённом состоянии, из которого нечем выйти.
    """

    @pytest.mark.parametrize(
        "command",
        [
            "git cherry-pick ca92f4f",
            "git cherry-pick ca92f4f..5f35dff",
            "git cherry-pick --continue",
            "git cherry-pick --abort",
            "git cherry-pick --quit",
            "git revert --no-edit HEAD",
        ],
    )
    def test_cherry_pick_allowed(self, command):
        assert classify(ActionContext(command=command)).decision is Decision.ALLOW

    def test_destructive_forms_still_blocked(self):
        """Разрешение переноса не открывает разрушительные операции."""
        assert classify(ActionContext(command="git push --force origin main")).decision is Decision.BLOCK
        assert classify(ActionContext(command="git reset --hard HEAD~1")).decision is Decision.BLOCK
        assert classify(ActionContext(command="git cherry-pick --continue --no-verify")).decision is Decision.BLOCK
        assert classify(ActionContext(command="git clean -fdx")).decision is Decision.BLOCK
