"""Отказ обогащения оставляет след, а не тишину.

Быстрый путь накладывает на каталог два улучшения: сохранённые detail-данные и
признак воспроизводимости. Оба обёрнуты в `except Exception: pass`, и это
намеренное решение — улучшение не должно ронять сборку.

Но «не ронять» и «не сообщать» — разные вещи, а здесь они были одним.

Цена уже известна. Признак воспроизводимости управляет верхней каруселью: при
рассогласовании `playable is None` полка исчезала со всех витрин разом.
Сборка при этом сообщала об успехе, страницы выходили беднее релиза, и
отличить «данных не было» от «шаг упал» было нельзя ничем.

Проверки требуют следа: сборка вправе продолжиться, но обязана сказать, что
именно не состоялось и почему.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.lords import fast_path  # noqa: E402


class TestОтказОставляетСлед:
    def test_отказ_обогащения_назван(self, monkeypatch):
        def падает(*args, **kwargs):
            raise RuntimeError("кэш detail-данных недоступен")

        monkeypatch.setattr(fast_path.detail_enrichment, "enrich_items", падает)
        entries, degraded = fast_path._apply_cached_enrichment([{"id": 1}], "lords-01")

        assert entries == [{"id": 1}], "записи обязаны вернуться, сборка не падает"
        assert degraded, "отказ обогащения не оставил следа"
        assert degraded[0]["stage"] == "detail_enrichment"
        assert "кэш detail-данных недоступен" in degraded[0]["error"]

    def test_отказ_признака_воспроизведения_назван(self, monkeypatch):
        def падает(*args, **kwargs):
            raise RuntimeError("нет издателя")

        monkeypatch.setattr(fast_path.playability_mod, "annotate", падает)
        monkeypatch.setattr(fast_path.live_site, "publisher_id_for", lambda site_id: "1")
        _, degraded = fast_path._apply_cached_enrichment([{"id": 1}], "lords-01")

        stages = [d["stage"] for d in degraded]
        assert "playability" in stages, (
            "именно рассогласование этого признака однажды убрало верхнюю "
            "карусель со всех витрин — молча")

    def test_успешный_проход_следа_не_оставляет(self, monkeypatch):
        monkeypatch.setattr(fast_path.detail_enrichment, "enrich_items",
                            lambda entries, **kw: (entries, None))
        monkeypatch.setattr(fast_path.live_site, "publisher_id_for", lambda site_id: None)
        _, degraded = fast_path._apply_cached_enrichment([{"id": 1}], "lords-01")
        assert degraded == [], "успешная сборка не должна сообщать о деградации"


class TestСледДоходитДоОтчёта:
    def test_отчёт_сборки_называет_деградацию(self, monkeypatch):
        """Список, никуда не попавший, — та же тишина, только дороже."""
        assert hasattr(fast_path, "DEGRADED_KEY"), (
            "отчёт обязан иметь поле для деградации, иначе след теряется в вызове")
