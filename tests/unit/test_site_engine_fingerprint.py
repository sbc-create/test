"""Отпечаток входных данных: сравнение до дорогой работы.

Главная опасность здесь — отпечаток, который что-то не учитывает. Он не
проявляется как ошибка: витрина просто остаётся со старой вёрсткой, а прогон
отчитывается, что менять нечего. Поэтому большая часть проверок ниже — о том,
что изменение НЕ прячется.
"""
import json
from pathlib import Path

import pytest

from factory.site_engine.fingerprint import (
    PARTS,
    RenderInputs,
    catalog_digest,
    compare,
    digest,
    load,
    save,
    tree_digest,
)


def входы(**kw) -> RenderInputs:
    база = {
        "catalog": "c1",
        "renderer_version": "r1",
        "template_version": "t1",
        "site_profile": "p1",
        "shelf_configuration": "s1",
        "route_registry": "rr1",
    }
    база.update(kw)
    return RenderInputs(**база)


class TestДетерминированность:
    def test_порядок_полей_json_не_влияет(self):
        assert digest({"а": 1, "б": 2}) == digest({"б": 2, "а": 1})

    def test_порядок_записей_каталога_не_влияет(self):
        записи = [{"external_id": str(i), "name": f"Т{i}"} for i in range(20)]
        assert catalog_digest(записи) == catalog_digest(list(reversed(записи)))

    def test_один_и_тот_же_вход_даёт_один_отпечаток(self):
        assert входы().fingerprint() == входы().fingerprint()

    def test_служебные_поля_каталога_не_влияют(self):
        """Иначе отпечаток менялся бы каждый прогон и обесценил бы проверку."""
        а = [{"external_id": "1", "name": "Т", "fetched_at_ms": 111}]
        б = [{"external_id": "1", "name": "Т", "fetched_at_ms": 999}]
        assert catalog_digest(а) == catalog_digest(б)


class TestИзменениеНеПрячется:
    @pytest.mark.parametrize("часть", PARTS)
    def test_каждая_часть_влияет_на_отпечаток(self, часть):
        """Часть, не влияющая на отпечаток, — дыра, а не оптимизация."""
        базовый = входы()
        изменённый = RenderInputs(**(базовый.as_dict() | {часть: "другое"}))
        assert базовый.fingerprint() != изменённый.fingerprint(), (
            f"изменение {часть} не отражается в отпечатке"
        )

    def test_изменение_каталога_видно(self):
        а = [{"external_id": "1", "name": "Было"}]
        б = [{"external_id": "1", "name": "Стало"}]
        assert catalog_digest(а) != catalog_digest(б)

    def test_отпечаток_каталога_не_скрывает_правку_шаблона(self):
        """Именно эта ошибка оставила бы витрину со старой вёрсткой."""
        одинаковый_каталог = входы(template_version="t1")
        новый_шаблон = входы(template_version="t2")
        assert одинаковый_каталог.fingerprint() != новый_шаблон.fingerprint()
        assert compare(одинаковый_каталог, новый_шаблон).changed == ("template_version",)

    def test_новая_серия_видна_через_счётчики(self):
        было = [{"external_id": "1", "name": "Т", "available_episodes_count": 8}]
        стало = [{"external_id": "1", "name": "Т", "available_episodes_count": 9}]
        assert catalog_digest(было) != catalog_digest(стало)


class TestСравнение:
    def test_ничего_не_изменилось(self):
        разница = compare(входы(), входы())
        assert not разница.any_change
        assert разница.describe() == "ничего не изменилось"

    def test_первый_прогон_это_неизвестность_а_не_изменение_всего(self):
        разница = compare(None, входы())
        assert разница.changed == PARTS
        assert разница.needs_full_rebuild

    def test_изменение_каталога_не_требует_полной_пересборки(self):
        разница = compare(входы(), входы(catalog="c2"))
        assert разница.changed == ("catalog",)
        assert not разница.needs_full_rebuild

    def test_изменение_реестра_адресов_не_требует_полной_пересборки(self):
        assert not compare(входы(), входы(route_registry="rr2")).needs_full_rebuild

    @pytest.mark.parametrize(
        "часть",
        ["renderer_version", "template_version", "schema_version", "site_profile",
         "shelf_configuration", "seo_contract_version"],
    )
    def test_общие_изменения_требуют_полной_пересборки(self, часть):
        """Эти части влияют на каждую страницу — частичная сборка соврала бы."""
        разница = compare(входы(), RenderInputs(**(входы().as_dict() | {часть: "иное"})))
        assert разница.needs_full_rebuild

    def test_разница_называет_изменившееся(self):
        разница = compare(входы(), входы(catalog="c2", route_registry="rr2"))
        assert set(разница.changed) == {"catalog", "route_registry"}
        assert "catalog" in разница.describe()


class TestДеревоФайлов:
    def test_содержимое_влияет(self, tmp_path: Path):
        (tmp_path / "a.html").write_text("один", encoding="utf-8")
        было = tree_digest(tmp_path)
        (tmp_path / "a.html").write_text("два", encoding="utf-8")
        assert tree_digest(tmp_path) != было

    def test_время_изменения_не_влияет(self, tmp_path: Path):
        """Скопированный файл — тот же файл; пересобирать из-за метки незачем."""
        import os

        (tmp_path / "a.html").write_text("один", encoding="utf-8")
        было = tree_digest(tmp_path)
        os.utime(tmp_path / "a.html", (0, 0))
        assert tree_digest(tmp_path) == было

    def test_имя_файла_влияет(self, tmp_path: Path):
        (tmp_path / "a.html").write_text("один", encoding="utf-8")
        было = tree_digest(tmp_path)
        (tmp_path / "a.html").rename(tmp_path / "b.html")
        assert tree_digest(tmp_path) != было

    def test_отсутствующее_дерево_не_роняет(self, tmp_path: Path):
        assert tree_digest(tmp_path / "нет") == digest(None)


class TestХранение:
    def test_запись_и_чтение(self, tmp_path: Path):
        файл = save(tmp_path / "fp.json", входы())
        снова = load(файл)
        assert снова.fingerprint() == входы().fingerprint()

    def test_отпечаток_сохраняется_рядом(self, tmp_path: Path):
        файл = save(tmp_path / "fp.json", входы())
        raw = json.loads(файл.read_text(encoding="utf-8"))
        assert raw["fingerprint"] == входы().fingerprint()

    def test_чужая_версия_схемы_даёт_пересборку_а_не_ошибку(self, tmp_path: Path):
        файл = tmp_path / "fp.json"
        файл.write_text(json.dumps({"schema_version": "0.1"}), encoding="utf-8")
        assert load(файл) is None

    def test_запись_атомарна(self, tmp_path: Path):
        save(tmp_path / "fp.json", входы())
        assert not list(tmp_path.glob("*.tmp"))
