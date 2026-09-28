"""Быстрый путь: обнаружение изменившихся произведений и отпечаток входа."""
from __future__ import annotations

import json

from factory.lords.fast_path import compare_titles, title_digests
from factory.site_engine.fingerprint import enrichment_digest, mapping_digest


class Каталог:
    def __init__(self, пары):
        self.titles = [type("T", (), {"external_id": e, "slug": s})() for e, s in пары]


def записи(*пары):
    return [{"external_id": e, "name": n, "poster_url": f"p/{n}.webp"} for e, n in пары]


class TestОбнаружениеИзменений:
    def test_одинаковые_снимки_не_дают_изменений(self):
        е = записи(("1", "Альфа"), ("2", "Бета"))
        к = Каталог([("1", "alfa"), ("2", "beta")])
        снимок = title_digests(е, к)
        итог = compare_titles(снимок, снимок)
        assert not итог.any
        assert (итог.added, итог.modified, итог.removed) == (0, 0, 0)

    def test_изменение_одного_называет_один_слаг(self):
        к = Каталог([("1", "alfa"), ("2", "beta")])
        было = title_digests(записи(("1", "Альфа"), ("2", "Бета")), к)
        стало = title_digests(
            [{"external_id": "1", "name": "Альфа", "poster_url": "p/ДРУГОЙ.webp"},
             {"external_id": "2", "name": "Бета", "poster_url": "p/Бета.webp"}], к)
        итог = compare_titles(было, стало)
        assert итог.modified == 1
        assert итог.changed_slugs == ("alfa",)

    def test_добавленное_и_удалённое_различаются(self):
        было = title_digests(записи(("1", "Альфа")), Каталог([("1", "alfa")]))
        стало = title_digests(записи(("2", "Бета")), Каталог([("2", "beta")]))
        итог = compare_titles(было, стало)
        assert итог.added == 1 and итог.removed == 1
        assert итог.changed_slugs == ("beta",)
        assert итог.removed_slugs == ("alfa",)

    def test_служебные_поля_не_считаются_изменением(self):
        """Иначе «изменилось» срабатывало бы на каждом прогоне и обесценило проверку."""
        к = Каталог([("1", "alfa")])
        было = title_digests([{"external_id": "1", "name": "А", "updated_at": "2026-01-01"}], к)
        стало = title_digests([{"external_id": "1", "name": "А", "updated_at": "2026-09-09"}], к)
        assert not compare_titles(было, стало).any

    def test_запись_без_идентификатора_пропускается(self):
        снимок = title_digests([{"name": "без идентификатора"}], Каталог([]))
        assert снимок == {}


class TestОтпечатокОбогащения:
    def test_время_выборки_не_меняет_отпечаток(self, tmp_path):
        """Записи кэша хранят fetched_at; отпечаток по сырому содержимому менялся
        бы каждый прогон и обесценил бы ворота."""
        поля = ("description", "genres")
        (tmp_path / "a.json").write_text(json.dumps({
            "fetched_at": 1.0,
            "detail": {"_fetched_at": 1.0, "description": "текст", "genres": ["драма"]},
        }), encoding="utf-8")
        первый = enrichment_digest(tmp_path, поля)
        (tmp_path / "a.json").write_text(json.dumps({
            "fetched_at": 999.0,
            "detail": {"_fetched_at": 999.0, "description": "текст", "genres": ["драма"]},
        }), encoding="utf-8")
        assert enrichment_digest(tmp_path, поля) == первый

    def test_изменение_содержания_меняет_отпечаток(self, tmp_path):
        поля = ("description",)
        (tmp_path / "a.json").write_text(json.dumps({"detail": {"description": "было"}}), encoding="utf-8")
        было = enrichment_digest(tmp_path, поля)
        (tmp_path / "a.json").write_text(json.dumps({"detail": {"description": "стало"}}), encoding="utf-8")
        assert enrichment_digest(tmp_path, поля) != было

    def test_нечитаемая_запись_видна_в_отпечатке(self, tmp_path):
        """Молча пропустить её — значит объявить вход неизменившимся при
        изменившемся кэше."""
        (tmp_path / "a.json").write_text('{"detail": {"description": "x"}}', encoding="utf-8")
        целый = enrichment_digest(tmp_path, ("description",))
        (tmp_path / "b.json").write_text("не json", encoding="utf-8")
        assert enrichment_digest(tmp_path, ("description",)) != целый

    def test_отсутствующий_каталог_даёт_пустой_отпечаток(self, tmp_path):
        assert enrichment_digest(tmp_path / "нет", ("x",)) == ""


class TestОтпечатокСловаря:
    def test_время_проверки_не_влияет(self, tmp_path):
        файл = tmp_path / "playability.json"
        файл.write_text(json.dumps({"kp:1": {"playable": True, "checked_at": 1.0}}), encoding="utf-8")
        первый = mapping_digest(файл, keep=("playable",))
        файл.write_text(json.dumps({"kp:1": {"playable": True, "checked_at": 2.0}}), encoding="utf-8")
        assert mapping_digest(файл, keep=("playable",)) == первый

    def test_смена_признака_меняет_отпечаток(self, tmp_path):
        файл = tmp_path / "playability.json"
        файл.write_text(json.dumps({"kp:1": {"playable": True, "checked_at": 1.0}}), encoding="utf-8")
        было = mapping_digest(файл, keep=("playable",))
        файл.write_text(json.dumps({"kp:1": {"playable": False, "checked_at": 1.0}}), encoding="utf-8")
        assert mapping_digest(файл, keep=("playable",)) != было

    def test_отсутствующий_файл_даёт_пустой_отпечаток(self, tmp_path):
        assert mapping_digest(tmp_path / "нет.json") == ""


class TestЧастиОтпечатка:
    def test_обогащение_и_воспроизводимость_входят_в_отпечаток(self):
        """Без них ворота отвечали «не надо» при изменившихся страницах."""
        from factory.site_engine.fingerprint import PARTS

        assert "enrichment" in PARTS
        assert "playability" in PARTS
