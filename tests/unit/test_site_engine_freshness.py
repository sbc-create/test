"""Быстрый путь свежести: очередь, времена и обещание в пятнадцать минут."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from factory.site_engine.freshness import (
    CRITICAL_AGE,
    WARNING_AGE,
    FreshnessQueue,
    Lock,
    QueueItem,
    Timeline,
    evaluate_sla,
    provider_gap,
    run_fast_cycle,
)

MOMENT = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


def элемент(ключ: str = "k1", *, detected: datetime | None = None, **kw) -> QueueItem:
    return QueueItem(
        idempotency_key=ключ,
        event_type=kw.pop("event_type", "EPISODE_ADDED"),
        canonical_title_id=kw.pop("canonical_title_id", "p:1"),
        payload=kw.pop("payload", {"season": 1}),
        timeline=Timeline(detected_at=detected or MOMENT,
                          provider_timestamp=kw.pop("provider_timestamp", None)),
    )


@pytest.fixture
def очередь(tmp_path: Path) -> FreshnessQueue:
    return FreshnessQueue(tmp_path / "queue.json")


class TestОчередьПереживаетПерезапуск:
    def test_элементы_восстанавливаются(self, tmp_path: Path):
        """Очередь, теряющаяся при перезапуске, теряет серию именно тогда,
        когда что-то пошло не так."""
        путь = tmp_path / "queue.json"
        первая = FreshnessQueue(путь)
        первая.offer(элемент("k1"))
        первая.offer(элемент("k2"))
        первая.save()

        вторая = FreshnessQueue(путь)
        assert len(вторая.pending()) == 2

    def test_обработанные_не_возвращаются(self, tmp_path: Path):
        путь = tmp_path / "queue.json"
        первая = FreshnessQueue(путь)
        первая.offer(элемент("k1"))
        первая.complete("k1", live_verified_at=MOMENT + timedelta(minutes=2))
        первая.save()
        assert FreshnessQueue(путь).pending() == []

    def test_запись_атомарна(self, очередь, tmp_path):
        очередь.offer(элемент())
        очередь.save()
        assert not list(tmp_path.glob("*.tmp"))

    def test_чужая_версия_не_роняет(self, tmp_path: Path):
        import json

        путь = tmp_path / "queue.json"
        путь.write_text(json.dumps({"schema_version": "0.1", "items": []}), encoding="utf-8")
        assert len(FreshnessQueue(путь)) == 0


class TestИдемпотентность:
    def test_повтор_не_создаёт_второй_записи(self, очередь):
        assert очередь.offer(элемент("k1")) is True
        assert очередь.offer(элемент("k1")) is False
        assert len(очередь.pending()) == 1

    def test_разные_ключи_живут_отдельно(self, очередь):
        очередь.offer(элемент("k1"))
        очередь.offer(элемент("k2"))
        assert len(очередь.pending()) == 2


class TestВремена:
    def test_время_поставщика_не_подменяет_наблюдение(self):
        """Подмена выдала бы наше наблюдение за факт выхода серии."""
        t = Timeline(detected_at=MOMENT, provider_timestamp=MOMENT - timedelta(days=30))
        t.live_verified_at = MOMENT + timedelta(minutes=3)
        assert t.total_latency_seconds == 180
        assert t.provider_timestamp != t.detected_at

    def test_незавершённое_изменение_не_имеет_задержки(self):
        assert Timeline(detected_at=MOMENT).total_latency_seconds is None

    def test_все_отметки_сохраняются(self, tmp_path: Path):
        путь = tmp_path / "q.json"
        q = FreshnessQueue(путь)
        item = элемент("k1")
        item.timeline.render_started_at = MOMENT + timedelta(seconds=10)
        item.timeline.published_at = MOMENT + timedelta(seconds=40)
        q.offer(item)
        q.save()
        снова = FreshnessQueue(путь).pending()[0]
        assert снова.timeline.render_started_at == MOMENT + timedelta(seconds=10)
        assert снова.timeline.published_at == MOMENT + timedelta(seconds=40)


class TestSLA:
    def test_пустая_очередь_это_не_задержка(self, очередь):
        """У поставщика нет изменений — это не наша вина."""
        отчёт = evaluate_sla(очередь, now=MOMENT)
        assert отчёт.level == "ok"
        assert provider_gap(очередь)

    def test_десять_минут_ожидания_это_предупреждение(self, очередь):
        очередь.offer(элемент("k1", detected=MOMENT - WARNING_AGE))
        assert evaluate_sla(очередь, now=MOMENT).level == "warning"

    def test_пятнадцать_минут_ожидания_это_тревога(self, очередь):
        очередь.offer(элемент("k1", detected=MOMENT - CRITICAL_AGE))
        отчёт = evaluate_sla(очередь, now=MOMENT)
        assert отчёт.level == "critical"
        assert "обещании" in отчёт.reasons[0]

    def test_отсутствие_циклов_это_тревога(self, очередь):
        отчёт = evaluate_sla(очередь, last_success=MOMENT - CRITICAL_AGE, now=MOMENT)
        assert отчёт.level == "critical"

    def test_свежий_цикл_не_тревожит(self, очередь):
        отчёт = evaluate_sla(очередь, last_success=MOMENT - timedelta(minutes=3), now=MOMENT)
        assert отчёт.level == "ok"

    def test_превышение_p95_это_тревога(self, очередь):
        for i in range(20):
            item = элемент(f"k{i}", detected=MOMENT)
            item.timeline.live_verified_at = MOMENT + timedelta(minutes=30)
            очередь.offer(item)
            очередь.complete(f"k{i}")
        отчёт = evaluate_sla(очередь, now=MOMENT)
        assert отчёт.level == "critical"
        assert отчёт.p95_seconds == 1800

    def test_p95_считается_по_измеренному(self, очередь):
        for i in range(10):
            item = элемент(f"k{i}", detected=MOMENT)
            item.timeline.live_verified_at = MOMENT + timedelta(seconds=60 + i)
            очередь.offer(item)
            очередь.complete(f"k{i}")
        отчёт = evaluate_sla(очередь, now=MOMENT)
        assert отчёт.measured == 10
        assert 60 <= отчёт.p95_seconds <= 69


class TestЗамок:
    def test_второй_цикл_не_входит(self, tmp_path: Path):
        замок = Lock(tmp_path / "lock")
        assert замок.acquire(now=MOMENT) is True
        assert Lock(tmp_path / "lock").acquire(now=MOMENT) is False

    def test_брошенный_замок_перехватывается(self, tmp_path: Path):
        """Оборванный процесс иначе останавливает очередь навсегда и молча."""
        замок = Lock(tmp_path / "lock")
        замок.acquire(now=MOMENT)
        поздно = MOMENT + timedelta(minutes=20)
        assert Lock(tmp_path / "lock").acquire(now=поздно) is True

    def test_освобождённый_замок_свободен(self, tmp_path: Path):
        замок = Lock(tmp_path / "lock")
        замок.acquire(now=MOMENT)
        замок.release()
        assert замок.acquire(now=MOMENT) is True

    def test_возраст_замка_известен(self, tmp_path: Path):
        замок = Lock(tmp_path / "lock")
        замок.acquire(now=MOMENT)
        assert замок.age(now=MOMENT + timedelta(minutes=5)) == timedelta(minutes=5)


class TestЦикл:
    def test_пустой_цикл_ничего_не_рендерит(self, очередь):
        итог = run_fast_cycle(очередь, render=lambda i: 1, publish=lambda: None,
                              verify=lambda i: True)
        assert итог.pages_rendered == 0
        assert итог.published is False
        assert "пусто" in итог.reason

    def test_цикл_рендерит_только_затронутое(self, очередь):
        страниц = []
        итог = run_fast_cycle(
            очередь,
            incoming=[элемент("k1")],
            render=lambda i: страниц.append(i) or 4,
            publish=lambda: None,
            verify=lambda i: True,
        )
        assert итог.processed == 1
        assert итог.pages_rendered == 4
        assert итог.published is True

    def test_повтор_в_том_же_цикле_не_дублируется(self, очередь):
        итог = run_fast_cycle(
            очередь, incoming=[элемент("k1"), элемент("k1")],
            render=lambda i: 1, publish=lambda: None, verify=lambda i: True,
        )
        assert итог.processed == 1
        assert итог.skipped_duplicates == 1

    def test_неподтверждённое_изменение_остаётся_в_очереди(self, очередь):
        """Не подтвердилось на живом адресе — значит, не сделано."""
        run_fast_cycle(очередь, incoming=[элемент("k1")], render=lambda i: 1,
                       publish=lambda: None, verify=lambda i: False)
        assert len(очередь.pending()) == 1

    def test_подтверждённое_уходит_из_очереди(self, очередь):
        run_fast_cycle(очередь, incoming=[элемент("k1")], render=lambda i: 1,
                       publish=lambda: None, verify=lambda i: True)
        assert очередь.pending() == []

    def test_попытки_считаются(self, очередь):
        for _ in range(3):
            run_fast_cycle(очередь, incoming=[элемент("k1")], render=lambda i: 1,
                           publish=lambda: None, verify=lambda i: False)
        assert очередь.pending()[0].attempts == 3
