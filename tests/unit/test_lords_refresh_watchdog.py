"""Сторож обязан поднимать тревогу ровно в тех случаях, что уже случались."""
import json
from datetime import datetime, timedelta, timezone

from factory.lords.refresh_watchdog import (
    CRITICAL_AGE,
    WARNING_AGE,
    Level,
    TimerFacts,
    evaluate,
    write_status,
)

СЕЙЧАС = datetime(2026, 8, 30, 18, 0, tzinfo=timezone.utc)


def факты(**kw) -> TimerFacts:
    основа = {
        "timer_active": True,
        "timer_enabled": True,
        "next_elapse": "6d 8h 28min",
        "service_active": False,
        "service_result": "success",
        "last_success": СЕЙЧАС - timedelta(hours=1),
    }
    основа.update(kw)
    return TimerFacts(**основа)


class TestЗдоровоеСостояние:
    def test_всё_тикает_тревоги_нет(self):
        assert evaluate(факты(), now=СЕЙЧАС).level == Level.OK

    def test_идущий_прогон_не_тревога(self):
        вердикт = evaluate(факты(service_active=True, service_result=""), now=СЕЙЧАС)
        assert вердикт.level == Level.OK


class TestСлучайКоторыйУжеБыл:
    """30 августа 2026: таймер enabled, но inactive; никто не знал три с половиной часа."""

    def test_enabled_без_active_это_тревога(self):
        вердикт = evaluate(факты(timer_active=False), now=СЕЙЧАС)
        assert вердикт.level == Level.CRITICAL
        assert any("не запущен сейчас" in r for r in вердикт.reasons)

    def test_в_причине_сказано_что_витрины_выглядят_исправными(self):
        """Иначе дежурный увидит 200 и решит, что тревога ложная."""
        вердикт = evaluate(факты(timer_active=False), now=СЕЙЧАС)
        assert any("200" in r for r in вердикт.reasons)

    def test_активный_таймер_без_срабатываний_это_тревога(self):
        вердикт = evaluate(факты(next_elapse=""), now=СЕЙЧАС)
        assert вердикт.level == Level.CRITICAL
        assert any("больше не тикает" in r for r in вердикт.reasons)

    def test_выключенный_таймер_это_тревога(self):
        вердикт = evaluate(факты(timer_enabled=False, timer_active=False), now=СЕЙЧАС)
        assert вердикт.level == Level.CRITICAL
        assert any("не включён" in r for r in вердикт.reasons)


class TestУстаревание:
    def test_свежий_обход_не_тревожит(self):
        assert evaluate(факты(), now=СЕЙЧАС).level == Level.OK

    def test_полсуток_без_обхода_предупреждение(self):
        вердикт = evaluate(факты(last_success=СЕЙЧАС - WARNING_AGE), now=СЕЙЧАС)
        assert вердикт.level == Level.WARNING

    def test_сутки_без_обхода_тревога(self):
        вердикт = evaluate(факты(last_success=СЕЙЧАС - CRITICAL_AGE), now=СЕЙЧАС)
        assert вердикт.level == Level.CRITICAL

    def test_отсутствие_отметки_это_тревога(self):
        """«Неизвестно» здесь опаснее, чем «давно»."""
        вердикт = evaluate(факты(last_success=None), now=СЕЙЧАС)
        assert вердикт.level == Level.CRITICAL
        assert any("неизвестно" in r.lower() for r in вердикт.reasons)


class TestОтказПрогона:
    def test_отказ_прогона_предупреждение_а_не_тревога(self):
        """Витрина осталась на прежнем релизе и отвечает; тревогу поднимает устаревание."""
        вердикт = evaluate(факты(service_result="timeout"), now=СЕЙЧАС)
        assert вердикт.level == Level.WARNING
        assert any("timeout" in r for r in вердикт.reasons)

    def test_отказ_вместе_с_мёртвым_таймером_даёт_тревогу(self):
        вердикт = evaluate(факты(service_result="timeout", timer_active=False), now=СЕЙЧАС)
        assert вердикт.level == Level.CRITICAL
        assert len(вердикт.reasons) >= 2, "обе причины обязаны быть названы"


class TestЗаписьСостояния:
    def test_состояние_пишется_файлом(self, tmp_path):
        вердикт = evaluate(факты(), now=СЕЙЧАС)
        путь = write_status(вердикт, tmp_path, now=СЕЙЧАС)
        данные = json.loads(путь.read_text(encoding="utf-8"))
        assert данные["level"] == "ok"
        assert данные["facts"]["timer_active"] is True

    def test_тревоги_дописываются_а_не_затирают_историю(self, tmp_path):
        for _ in range(3):
            write_status(evaluate(факты(timer_active=False), now=СЕЙЧАС), tmp_path, now=СЕЙЧАС)
        строки = (tmp_path / "refresh-watchdog-alerts.jsonl").read_text(
            encoding="utf-8"
        ).strip().splitlines()
        assert len(строки) == 3

    def test_спокойное_состояние_не_попадает_в_ленту_тревог(self, tmp_path):
        write_status(evaluate(факты(), now=СЕЙЧАС), tmp_path, now=СЕЙЧАС)
        assert not (tmp_path / "refresh-watchdog-alerts.jsonl").exists()
