"""REQ-HEALTH-LOG-ROTATION: лог здоровья вращается, а не растёт без предела.

История отказа. `site-factory-health.service` работает от root, поэтому `tee`
создавал `/var/log/site-factory/health.log` как `root:root`. Каталог принадлежит
`claude`, и logrotate для него настроен с `su claude claude` — понижает права и
затем не может открыть root-овский файл.

Итог, видимый в журнале с 2026-09-02: `logrotate.service` падал ежедневно с
`error opening /var/log/site-factory/health.log: Permission denied`, лог не
вращался вовсе, а отказ выглядел как поломка ротации целиком, хотя спотыкалась
она об один файл.

Выравнивание делает тот, кто пишет: он один знает, что создал файл, и он один
имеет на это права.

Чего этот тест НЕ покрывает и почему. Случай «владелец файла отличается от
владельца каталога» требует создать файл от другого пользователя, то есть root.
Тесты выполняются от `claude`, поэтому проверяются безопасные ветки: совпадение
владельцев, отсутствие файла и отсутствие прав. Ветку с настоящим chown
проверяет только эксплуатация, и это сказано здесь прямо, а не умолчано.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "automation" / "host" / "site-factory-health.sh"


def function_source() -> str:
    """Функция извлекается из скрипта: копия в тесте разошлась бы с оригиналом."""
    text = SCRIPT.read_text(encoding="utf-8")
    match = re.search(r"^align_log_owner\(\) \{.*?^\}", text, re.S | re.M)
    assert match, "align_log_owner не найдена в скрипте здоровья"
    return match.group(0)


def run_function(body: str) -> subprocess.CompletedProcess[str]:
    script = f"set -uo pipefail\n{function_source()}\n{body}\n"
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60)


def test_function_is_self_contained() -> None:
    """Функция обязана работать в отрыве от остального скрипта."""
    result = run_function('align_log_owner /tmp /tmp; echo "rc=$?"')
    assert "rc=0" in result.stdout, result.stderr


def test_same_owner_changes_nothing(tmp_path: Path) -> None:
    log = tmp_path / "health.log"
    log.write_text("x", encoding="utf-8")
    before = log.stat()

    result = run_function(f'align_log_owner "{tmp_path}" "{log}"; echo "rc=$?"')

    assert "rc=0" in result.stdout
    assert log.stat().st_uid == before.st_uid
    assert log.read_text(encoding="utf-8") == "x", "содержимое лога не должно меняться"


def test_missing_file_is_not_an_error(tmp_path: Path) -> None:
    """Первый запуск на чистом хосте не должен валить проверку здоровья."""
    result = run_function(f'align_log_owner "{tmp_path}" "{tmp_path}/нет.log"; echo "rc=$?"')
    assert "rc=0" in result.stdout


def test_missing_directory_is_not_an_error(tmp_path: Path) -> None:
    result = run_function(f'align_log_owner "{tmp_path}/нет" "{tmp_path}/нет/x.log"; echo "rc=$?"')
    assert "rc=0" in result.stdout


def test_health_script_calls_the_alignment_after_writing() -> None:
    """Порядок важен: выравнивать нечего, пока файл не создан."""
    text = SCRIPT.read_text(encoding="utf-8")
    write_at = text.index('tee -a "$STATE_DIR/health.log"')
    call_at = text.index('align_log_owner "$STATE_DIR"')
    assert call_at > write_at, "выравнивание вызвано раньше записи"


def test_logrotate_config_is_version_controlled() -> None:
    """Конфиг ротации жил только на хосте: ни ревью, ни отката, ни переноса."""
    config = REPO / "automation" / "host" / "logrotate" / "site-factory"
    assert config.exists(), "конфиг logrotate не внесён в репозиторий"
    text = config.read_text(encoding="utf-8")
    assert "/var/log/site-factory/*.log" in text
    assert "su claude claude" in text, "правило su и есть причина, ради которой выравнивают владельца"
