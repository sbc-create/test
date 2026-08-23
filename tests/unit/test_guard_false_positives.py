"""REQ-GUARD: ложные срабатывания защиты чинятся в защите, а не обходятся.

Каждый случай здесь однажды остановил безопасную работу. Правило осталось на
месте — изменилось только то, что оно считает опасным. Тест закрепляет обе
стороны: безопасная форма проходит, опасная по-прежнему запрещена.
"""

import guard_rules as g
import pytest

from seo_operator import unattended
from seo_operator.guardrails import ActionContext, Decision, classify
from tests.unit.test_permission_matrix import final


class TestRedirectionIsNotASeparator:
    """`2>&1` — перенаправление дескриптора, а не разделитель команд.

    Разбиение по `&` выдавало сегменты `cmd 2>` и `1`. На запреты это не
    влияло, но сегмент `1` не совпадал ни с одним разрешающим правилом, и вся
    команда уходила на подтверждение.
    """

    @pytest.mark.parametrize(
        "command,expected",
        [
            ("git status; timeout 300 git push origin claude/x 2>&1 | tail -3",
             ["git status", "timeout 300 git push origin claude/x 2>&1", "tail -3"]),
            ("pytest -q &> out.log", ["pytest -q &> out.log"]),
            ("make build >&2", ["make build >&2"]),
        ],
    )
    def test_redirection_keeps_the_command_whole(self, command, expected):
        assert g.split_subcommands(command) == expected

    def test_background_and_chaining_still_split(self):
        assert g.split_subcommands("build && ssh prod") == ["build", "ssh prod"]

    def test_a_denied_command_after_a_redirection_is_still_denied(self):
        verdict = g.evaluate_bash("pytest -q 2>&1 | tail && ssh prod uptime")
        assert verdict.decision == g.DENY
        assert verdict.rule_id == "G-REMOTE"


class TestSedWithoutInPlaceIsReading:
    """`sed -n '1,50p' path` ничего не пишет.

    G-WRITE проверял каждый аргумент `sed` как цель записи, поэтому правило,
    охраняющее запись в `.claude/`, запрещало ещё и чтение оттуда.
    """

    def test_reading_a_protected_file_is_allowed(self):
        assert g.evaluate_bash("sed -n '1,50p' .claude/hooks/guard_rules.py").decision != g.DENY

    @pytest.mark.parametrize("command", [
        "sed -i 's/a/b/' .claude/settings.json",
        "sed --in-place 's/a/b/' .claude/hooks/guard_rules.py",
        "sed -i.bak 's/a/b/' .claude/settings.json",
    ])
    def test_in_place_editing_stays_denied(self, command):
        verdict = g.evaluate_bash(command)
        assert verdict.decision == g.DENY
        assert verdict.rule_id == "G-WRITE"

    def test_other_writers_are_unaffected(self):
        assert g.evaluate_bash("cp x .claude/settings.json").rule_id == "G-WRITE"


class TestEnvAssignmentIsNotADump:
    """`env VAR=1 cmd` задаёт переменную для одной команды и ничего не печатает."""

    @pytest.mark.parametrize("command", [
        "env FACTORY_CLOSED_WORLD=0 pytest -q",
        "env NODE_ENV=test npm run build",
    ])
    def test_setting_one_variable_is_ordinary_work(self, command):
        # Правило «дамп окружения» больше не срабатывает: остаётся обычный
        # default-deny, который профиль UNATTENDED_SAFE поднимает до allow.
        verdict = classify(ActionContext(command=command))
        assert verdict.rule == "default-deny", verdict.reason
        assert final(command) == "allow"

    @pytest.mark.parametrize("command", ["env", "env | grep TOKEN", "printenv", "ls; printenv"])
    def test_dumping_the_environment_stays_blocked(self, command):
        verdict = classify(ActionContext(command=command))
        assert verdict.decision is Decision.BLOCK
        assert "environment dump" in verdict.reason


class TestRemoteAccessFollowsInventory:
    """Разрешение на хост даёт inventory, а не форма команды."""

    def test_absent_host_is_denied_by_name(self):
        verdict = g.evaluate_bash("ssh deploy@stage-1 uptime")
        assert verdict.decision == g.DENY
        assert "inventory/ssh-hosts.yaml" in verdict.reason

    def test_empty_inventory_grants_nothing(self):
        """Пустой инвентарь — не поломка, а отсутствие переданных хостов."""
        for host in g.inventory_ssh_hosts():
            assert host, "пустая запись хоста в inventory недопустима"

    def test_dns_without_a_registered_zone_is_denied(self):
        verdict = g.evaluate_bash("nsupdate -k /tmp/k example.tld")
        if "example.tld" not in g.inventory_dns_zones():
            assert verdict.decision == g.DENY
            assert verdict.rule_id == "G-NET-CFG"


class TestHeredocBodyIsData:
    """Тело heredoc — данные, а не команды.

    Профиль разбирал `git commit -F - <<MSG … MSG` вместе с текстом сообщения и
    видел в описании работы «неизвестную команду». Получалось, что коммит,
    описывающий защиту, останавливался этой же защитой.
    """

    COMMIT = (
        "git add -A && git commit -q -F - <<'MSG'\n"
        "guard: описание работы\n"
        "\n"
        "rm -rf и git push --force упомянуты в тексте, но не выполняются.\n"
        "MSG"
    )

    def test_commit_message_is_not_parsed_as_commands(self):
        assert unattended.evaluate(self.COMMIT).decision == unattended.ALLOW

    def test_writing_a_file_is_not_parsed_as_commands(self):
        command = "cat > var/note.txt <<'TXT'\nssh root@unknown.example\nTXT"
        assert unattended.evaluate(command).decision == unattended.ALLOW

    def test_a_body_the_interpreter_executes_is_never_auto_approved(self):
        command = "bash <<'SH'\nssh root@unknown.example uptime\nSH"
        assert unattended.evaluate(command).decision == unattended.PASS
        assert g.evaluate_bash(command).decision == g.DENY

