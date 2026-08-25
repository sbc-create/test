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

    def test_a_shell_body_is_judged_as_commands(self):
        """Тело, которое исполнит оболочка, разбирается наравне с командой."""
        command = "bash <<'SH'\nssh root@unknown.example uptime\nSH"
        assert unattended.evaluate(command).decision == unattended.PASS
        assert g.evaluate_bash(command).decision == g.DENY

    def test_a_shell_body_cannot_hide_a_stop_signal(self):
        command = "bash <<'SH'\ngit push --force origin claude/x\nSH"
        assert unattended.evaluate(command).decision == unattended.PASS
        assert "force push" in unattended.mandatory_confirmation(command)

    def test_a_script_body_is_ordinary_local_code(self):
        """`python - <<PY` — то же самое, что `python script.py`, и оно разрешено."""
        command = ".venv/bin/python - <<'PY'\nprint(len(open('README.md').read()))\nPY"
        assert unattended.evaluate(command).decision == unattended.ALLOW

    def test_a_script_body_touching_a_secret_is_still_denied(self):
        command = ".venv/bin/python - <<'PY'\nprint(open('.env').read())\nPY"
        assert g.evaluate_bash(command).decision == g.DENY


class TestStopSignalsStayInsideOneSegment:
    """Стоп-сигнал описывает форму одной команды, а не набор слов в строке.

    Разрыв `[^\\n]*` перескакивал через `;`, `&&` и `|`, поэтому глагол из
    одного сегмента склеивался со словом из другого. На запреты это не влияло,
    а безопасную работу останавливало: `rm -f var/tmp.diff && git checkout
    claude/unattended-safe-audit` читалось как удаление аудита, потому что имя
    ветки содержит «audit».
    """

    @pytest.mark.parametrize(
        "command",
        [
            # Имя ветки содержит «audit» — это не удаление журнала.
            "rm -f var/tmp.diff && git checkout claude/unattended-safe-audit",
            "git worktree remove var/check --force && git checkout claude/audit-branch",
            # Переключение на main после push в собственную ветку.
            "git push origin claude/example && git checkout main",
            "git push -u origin claude/example; git branch --show-current",
            # Чтение каталога бэкапов не является его удалением.
            "ls var/backups && npm run build",
            "find var/backups -name '*.tar.gz' | head -5",
            # Слово production в чужом сегменте не делает команду выкатом.
            "grep -rn production docs/ | head",
        ],
        ids=lambda c: c[:52],
    )
    def test_a_word_from_another_segment_does_not_stop_the_command(self, command):
        assert unattended.mandatory_confirmation(command) == "", command

    @pytest.mark.parametrize(
        "command",
        [
            "rm -rf var/backups",
            "rm var/audit/operator.jsonl",
            "git status && rm var/audit/operator.jsonl",
            "pytest -q; truncate -s 0 var/audit/operator.jsonl",
            "git push origin main",
            "git push --force origin claude/x",
            "sed -i 's/before_mutation: true/before_mutation: false/' sites/site-a/package.yaml",
            "python3 -m factory deploy --site site-a --environment production",
        ],
        ids=lambda c: c[:52],
    )
    def test_the_same_shape_inside_one_segment_still_stops(self, command):
        assert unattended.mandatory_confirmation(command), command



class TestLineContinuation:
    """Перенос строки, экранированный обратной косой чертой, — не разделитель.

    Оболочка стирает пару `\\` + перевод строки до разбора, поэтому продолжение
    строки принадлежит той же команде. Разбор, который этого не делал, видел
    второй «командой» её собственные аргументы (`-e s/…/`), не находил для них
    правила и снимал разрешение с обычной правки файла.
    """

    def test_continuation_is_one_segment(self):
        command = 'sed -i \\\n  -e "s#/old/#/new/#g" \\\n  -e "s#a#b#" sites/lords-01/package.yaml'
        assert len(unattended.segments(command)) == 1
        assert unattended.evaluate(command).decision == unattended.ALLOW

    def test_continuation_does_not_hide_a_second_command(self):
        """Настоящий разделитель после переноса остаётся разделителем."""
        command = "git status --short \\\n  && rm -rf /"
        assert len(unattended.segments(command)) == 2
        assert unattended.evaluate(command).decision != unattended.ALLOW

    def test_continuation_inside_quotes_is_left_alone(self):
        command = "printf 'one \\\ntwo'"
        assert "\\\n" in unattended.segments(command)[0]
