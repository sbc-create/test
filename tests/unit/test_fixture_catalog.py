"""Набор записей стенда: проверяется то, чем он может соврать.

Набор нужен трём семействам, чей пакет объявляет источник `fixture`. Он
синтетический по определению, и именно поэтому у него есть ровно три
обязанности: объявить отпечаток, который сходится; дать каждой записи
идентификатор; и оставить в данных настоящее расхождение — иначе очередь
разбора окажется пустой, и «зелёная» приёмка докажет только то, что решать
было нечего.
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

РЕПО = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(РЕПО / "tests" / "tools"))

import fixture_catalog  # noqa: E402

from factory.site_engine.catalog_identity import decide  # noqa: E402


@pytest.fixture()
def стенд(tmp_path):
    (tmp_path / "sites" / "site-a").mkdir(parents=True)
    shutil.copy(РЕПО / "sites" / "site-a" / "package.yaml",
                tmp_path / "sites" / "site-a" / "package.yaml")
    fixture_catalog.записать(tmp_path, РЕПО, "site-a", 40)
    return tmp_path


def _пакет(стенд):
    return yaml.safe_load(
        (стенд / "sites" / "site-a" / "package.yaml").read_text(encoding="utf-8"))


def _набор(стенд):
    return json.loads(
        (стенд / "sites" / "site-a" / "content" / "catalog.json").read_text(encoding="utf-8"))


def test_отпечаток_в_пакете_сходится_с_файлом(стенд):
    тело = (стенд / "sites" / "site-a" / "content" / "catalog.json").read_text(encoding="utf-8")
    assert _пакет(стенд)["content_package_sha256"] == hashlib.sha256(
        тело.encode("utf-8")).hexdigest()


def test_ссылка_на_набор_объявлена(стенд):
    assert _пакет(стенд)["content_package_ref"] == "content/catalog.json"


def test_у_каждой_записи_есть_идентификатор(стенд):
    записи = _набор(стенд)["titles"]
    assert len(записи) == 40
    assert all(з["id"] for з in записи)
    assert len({з["id"] for з in записи}) == 40


def test_происхождение_названо_в_самом_наборе(стенд):
    assert "стенд" in _набор(стенд)["provenance"].lower()


def test_в_наборе_есть_настоящее_расхождение(стенд):
    спорных = 0
    for з in _набор(стенд)["titles"]:
        решение = decide(provider_type=з["type"], tags=з["tags"], entity_id=з["id"], root=стенд)
        спорных += bool(решение.conflicts)
    assert спорных > 0, "без расхождений очередь разбора пуста и утверждать нечего"


def test_записи_не_выдают_себя_за_поставщика(стенд):
    # Ни одна запись не несёт внешних идентификаторов чужих каталогов: набор
    # стенда, попавший в сопоставление как настоящий, испортил бы соединение.
    for з in _набор(стенд)["titles"]:
        assert set(з["external_ids"]) == {"stand"}
        assert з["playback"] is None


def test_пакет_витрины_в_репозитории_не_тронут():
    исходный = yaml.safe_load(
        (РЕПО / "sites" / "site-a" / "package.yaml").read_text(encoding="utf-8"))
    assert исходный["content_package_ref"] is None
    assert not (РЕПО / "sites" / "site-a" / "content").exists()
