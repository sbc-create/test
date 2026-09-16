"""Очередь по витрине: чужой застой не держит остальных.

Одна общая очередь означала, что зависшая отрисовка Lords держала всё: Yummy,
Zona и Animedia ждали её часами, хотя ни одна не пересекается с ней ни файлом,
ни службой. Логическая зависимость там, где нет физической, — выдуманное
ограничение, и стоило оно суток.

Физическое ограничение ровно одно: памяти хватает на один тяжёлый рендер. Оно
выражено отдельным семафором, а не общей очередью, и проверки, DNS и nginx его
не берут вовсе.
"""

from __future__ import annotations

import json

import pytest

from automation.deploy import lords_queue as q


def заявка(ид: str, rev: str = "a" * 40, art: str = "1" * 64, gen: int = 1) -> dict:
    return {"deployment_id": ид, "revision": rev, "artifact_sha256": art,
            "generation": gen, "sites": ["lords-02"]}


class TestОчередьПоВитрине:
    def test_витрины_не_видят_очередей_друг_друга(self, tmp_path):
        q.поставить("lords-02", заявка("a1"), корень=tmp_path)
        q.поставить("yummy-biz", заявка("b1"), корень=tmp_path)
        assert q.ожидает("lords-02", корень=tmp_path) == ["a1"]
        assert q.ожидает("yummy-biz", корень=tmp_path) == ["b1"]

    def test_снятие_у_одной_не_трогает_другую(self, tmp_path):
        q.поставить("lords-02", заявка("a1"), корень=tmp_path)
        q.поставить("yummy-biz", заявка("b1"), корень=tmp_path)
        q.снять("lords-02", корень=tmp_path)
        assert q.ожидает("lords-02", корень=tmp_path) == []
        assert q.ожидает("yummy-biz", корень=tmp_path) == ["b1"]

    def test_имя_витрины_с_путём_отвергается(self, tmp_path):
        with pytest.raises(q.QueueError):
            q.поставить("../etc", заявка("a1"), корень=tmp_path)


class TestЗамкиНеПересекаются:
    def test_замок_витрины_не_держит_другую(self, tmp_path):
        with q.замок("lords-02", корень=tmp_path):
            with q.замок("yummy-biz", корень=tmp_path):
                pass  # обе взяты одновременно — значит независимы

    def test_повторный_захват_той_же_витрины_отвергается(self, tmp_path):
        with q.замок("lords-02", корень=tmp_path):
            with pytest.raises(q.QueueError):
                with q.замок("lords-02", корень=tmp_path):
                    pass

    def test_семафор_тяжёлых_один_на_всех(self, tmp_path):
        """Памяти хватает на один тяжёлый рендер — это измерено, а не мнение."""
        with q.замок(q.СЕМАФОР_ТЯЖЁЛЫХ, корень=tmp_path):
            with pytest.raises(q.QueueError):
                with q.замок(q.СЕМАФОР_ТЯЖЁЛЫХ, корень=tmp_path):
                    pass

    def test_проверки_не_берут_семафор_тяжёлых(self, tmp_path):
        """Пока идёт рендер, DNS, nginx и приёмка обязаны работать."""
        with q.замок(q.СЕМАФОР_ТЯЖЁЛЫХ, корень=tmp_path):
            with q.замок("dns-zonafilm", корень=tmp_path):
                with q.замок("nginx-animedia", корень=tmp_path):
                    pass


class TestСлияниеДубликатов:
    def test_точный_дубликат_поглощается(self, tmp_path):
        q.поставить("lords-02", заявка("a1"), корень=tmp_path)
        итог = q.поставить("lords-02", заявка("a2"), корень=tmp_path)
        assert итог["queued"] is False and итог["merged_into"] == "a1"
        assert q.ожидает("lords-02", корень=tmp_path) == ["a1"]

    def test_другая_ревизия_это_другая_работа(self, tmp_path):
        q.поставить("lords-02", заявка("a1"), корень=tmp_path)
        итог = q.поставить("lords-02", заявка("a2", rev="b" * 40), корень=tmp_path)
        assert итог["queued"] is True
        assert q.ожидает("lords-02", корень=tmp_path) == ["a1", "a2"]

    def test_другое_поколение_это_другая_работа(self, tmp_path):
        q.поставить("lords-02", заявка("a1", gen=1), корень=tmp_path)
        итог = q.поставить("lords-02", заявка("a2", gen=2), корень=tmp_path)
        assert итог["queued"] is True


class TestСнятоеНеВоскресает:
    def test_снятая_заявка_не_возвращается_в_очередь(self, tmp_path):
        """Возврат снятой заявки и есть воскрешение после падения приёмщика."""
        q.поставить("lords-02", заявка("a1"), корень=tmp_path)
        снято = q.снять("lords-02", корень=tmp_path)
        assert снято["deployment_id"] == "a1"
        assert q.снять("lords-02", корень=tmp_path) is None
        assert q.ожидает("lords-02", корень=tmp_path) == []

    def test_снятое_сохраняется_для_отчёта(self, tmp_path):
        q.поставить("lords-02", заявка("a1"), корень=tmp_path)
        q.снять("lords-02", корень=tmp_path)
        принятые = list((tmp_path / "taken" / "lords-02").glob("a1.*.json"))
        assert len(принятые) == 1
        assert json.loads(принятые[0].read_text(encoding="utf-8"))["deployment_id"] == "a1"

    def test_пустая_очередь_даёт_none_а_не_ошибку(self, tmp_path):
        assert q.снять("lords-02", корень=tmp_path) is None
