"""Сторож автоматического обновления каталога Lords.

Существует из-за конкретного случая. 30 августа 2026 года таймер
`lords-content-refresh.timer` оказался `enabled`, но `inactive`: следующего
срабатывания у него не было вовсе, и обновление каталога просто перестало
происходить. Витрины при этом отвечали HTTP 200 и выглядели исправными —
заметить это можно было только по датам в каталоге. Три с половиной часа никто
не знал.

Ровно эти три состояния сторож и различает:

* таймер включён при загрузке, но не запущен сейчас — «enabled» без «active»;
* таймер активен, но следующего срабатывания у него нет;
* обновлений давно не было, независимо от состояния таймера.

Все три дают критический уровень. Предупредительного уровня у первых двух нет
намеренно: таймер либо тикает, либо нет, промежуточного состояния тут не бывает.
"""
from __future__ import annotations

import contextlib
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

SERVICE = "lords-content-refresh.service"
TIMER = "lords-content-refresh.timer"
STATE_DIR = Path("/var/lib/lords-content-refresh")

#: Насколько давним может быть последний успешный обход, прежде чем это станет
#: поводом для тревоги. Цикл занимает около восьми часов, таймер повторяет его
#: раз в девять: два пропущенных цикла — это сутки без обновления, и дольше
#: молчать нельзя.
WARNING_AGE = timedelta(hours=12)
CRITICAL_AGE = timedelta(hours=24)


class Level:
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


ORDER = {Level.OK: 0, Level.WARNING: 1, Level.CRITICAL: 2}


@dataclass
class TimerFacts:
    """Что systemd говорит о таймере и службе."""

    timer_active: bool
    timer_enabled: bool
    next_elapse: str
    service_active: bool
    service_result: str
    last_success: datetime | None


@dataclass
class Verdict:
    level: str = Level.OK
    reasons: list[str] = field(default_factory=list)
    facts: dict = field(default_factory=dict)

    def raise_to(self, level: str, reason: str) -> None:
        self.reasons.append(reason)
        if ORDER[level] > ORDER[self.level]:
            self.level = level


def _systemctl(*args: str) -> str:
    try:
        return subprocess.run(
            ["systemctl", *args], capture_output=True, text=True, check=False, timeout=15
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _read_last_success(state_dir: Path) -> datetime | None:
    path = state_dir / "last_success"
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def collect(state_dir: Path = STATE_DIR) -> TimerFacts:
    return TimerFacts(
        timer_active=_systemctl("is-active", TIMER) == "active",
        timer_enabled=_systemctl("is-enabled", TIMER) in ("enabled", "enabled-runtime"),
        # Пустая строка — это «срабатываний не запланировано». Значение
        # приходится читать как строку: systemd отдаёт то время, то ничего.
        next_elapse=_systemctl("show", TIMER, "-p", "NextElapseUSecMonotonic", "--value"),
        service_active=_systemctl("is-active", SERVICE) in ("active", "activating"),
        service_result=_systemctl("show", SERVICE, "-p", "Result", "--value"),
        last_success=_read_last_success(state_dir),
    )


def evaluate(facts: TimerFacts, *, now: datetime | None = None) -> Verdict:
    now = now or datetime.now(timezone.utc)
    verdict = Verdict()

    if facts.timer_enabled and not facts.timer_active:
        verdict.raise_to(
            Level.CRITICAL,
            "таймер включён при загрузке, но не запущен сейчас: обновление каталога "
            "не произойдёт, а витрины продолжат отвечать 200",
        )
    elif not facts.timer_enabled:
        verdict.raise_to(
            Level.CRITICAL,
            "таймер не включён: после перезагрузки обновление не возобновится",
        )

    if facts.timer_active and not facts.next_elapse:
        verdict.raise_to(
            Level.CRITICAL,
            "таймер активен, но следующего срабатывания у него нет: он больше не тикает",
        )

    if facts.last_success is None:
        verdict.raise_to(
            Level.CRITICAL,
            "нет отметки об успешном обходе: неизвестно, обновлялся ли каталог хоть раз",
        )
    else:
        age = now - facts.last_success
        if age >= CRITICAL_AGE:
            verdict.raise_to(
                Level.CRITICAL,
                f"последний успешный обход был {_human(age)} назад",
            )
        elif age >= WARNING_AGE:
            verdict.raise_to(
                Level.WARNING,
                f"последний успешный обход был {_human(age)} назад",
            )

    # Отказ последнего прогона — повод предупредить, но не тревожить: витрина
    # осталась на прежнем релизе и отвечает. Тревогу поднимает устаревание.
    if facts.service_result not in ("success", "") and not facts.service_active:
        verdict.raise_to(
            Level.WARNING,
            f"последний прогон окончился как {facts.service_result}",
        )

    verdict.facts = {
        "timer_active": facts.timer_active,
        "timer_enabled": facts.timer_enabled,
        "next_elapse": facts.next_elapse or None,
        "service_active": facts.service_active,
        "service_result": facts.service_result or None,
        "last_success": facts.last_success.isoformat() if facts.last_success else None,
    }
    return verdict


def _human(delta: timedelta) -> str:
    hours = int(delta.total_seconds() // 3600)
    minutes = int((delta.total_seconds() % 3600) // 60)
    return f"{hours} ч {minutes} мин" if hours else f"{minutes} мин"


def check(state_dir: Path = STATE_DIR, *, now: datetime | None = None) -> Verdict:
    return evaluate(collect(state_dir), now=now)


def write_status(verdict: Verdict, state_dir: Path = STATE_DIR,
                 *, now: datetime | None = None) -> Path:
    """Состояние ложится файлом рядом с прочим состоянием обновления."""
    now = now or datetime.now(timezone.utc)
    payload = {
        "checked_at": now.isoformat(),
        "level": verdict.level,
        "reasons": verdict.reasons,
        "facts": verdict.facts,
    }
    path = state_dir / "refresh-watchdog-status.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if verdict.level != Level.OK:
        # Тревоги дописываются, а не перезаписываются: история важнее краткости.
        alerts = state_dir / "refresh-watchdog-alerts.jsonl"
        with alerts.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    """Код возврата: 0 — всё в порядке, 1 — предупреждение, 2 — тревога."""
    verdict = check()
    # Невозможность записать состояние не должна мешать сказать вердикт вслух:
    # тревога, не доехавшая до дежурного из-за прав на каталог, бесполезна.
    with contextlib.suppress(OSError):
        write_status(verdict)
    print(f"[lords-refresh-watchdog] {verdict.level}")
    for reason in verdict.reasons:
        print(f"  {reason}")
    return {Level.OK: 0, Level.WARNING: 1, Level.CRITICAL: 2}[verdict.level]


if __name__ == "__main__":
    raise SystemExit(main())
