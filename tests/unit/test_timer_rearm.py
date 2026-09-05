"""REQ-TIMER-REARM: таймер обязан переоснащаться после неудачного запуска.

Дефект, который эти проверки закрывают: `lords-content-refresh.timer` был задан
только через OnBootSec и OnUnitActiveSec. Запуск 2026-09-04 07:01 убили
сигналом, служба больше не активировалась, и следующий срок стал `infinity` —
таймер числился active, а каталог не обновлялся сутки.

OnUnitActiveSec считает от активации службы. Если служба мертва, считать не от
чего. OnUnitInactiveSec считает от завершения — и переоснащает таймер после
любого исхода, включая убитый.
"""
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TIMERS = sorted((REPO / "automation" / "host" / "systemd").glob("*.timer"))


def читать(p: Path) -> dict[str, list[str]]:
    поля: dict[str, list[str]] = {}
    for строка in p.read_text(encoding="utf-8").splitlines():
        строка = строка.strip()
        if not строка or строка.startswith("#") or "=" not in строка:
            continue
        k, _, v = строка.partition("=")
        поля.setdefault(k.strip(), []).append(v.strip())
    return поля


@pytest.mark.parametrize("path", TIMERS, ids=lambda p: p.name)
def test_таймер_переоснащается_после_неудачи(path):
    """Хотя бы один якорь, не зависящий от успешной активации службы."""
    поля = читать(path)
    календарь = [v for v in поля.get("OnCalendar", []) if v]
    после_завершения = [v for v in поля.get("OnUnitInactiveSec", []) if v]
    после_активации = [v for v in поля.get("OnUnitActiveSec", []) if v]
    if не_периодический(поля):
        pytest.skip("таймер не периодический")
    assert календарь or после_завершения, (
        f"{path.name}: расписание только через OnUnitActiveSec={после_активации}. "
        "После убитого запуска служба не активируется, следующий срок становится "
        "infinity, и таймер молча перестаёт работать, оставаясь active."
    )


def не_периодический(поля) -> bool:
    периодические = ("OnCalendar", "OnUnitActiveSec", "OnUnitInactiveSec")
    return not any(v for k in периодические for v in поля.get(k, []) if v)


def test_обновление_каталога_переоснащается():
    """Именно этот таймер застрял в проде."""
    поля = читать(REPO / "automation" / "host" / "systemd" / "lords-content-refresh.timer")
    assert [v for v in поля.get("OnUnitInactiveSec", []) if v], (
        "у обновления каталога нет якоря по завершению")


def test_интервал_не_превышает_обещанной_свежести():
    """SLO свежести пятнадцать минут; интервал обязан быть меньше."""
    поля = читать(REPO / "automation" / "host" / "systemd" / "lords-content-refresh.timer")
    for ключ in ("OnUnitActiveSec", "OnUnitInactiveSec"):
        for v in поля.get(ключ, []):
            m = re.match(r"^(\d+)min$", v)
            if m:
                assert int(m.group(1)) <= 15, f"{ключ}={v} превышает обещанную свежесть"
