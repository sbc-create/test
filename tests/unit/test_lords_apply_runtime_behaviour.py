"""REQ-LORDS-STAGING: опасные участки root-сценария проверяются исполнением.

Два отказа подряд дожили до root-запуска, потому что проверялся текст сценария,
а не его поведение:

1. `tr -dc ... </dev/urandom | head -c 32` — /dev/urandom бесконечен, `head`
   забирал 32 байта и закрывал канал, `tr` получал SIGPIPE и завершался кодом
   141, а `pipefail` объявлял отказом весь конвейер. Пароль создавался верно —
   падала проверка статуса.
2. Ловушка ERR наследуется функциями из-за `set -E`, поэтому неудачная команда
   внутри самого отката снова входила в обработчик: сообщение печаталось
   дважды, а откат обрывался на середине, не вернув юниты на место.

Ни `bash -n`, ни shellcheck, ни чтение текста этого не показывают. Поэтому здесь
исполняются настоящие функции сценария — его же заголовок подключается через
`source`, а команды, меняющие систему, подменяются заглушками, которые только
записывают, что было бы сделано.
"""

from __future__ import annotations

import os
import re
import subprocess

import pytest

from factory.paths import PATHS

SCRIPT = PATHS.root / "automation/host/lords-staging-apply.sh"
BASH = "/bin/bash"

# Метка-канарейка для проверок утечки. Это не пароль и не секрет: она передаётся
# через окружение и нужна ровно для того, чтобы убедиться, что подобное значение
# в отчёт об отказе не попадает.
CANARY = "canary-must-not-surface"

# Заголовок сценария: всё до проверки root. Там объявлены log/warn/die, STAGE,
# rollback, on_error и сама ловушка — то, что проверяется ниже.
HEADER_END = "[[ ${EUID} -eq 0 ]] || die"


def header() -> str:
    text = SCRIPT.read_text(encoding="utf-8")
    cut = text.index(HEADER_END)
    return text[:cut]


def run_bash(script: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        [BASH, "-c", script], capture_output=True, text=True, timeout=120, **kwargs
    )


