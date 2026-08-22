"""Heredoc handling in the guard.

The guard must judge instructions, not the data a command writes. Writing a
test that mentions a destructive statement is not the same as issuing one --
but feeding that same text to an interpreter is, and must stay blocked.
"""

from __future__ import annotations

from seo_operator.guardrails import ActionContext, Decision, classify, strip_data_heredocs

DESTRUCTIVE = "DR" "OP TABLE pages"  # split so this file is itself classifiable


def verdict(command: str) -> Decision:
    return classify(ActionContext(command=command)).decision


def test_data_heredoc_body_is_not_executed():
    command = f"cat > tests/x.py <<'PY'\nbad = \"{DESTRUCTIVE}\"\nPY\necho done"
    assert verdict(command) is Decision.ALLOW


def test_heredoc_into_interpreter_stays_classified():
    command = f"psql <<'SQL'\n{DESTRUCTIVE};\nSQL"
    assert verdict(command) is Decision.BLOCK


def test_heredoc_piped_into_shell_stays_classified():
    command = "cat <<'EOF' | bash\nrm -rf /srv/backups\nEOF"
    assert verdict(command) is Decision.BLOCK


def test_direct_command_still_blocked():
    assert verdict(f"psql -c '{DESTRUCTIVE}'") is Decision.BLOCK


def test_strip_removes_only_the_body():
    command = "cat > f.txt <<'EOF'\nsecret line\nEOF\nls -la"
    stripped = strip_data_heredocs(command)
    assert "secret line" not in stripped
    assert "ls -la" in stripped
    assert "cat > f.txt" in stripped


def test_unterminated_heredoc_does_not_swallow_the_rest():
    """A missing terminator must not hide a later command from the classifier."""
    command = "cat > f.txt <<'EOF'\nbody\n"
    stripped = strip_data_heredocs(command)
    assert "cat > f.txt" in stripped


def test_writing_documentation_that_quotes_dangerous_commands_is_allowed():
    command = (
        "cat > docs/policy.md <<'MD'\n"
        "Запрещено: rm -rf /, terraform destroy, git push --force\n"
        "MD"
    )
    assert verdict(command) is Decision.ALLOW


class TestCommitMessageSink:
    """A commit message is data. Naming a protected action in one is not
    performing it -- otherwise the operator cannot document its own guardrails."""

    def test_commit_message_naming_a_protected_action_is_allowed(self):
        command = (
            "git commit -q -F - <<'EOF'\n"
            "Add guardrails\n\n"
            "UNATTENDED_SAFE is achieved without bypassPermissions.\n"
            "EOF"
        )
        assert verdict(command) is Decision.ALLOW

    def test_commit_message_quoting_destructive_sql_is_allowed(self):
        command = f"git commit -F - <<'EOF'\nBlocks {DESTRUCTIVE} and friends\nEOF"
        assert verdict(command) is Decision.ALLOW

    def test_commit_piped_into_shell_is_not_a_sink(self):
        command = "git commit -F - <<'EOF' | bash\nrm -rf /srv/backups\nEOF"
        assert verdict(command) is Decision.BLOCK

    def test_plain_commit_without_file_flag_is_unaffected(self):
        assert verdict("git commit -m 'обычный коммит'") is Decision.ALLOW


class TestSinkAfterChain:
    """The sink is almost never at the start of the line."""

    def test_commit_sink_after_and_chain(self):
        command = (
            "./scripts/verify.sh && git add -A && git commit -F - <<'EOF'\n"
            "Message mentioning bypassPermissions and rm -rf /srv/backups\n"
            "EOF"
        )
        assert verdict(command) is Decision.ALLOW

    def test_cat_sink_after_and_chain(self):
        command = f"mkdir -p docs && cat > docs/x.md <<'MD'\n{DESTRUCTIVE}\nMD"
        assert verdict(command) is Decision.ALLOW

    def test_dangerous_command_in_the_chain_still_blocks(self):
        command = "rm -rf /srv/backups && git commit -F - <<'EOF'\n" "innocent message\n" "EOF"
        assert verdict(command) is Decision.BLOCK
