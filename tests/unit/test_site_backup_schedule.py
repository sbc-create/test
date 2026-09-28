"""REQ-SITE-BACKUP-SCHEDULE: базы витрин копируются по расписанию, а не только при выкатке.

Измерено 2026-09-03. Копия трёх баз YummyAnime снималась ТОЛЬКО из deploy.sh —
других вызывающих у `deploy/staging/backup.sh` нет, таймера не существовало.
Последняя копия датировалась 31 августа 16:35, то есть RPO составил трое суток
и продолжал расти с каждым днём без выкатки.

Другого механизма нет: базы лежат в томах docker
(`/var/lib/docker/volumes/yummyani-staging_pg_*`), то есть вне `/srv/sites`,
который собирает host-бэкап. Единственный ежедневный таймер, `site-factory-backup`,
их не касается — и вдобавок сам падал с 03:28 того же дня.

Тест закрепляет три вещи: юнит существует, зовёт настоящий скрипт, и таймер
не назначен на круглую минуту (в ноль стартует слишком многое сразу).
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
UNITS = REPO / "automation" / "host" / "systemd"
SERVICE = UNITS / "yummy-site-backup.service"
TIMER = UNITS / "yummy-site-backup.timer"


def test_service_unit_exists_and_calls_the_real_script() -> None:
    assert SERVICE.exists(), "нет юнита резервного копирования витрин"
    text = SERVICE.read_text(encoding="utf-8")
    assert "deploy/staging/backup.sh" in text, "юнит должен звать существующий скрипт, а не свой дубль"
    assert "Type=oneshot" in text


def test_timer_exists_and_is_daily() -> None:
    assert TIMER.exists(), "без таймера юнит остаётся ручным, то есть ничего не меняет"
    text = TIMER.read_text(encoding="utf-8")
    assert "OnCalendar=" in text
    assert "Persistent=true" in text, "пропущенный из-за выключенного хоста прогон обязан догоняться"


def test_timer_avoids_the_round_minute() -> None:
    """В ноль минут стартует слишком многое сразу, включая host-бэкап в 03:20."""
    text = TIMER.read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if ln.startswith("OnCalendar="))
    minute = line.split(":")[1]
    assert minute not in {"00", "30"}, f"таймер назначен на круглую минуту: {line}"


def test_unit_bounds_its_own_growth() -> None:
    """Ежедневный таймер обязан ограничивать рост, а не только создавать копии.

    Раньше здесь проверялось наличие предупреждения: у скрипта сайта удержания
    не было, и таймер без него заполнил бы диск. Удержание написано отдельно
    (`site-backup-retention.sh`) и подключено вторым шагом, поэтому проверка
    сменилась с «предупреждение на месте» на «рост действительно ограничен».

    Причина, по которой это вообще важно, названа в самом юните: этот диск уже
    ломался на неограниченном росте бэкапов.
    """
    text = SERVICE.read_text(encoding="utf-8")
    assert "site-backup-retention.sh" in text, "таймер создаёт копии, но не ограничивает рост"
    assert "No space left on device" in text, "не назван инцидент, ради которого удержание нужно"