# ---------------------------------------------------------------------------
# Причина отказа: SIGPIPE в конвейере под pipefail
# ---------------------------------------------------------------------------
class TestNoSigpipePipelines:
    """Наследие дефекта с генерацией пароля.

    Сам участок исчез вместе с Basic Auth — пароль больше не создаётся. Но
    урок остаётся применимым к любой строке сценария: конвейер, где левое
    звено читает бесконечный источник, а правое закрывает канал, под
    `pipefail` объявляется отказом. Поэтому проверяется не участок, которого
    нет, а отсутствие самого приёма во всём файле.
    """

    def test_the_script_has_no_endless_source_piped_into_head(self):
        code = [
            line for line in SCRIPT.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("#")
        ]
        for line in code:
            assert not re.search(r"</dev/urandom\s*\|\s*head", line), line
            assert not re.search(r"/dev/urandom.*\|\s*head", line), line

    def test_the_old_sigpipe_pattern_really_does_fail(self):
        """Доказательство, что запрет выше не формальность."""
        result = run_bash(
            "set -Eeuo pipefail\n"
            "value=\"$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)\"\n"
            'echo "LEN=${#value}"\n'
        )
        assert result.returncode == 141, f"ожидался 141 (SIGPIPE), получен {result.returncode}"

    def test_the_script_creates_no_password_at_all(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for forbidden in ("htpasswd", "apache2-utils", "lords-staging-credentials"):
            assert forbidden not in text, forbidden


# ---------------------------------------------------------------------------
# Откат: ровно один раз и до конца
# ---------------------------------------------------------------------------
HARNESS = """
set -Eeuo pipefail
source "{header_file}"

ACTIONS="{actions}"

# Системные команды подменяются: тест ничего не меняет на хосте, но видит,
# что именно откат собирался сделать.
systemctl() {{ printf 'systemctl %s\\n' "$*" >> "${{ACTIONS}}"; return 0; }}
nginx()     {{ printf 'nginx %s\\n' "$*" >> "${{ACTIONS}}"; return 0; }}
rm()        {{ printf 'rm %s\\n' "$*" >> "${{ACTIONS}}"; return 0; }}
cp()        {{ printf 'cp %s\\n' "$*" >> "${{ACTIONS}}"; return 0; }}
install()   {{ printf 'install %s\\n' "$*" >> "${{ACTIONS}}"; return {install_rc}; }}

BACKUP_DIR="{backup}"
ROLLBACK_MARKER="{backup}/.rollback-done"
ROLLBACK_READY=1
stage "{stage}"

{trigger}
"""


def harness(tmp_path, *, trigger, install_rc=0, stage="проверяемый этап", env_canary=False):
    header_file = tmp_path / "header.sh"
    header_file.write_text(header(), encoding="utf-8")
    actions = tmp_path / "actions.log"
    actions.touch()
    backup = tmp_path / "backup"
    (backup / "systemd").mkdir(parents=True)
    # Юнит в снимке заставляет откат вызвать install — на нём и проверяется
    # поведение при неудачной команде внутри самого отката.
    (backup / "systemd" / "lords-01.service").write_text("[Unit]\n", encoding="utf-8")
    (backup / "active-units").write_text("lords-01.service\n", encoding="utf-8")

    script = HARNESS.format(
        header_file=header_file, actions=actions, backup=backup,
        install_rc=install_rc, stage=stage, trigger=trigger,
    )
    extra = {}
    if env_canary:
        extra["env"] = {**os.environ, "CANARY": CANARY}
    result = run_bash(script, **extra)
    return result, actions.read_text(encoding="utf-8")


class TestRollbackRunsOnce:
    def test_a_plain_failure_rolls_back_exactly_once(self, tmp_path):
        result, actions = harness(tmp_path, trigger="false")
        assert result.returncode == 1
        assert result.stderr.count("откат: возвращаю") == 1, result.stderr
        assert result.stderr.count("снимок сохранён") == 1, "откат не дошёл до конца"
        assert "systemctl daemon-reload" in actions

    def test_a_failure_inside_the_rollback_does_not_re_enter_the_handler(self, tmp_path):
        """Главная проверка регрессии двойного отката.

        `install` внутри отката отказывает. Прежде это снова поднимало ловушку
        ERR — обработчик входил повторно и обрывал откат на середине.
        """
        result, actions = harness(tmp_path, trigger="false", install_rc=1)

        assert result.stderr.count("откат: возвращаю") == 1, (
            "откат запустился больше одного раза:\n" + result.stderr
        )
        assert result.stderr.count("отказ на этапе") == 1, (
            "обработчик отказа сработал повторно:\n" + result.stderr
        )
        # И, что важнее, откат дошёл до конца, несмотря на неудачную команду.
        assert result.stderr.count("снимок сохранён") == 1, (
            "откат оборвался на середине:\n" + result.stderr
        )
        assert "systemctl start lords-01.service" in actions, (
            "юниты не были подняты обратно:\n" + actions
        )

    def test_a_failure_inside_a_command_substitution_rolls_back_once(self, tmp_path):
        """Ровно тот случай, что наблюдался на хосте.

        При отказе внутри `x="$(...)"` ловушка ERR срабатывает дважды: в
        подоболочке, наследующей её из-за `set -E`, и в родителе, когда
        присваивание возвращает ненулевой код. Переменная-guard от этого не
        спасает — подоболочка меняет только свою копию, — поэтому признак
        «уже откатились» держится в файле.
        """
        result, _actions = harness(
            tmp_path,
            trigger='value="$(LC_ALL=C tr -dc \'A-Za-z0-9\' </dev/urandom | head -c 8)"',
        )
        assert result.stderr.count("откат: возвращаю") == 1, (
            "откат выполнился дважды:\n" + result.stderr
        )
        assert result.stderr.count("снимок сохранён") == 1, (
            "откат не дошёл до конца:\n" + result.stderr
        )

    def test_the_marker_is_a_file_not_only_a_variable(self):
        """Переменной недостаточно: подоболочка родителю её не передаёт."""
        text = SCRIPT.read_text(encoding="utf-8")
        assert "ROLLBACK_MARKER" in text
        assert "noclobber" in text, "признак отката создаётся неатомарно"

    def test_rollback_is_skipped_when_nothing_was_changed_yet(self, tmp_path):
        header_file = tmp_path / "header.sh"
        header_file.write_text(header(), encoding="utf-8")
        result = run_bash(
            f'set -Eeuo pipefail\nsource "{header_file}"\nROLLBACK_READY=0\nfalse\n'
        )
        assert result.returncode == 1
        assert "откат" not in result.stderr, "откат при отсутствии изменений"

    def test_rollback_never_touches_paths_outside_lords(self, tmp_path):
        """Внутри /etc/nginx откату принадлежат ровно два пути.

        Каталог Lords и подключающий его файл в conf.d — всё остальное там
        чужое, в том числе конфигурация соседа.
        """
        allowed = ("/etc/nginx/lords", "/etc/nginx/conf.d/lords.conf")
        _result, actions = harness(tmp_path, trigger="false")
        touched = []
        for line in actions.splitlines():
            if not line.startswith(("rm ", "cp ", "install ")):
                continue
            assert "yummyani" not in line.lower(), line
            for token in line.split():
                if token.startswith("/etc/nginx"):
                    touched.append(token)
                    assert token.startswith(allowed), f"откат трогает чужой путь: {token}"
        assert touched, "откат не тронул ни одного пути в /etc/nginx — заглушки не сработали"


class TestFailureReport:
    def test_the_report_names_the_stage_and_the_command(self, tmp_path):
        result, _actions = harness(
            tmp_path, trigger="grep -q nosuchpattern /dev/null", stage="создание Basic Auth"
        )
        assert "отказ на этапе: создание Basic Auth" in result.stderr, result.stderr
        assert "команда: grep -q nosuchpattern /dev/null" in result.stderr, result.stderr
        assert "код возврата 1" in result.stderr, result.stderr

    def test_the_report_hides_credential_commands(self, tmp_path):
        """Текст команды с паролем не показывается даже неразвёрнутым.

        Значение-метка приходит из окружения: держать в тесте строку, похожую
        на пароль, незачем — проверяется, что она не всплывает в отчёте.
        """
        result, _actions = harness(
            tmp_path,
            trigger='password="${CANARY}"; htpasswd -bcB lords "${password}"',
            env_canary=True,
        )
        assert CANARY not in result.stderr, "значение пароля попало в отчёт"
        assert "скрыта" in result.stderr, result.stderr

    def test_the_report_never_prints_a_password_variable_value(self, tmp_path):
        result, _actions = harness(
            tmp_path, trigger='password="${CANARY}"; false', env_canary=True
        )
        assert CANARY not in result.stderr


class TestHostEnvironment:
    def test_the_stage_helper_is_used_across_the_script(self):
        text = SCRIPT.read_text(encoding="utf-8")
        assert text.count('\nstage "') >= 10, "этапы размечены не по всему сценарию"

    def test_the_handler_disarms_the_trap_before_rolling_back(self):
        text = SCRIPT.read_text(encoding="utf-8")
        handler = text.split("on_error() {", 1)[1].split("\n}", 1)[0]
        assert "trap - ERR" in handler
        assert handler.index("trap - ERR") < handler.index("rollback")

    def test_bash_is_the_one_the_host_runs(self):
        result = run_bash("echo ${BASH_VERSION}")
        assert result.returncode == 0
        major = int(result.stdout.strip().split(".")[0])
        assert major >= 5, f"ожидался bash 5.x (Ubuntu 22.04), получен {result.stdout.strip()}"


@pytest.mark.parametrize("interpreter", ["/usr/bin/python3"])
def test_host_python_is_the_one_the_units_use(interpreter):
    result = subprocess.run(
        [interpreter, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0
    assert result.stdout.strip().startswith("3."), result.stdout
