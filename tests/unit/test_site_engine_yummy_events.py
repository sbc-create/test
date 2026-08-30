"""Согласие двух языков об одном событии.

Наблюдатель написан на TypeScript и пишет ленту в своём формате; контракт
Site Engine написан на Python. Тесты проверяют, что переводчик между ними
покрывает весь словарь наблюдателя и сохраняет свойства контракта.
"""
import json
from datetime import timezone
from pathlib import Path

import pytest

from factory.site_engine.adapters.yummy_events import (
    ALIASES,
    WATCHER_KINDS,
    UnknownEventKind,
    YummyEventLog,
    event_from_watcher,
)
from factory.site_engine.contracts import ContractError, EventType

ROOT = Path(__file__).resolve().parents[2]

#: Запись снята с настоящей ленты наблюдателя.
СОБЫТИЕ = {
    "titleId": "019efa53-fb26-7ef3-a615-4a088f510ba8",
    "name": "Рекомендация старшеклассника Ивамото",
    "observedAt": "2026-08-29T18:26:51.072Z",
    "providerTimestamp": "2026-07-04T17:22:46Z",
    "endpoint": "detail:active",
    "kind": "EPISODE_ADDED",
    "from": 8,
    "to": 9,
    "season": 1,
    "episode": 9,
    "fingerprint": "1:9:9",
    "playable": True,
}


class TestСловарь:
    def test_весь_словарь_наблюдателя_переводится(self):
        """Род события, который выпускает витрина, обязан иметь перевод.

        Проверяется словарь из кода наблюдателя, а не роды, попавшиеся в ленте:
        событие, ещё ни разу не выпущенное, всё равно должно переводиться.
        """
        известные = {t.value for t in EventType}
        непокрытые = [k for k in WATCHER_KINDS if k not in ALIASES and k not in известные]
        assert not непокрытые, f"без перевода остались: {непокрытые}"

    def test_незнакомый_род_это_отказ_а_не_пропуск(self):
        """Молчаливый пропуск спрятал бы расхождение до худшего момента."""
        with pytest.raises(UnknownEventKind, match="которого нет в контракте"):
            event_from_watcher({**СОБЫТИЕ, "kind": "ЧТО-ТО-НОВОЕ"})

    def test_переименование_не_удваивает_контракт(self):
        """METADATA_UPDATED и TITLE_UPDATED — одно утверждение."""
        событие = event_from_watcher({**СОБЫТИЕ, "kind": "METADATA_UPDATED"})
        assert событие.event_type is EventType.TITLE_UPDATED

    def test_озвучка_есть_в_контракте(self):
        """Наблюдатель выпускает её на живой витрине; контракт её не знал."""
        assert EventType("VOICEOVER_ADDED")
        схема = json.loads(
            (ROOT / "schemas/site-engine/content-event.schema.json").read_text(encoding="utf-8")
        )
        assert "VOICEOVER_ADDED" in схема["properties"]["event_type"]["enum"]


class TestСвойстваПеревода:
    def test_времена_остаются_разными(self):
        событие = event_from_watcher(СОБЫТИЕ)
        assert событие.observed_at.tzinfo is not None
        assert событие.provider_timestamp is not None
        assert событие.observed_at != событие.provider_timestamp

    def test_время_приводится_к_utc(self):
        событие = event_from_watcher(СОБЫТИЕ)
        assert событие.observed_at.tzinfo == timezone.utc

    def test_без_времени_наблюдения_событие_не_создать(self):
        """Подставить «сейчас» значило бы записать другую метку."""
        без = {k: v for k, v in СОБЫТИЕ.items() if k != "observedAt"}
        with pytest.raises(ContractError, match="времени наблюдения"):
            event_from_watcher(без)

    def test_без_идентификатора_тайтла_событие_не_создать(self):
        без = {k: v for k, v in СОБЫТИЕ.items() if k != "titleId"}
        with pytest.raises(ContractError, match="идентификатора"):
            event_from_watcher(без)

    def test_ключ_идемпотентности_устойчив(self):
        """Одна и та же серия, увиденная дважды, — одно событие."""
        первый = event_from_watcher(СОБЫТИЕ)
        второй = event_from_watcher({**СОБЫТИЕ, "observedAt": "2026-08-30T01:02:03Z"})
        assert первый.idempotency_key == второй.idempotency_key

    def test_разные_серии_дают_разные_ключи(self):
        девятая = event_from_watcher(СОБЫТИЕ)
        десятая = event_from_watcher({**СОБЫТИЕ, "episode": 10, "to": 10})
        assert девятая.idempotency_key != десятая.idempotency_key

    def test_отпечаток_переносится_как_отпечаток(self):
        событие = event_from_watcher(СОБЫТИЕ)
        assert событие.source_fingerprint == {"value": "1:9:9"}

    def test_выход_серии_сбрасывает_полку_новых_серий(self):
        assert "shelf:new-episodes" in event_from_watcher(СОБЫТИЕ).cache_tags()

    def test_озвучка_не_трогает_полку_новых_серий(self):
        """Серии от новой озвучки не прибавляется."""
        событие = event_from_watcher({**СОБЫТИЕ, "kind": "VOICEOVER_ADDED"})
        assert событие.cache_tags() == ("title",)


class TestЛента:
    def test_битая_строка_это_отказ(self, tmp_path: Path):
        путь = tmp_path / "events.jsonl"
        путь.write_text(json.dumps(СОБЫТИЕ) + "\nне json\n", encoding="utf-8")
        with pytest.raises(ContractError, match="не разбирается"):
            list(YummyEventLog(путь).read())

    def test_пустые_строки_пропускаются(self, tmp_path: Path):
        путь = tmp_path / "events.jsonl"
        путь.write_text("\n" + json.dumps(СОБЫТИЕ) + "\n\n", encoding="utf-8")
        assert len(list(YummyEventLog(путь).read())) == 1

    def test_нестрогий_разбор_переживает_устаревший_род(self, tmp_path: Path):
        путь = tmp_path / "events.jsonl"
        путь.write_text(
            json.dumps({**СОБЫТИЕ, "kind": "ДАВНО_УБРАННЫЙ"}) + "\n"
            + json.dumps(СОБЫТИЕ) + "\n",
            encoding="utf-8",
        )
        assert len(list(YummyEventLog(путь).read(strict=False))) == 1

    def test_отсутствие_ленты_названо_прямо(self, tmp_path: Path):
        from factory.site_engine.providers import ProviderUnavailable

        with pytest.raises(ProviderUnavailable):
            list(YummyEventLog(tmp_path / "нет.jsonl").read())
