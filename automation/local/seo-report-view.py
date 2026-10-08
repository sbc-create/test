#!/usr/bin/env python3
"""Вкладка «SEO — ОТЧЁТ»: показывает новый суточный отчёт в 10:00 МСК.

    python3 automation/local/seo-report-view.py

* Отчёт дня D формирует служба seo-regular-daily (05:40 UTC); здесь он
  показывается в 10:00 МСК (07:00 UTC) того же дня — или сразу, если появился
  позже.
* Уже показанные отчёты повторно не выводятся, в том числе после перезапуска
  вкладки: показанная дата запоминается в ~/.seo-report-view.json. При первом
  запуске прошлые отчёты НЕ выводятся: вкладка ждёт ближайший.
* Если к 10:10 МСК отчёта дня нет, это сказано прямо, один раз.
* Почасовые сводки здесь не показываются — они в var/seo-regular/hourly.

Ничего не пишет, кроме своего файла состояния; в сессию Claude не вмешивается.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

REPORTS = Path(__file__).resolve().parents[2] / "var" / "seo-regular" / "reports" / "daily"
STATE = Path(os.path.expanduser("~/.seo-report-view.json"))
UTC = dt.timezone.utc
MSK = dt.timezone(dt.timedelta(hours=3))
SHOW_AT_UTC = dt.time(7, 0)  # 10:00 МСК
LATE_NOTE_AFTER = dt.timedelta(minutes=10)


def show_time(day: str) -> dt.datetime:
    return dt.datetime.combine(dt.date.fromisoformat(day), SHOW_AT_UTC, tzinfo=UTC)


def decide(available: list[str], now: dt.datetime, shown: str | None) -> dict:
    """Что делать сейчас. available — даты готовых отчётов (YYYY-MM-DD)."""
    due = [d for d in sorted(available) if show_time(d) <= now and (shown is None or d > shown)]
    if due:
        return {"show": due[-1]}  # пропущенные из-за простоя не выводятся пачкой
    today = now.astimezone(MSK).date().isoformat()
    if (
        show_time(today) + LATE_NOTE_AFTER <= now
        and today not in available
        and (shown is None or today > shown)
    ):
        return {"late": today}
    return {}


def _available() -> list[str]:
    return sorted(p.stem for p in REPORTS.glob("????-??-??.md"))


def _load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(state: dict) -> None:
    STATE.write_text(json.dumps(state), encoding="utf-8")


def main() -> int:
    sys.stdout.write("\033]0;SEO — ОТЧЁТ\007")
    state = _load()
    now = dt.datetime.now(UTC)
    if "shown" not in state:
        # Первый запуск: прошлые отчёты не выводятся — ждём ближайший.
        past = [d for d in _available() if show_time(d) <= now]
        state["shown"] = past[-1] if past else None
        _save(state)
    print(
        f"SEO — ОТЧЁТ: жду суточный отчёт (показ в 10:00 МСК). Последний показанный: "
        f"{state.get('shown') or 'нет'}.",
        flush=True,
    )
    while True:
        now = dt.datetime.now(UTC)
        action = decide(_available(), now, state.get("shown"))
        if "show" in action:
            day = action["show"]
            text = (REPORTS / f"{day}.md").read_text(encoding="utf-8")
            print("\033[2J\033[H", end="")
            print(
                f"=== SEO — ОТЧЁТ за {day}, показан {now.astimezone(MSK):%Y-%m-%d %H:%M} МСК ===\n"
            )
            print(text, flush=True)
            state["shown"] = day
            state.pop("late_noted", None)
            _save(state)
        elif "late" in action and state.get("late_noted") != action["late"]:
            print(
                f"\n[{now.astimezone(MSK):%H:%M} МСК] Отчёт за {action['late']} "
                "ещё не сформирован — проверьте seo-regular-daily. "
                "Покажу, как только появится.",
                flush=True,
            )
            state["late_noted"] = action["late"]
            _save(state)
        time.sleep(30)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
