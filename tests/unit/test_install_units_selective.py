"""REQ-INSTALL-SELECTIVE: можно поставить названные unit'ы, а не всё сразу.

Установщик ставил всё, что лежит в каталоге. Для владельца это означало выбор
между «поставить лишнее» и «не ставить ничего»: ветка, где менялся один unit,
заодно заменила бы остальные их версиями из этой ветки — а они там могли не
меняться вовсе или меняться чужой рукой. Владелец обоснованно выбирал второе,
и подготовленные unit'ы оставались лежать.

Отбор идёт до проверки root: опечатку в имени незачем ловить только под sudo.
Именно это здесь и проверяется — тесты выполняются от обычного пользователя,
и без такого порядка проверить отбор было бы нечем.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "automation" / "host" / "install-units.sh"
UNITS = REPO / "automation" / "host" / "systemd"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    assert SCRIPT.exists(), f"нет установщика: {SCRIPT}"
    return subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True, timeout=60
    )


def test_unknown_unit_is_refused_before_root_check() -> None:
    result = run("нет-такого.service")
    assert result.returncode == 66, result.stderr
    assert "нет такого" in result.stderr
    assert "systemd" in result.stderr, "сообщение должно называть каталог, где искали"


def test_known_unit_passes_selection() -> None:
    """Дальше отбора идёт проверка прав — значит отбор пройден."""
    existing = sorted(p.name for p in UNITS.glob("*.timer"))
    assert existing, "в репозитории нет ни одного timer'а"

    result = run(existing[0])

    assert result.returncode != 66, "существующий unit отвергнут отбором"
    assert "нужен root" in (result.stderr + result.stdout)


def test_no_arguments_keeps_the_old_behaviour() -> None:
    """Прежний способ вызова обязан работать как раньше."""
    result = run()
    assert result.returncode != 66
    assert "нужен root" in (result.stderr + result.stdout)


def test_explicit_list_does_not_enable_timers() -> None:
    """Включение и здесь остаётся отдельным шагом.

    Ставить чужие timer'ы за того, кто попросил один конкретный, — самоуправство.
    Скрипт вместо этого печатает команду включения.
    """
    text = SCRIPT.read_text(encoding="utf-8")
    marker = text.index('if [ "$#" -gt 0 ]; then\n  echo\n  echo "timer\'ы не включены')
    enable_loop = text.index("for timer in site-factory-health.timer")
    assert marker < enable_loop, "выход при явном списке должен быть до автовключения"
    assert "systemctl enable --now" in text, "нет подсказки, как включить вручную"


def test_prepared_units_are_installable_by_name() -> None:
    """Ради этого всё и делалось: подготовленные unit'ы можно поставить точечно."""
    for name in (
        "yummy-site-backup.service",
        "yummy-site-backup.timer",
        "yummy-episode-watcher.service",
    ):
        assert (UNITS / name).exists(), f"нет подготовленного unit'а {name}"
        assert run(name).returncode != 66, f"{name} не проходит отбор"
