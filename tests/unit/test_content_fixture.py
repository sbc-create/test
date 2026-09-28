"""REQ-CONTENT-FIXTURE: содержимое витрины из её же пакета.

Три семейства из пяти объявляют источник содержимого `fixture` — набор записей,
лежащий в пакете самой витрины. Движок такой источник читать не умел: каталог
он берёт только из кэша поставщика, а кэша у этих витрин нет и быть не должно.

Отсюда пробел: админка семейства работает целиком, а управлять ей нечем —
каталог пуст, очередь разбора пуста, публиковать нечего.

Три правила.

**Отпечаток проверяется, если объявлен.** Пакет объявляет sha256 набора; чтение
без сверки означает, что подменённый набор попадёт на витрину молча.

**Отсутствующий набор — это отказ, а не пустой каталог.** Пустой каталог
отвечает 200 и выглядит исправной витриной без материалов.

**Перенос ничего не выдумывает.** Поля, которых в наборе нет, остаются пустыми;
записи без идентификатора отвергаются целиком, а не получают выдуманный.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from factory.paths import PATHS

САЙТ = "fx-site"
REPO = Path(__file__).resolve().parents[2]
ENV = {"SITE_ENGINE_CATALOG_DIR": "var/catalog-cache"}

НАБОР = {
    "schema_version": 1,
    "kind": "fixture",
    "categories": [{"slug": "lekcii", "title": "Лекции"}],
    "titles": [
        {"id": "fx-1", "title": "Первая", "kind": "movie", "year": 2020,
         "category": "lekcii"},
        {"id": "fx-2", "title": "Вторая", "kind": "series", "year": 2021,
         "category": "lekcii"},
    ],
}


def _пакет(корень: Path, *, sha: str | None = None) -> None:
    место = корень / "sites" / САЙТ
    (место / "content").mkdir(parents=True, exist_ok=True)
    тело = json.dumps(НАБОР, ensure_ascii=False, indent=2)
    (место / "content" / "catalog.json").write_text(тело, encoding="utf-8")
    отпечаток = sha if sha is not None else hashlib.sha256(тело.encode("utf-8")).hexdigest()
    (место / "package.yaml").write_text(
        "site_id: " + САЙТ + "\n"
        "content_source:\n"
        "  kind: fixture\n"
        "  rights_confirmed: true\n"
        "content_package_ref: content/catalog.json\n"
        "content_package_sha256: " + отпечаток + "\n",
        encoding="utf-8",
    )


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    профили = tmp_path / "config" / "site-profiles"
    профили.mkdir(parents=True)
    (профили / f"{САЙТ}.json").write_text(
        json.dumps({"site_id": САЙТ, "domains": [f"{САЙТ}.test"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / "var" / "catalog-cache").mkdir(parents=True)
    for под in ("var/state", "var/audit", "var/locks"):
        (tmp_path / под).mkdir(parents=True, exist_ok=True)
    return tmp_path


class TestПеренос:
    def test_записи_попадают_в_каталог_движка(self, sandbox):
        from factory.site_engine import content_fixture

        _пакет(sandbox)
        итог = content_fixture.ingest(sandbox, САЙТ, env=ENV)
        assert итог["records"] == 2
        файл = sandbox / "var" / "catalog-cache" / f"{САЙТ}.json"
        assert файл.is_file()
        данные = json.loads(файл.read_text(encoding="utf-8"))
        внешние = {з["external_id"] for з in данные["items"]}
        assert внешние == {"fx-1", "fx-2"}

    def test_вид_и_год_переносятся(self, sandbox):
        from factory.site_engine import content_fixture

        _пакет(sandbox)
        content_fixture.ingest(sandbox, САЙТ, env=ENV)
        данные = json.loads(
            (sandbox / "var" / "catalog-cache" / f"{САЙТ}.json").read_text(encoding="utf-8")
        )
        запись = next(з for з in данные["items"] if з["external_id"] == "fx-2")
        assert запись["name"] == "Вторая"
        assert запись["type"] == "series"
        assert запись["year"] == 2021

    def test_происхождение_записано(self, sandbox):
        from factory.site_engine import content_fixture

        _пакет(sandbox)
        content_fixture.ingest(sandbox, САЙТ, env=ENV)
        данные = json.loads(
            (sandbox / "var" / "catalog-cache" / f"{САЙТ}.json").read_text(encoding="utf-8")
        )
        assert данные["source"].startswith("fixture:")
        assert данные["fetched_at_ms"] > 0

    def test_подменённый_набор_отвергается(self, sandbox):
        """Отпечаток объявлен — значит, он и проверяется."""
        from factory.site_engine import content_fixture

        _пакет(sandbox, sha="0" * 64)
        with pytest.raises(content_fixture.FixtureError) as ошибка:
            content_fixture.ingest(sandbox, САЙТ, env=ENV)
        assert "отпечаток" in str(ошибка.value).lower()

    def test_отсутствующий_набор_это_отказ(self, sandbox):
        from factory.site_engine import content_fixture

        (sandbox / "sites" / САЙТ).mkdir(parents=True)
        (sandbox / "sites" / САЙТ / "package.yaml").write_text(
            "site_id: " + САЙТ + "\ncontent_source:\n  kind: fixture\n", encoding="utf-8"
        )
        with pytest.raises(content_fixture.FixtureError):
            content_fixture.ingest(sandbox, САЙТ, env=ENV)
        assert not (sandbox / "var" / "catalog-cache" / f"{САЙТ}.json").exists(), (
            "пустой каталог на месте отсутствующего набора выглядит исправной витриной"
        )

    def test_запись_без_идентификатора_отвергается(self, sandbox):
        from factory.site_engine import content_fixture

        _пакет(sandbox)
        место = sandbox / "sites" / САЙТ / "content" / "catalog.json"
        плохой = dict(НАБОР)
        плохой["titles"] = [{"title": "Без идентификатора"}]
        тело = json.dumps(плохой, ensure_ascii=False, indent=2)
        место.write_text(тело, encoding="utf-8")
        (sandbox / "sites" / САЙТ / "package.yaml").write_text(
            "site_id: " + САЙТ + "\ncontent_source:\n  kind: fixture\n"
            "content_package_ref: content/catalog.json\n"
            "content_package_sha256: "
            + hashlib.sha256(тело.encode("utf-8")).hexdigest() + "\n",
            encoding="utf-8",
        )
        with pytest.raises(content_fixture.FixtureError) as ошибка:
            content_fixture.ingest(sandbox, САЙТ, env=ENV)
        assert "идентификатор" in str(ошибка.value).lower()

    def test_чужой_источник_не_переносится(self, sandbox):
        """У витрины поставщика свой путь: подменять его фикстурой нельзя."""
        from factory.site_engine import content_fixture

        (sandbox / "sites" / САЙТ).mkdir(parents=True)
        (sandbox / "sites" / САЙТ / "package.yaml").write_text(
            "site_id: " + САЙТ + "\ncontent_source:\n  kind: cdnvideohub\n", encoding="utf-8"
        )
        with pytest.raises(content_fixture.FixtureError) as ошибка:
            content_fixture.ingest(sandbox, САЙТ, env=ENV)
        assert "fixture" in str(ошибка.value)


class TestМаршрут:
    def test_перенос_доступен_через_api(self, sandbox):
        from factory.site_engine.api.control import ControlApi

        _пакет(sandbox)
        api = ControlApi(
            root=sandbox,
            env={
                "SITE_ENGINE_CONTROL_WRITES": "1",
                "SITE_ENGINE_CONTROL_TOKENS": "t=read,jobs:write",
                **ENV,
            },
        )
        ответ = api.handle(
            "POST", "/api/v1/content-ingest",
            headers={"Authorization": "Bearer t"}, body={"siteId": САЙТ},
        )
        assert ответ.status == 200, ответ.body
        assert ответ.body["records"] == 2

    def test_без_права_заданий_отказ(self, sandbox):
        from factory.site_engine.api.control import ControlApi

        _пакет(sandbox)
        api = ControlApi(
            root=sandbox,
            env={
                "SITE_ENGINE_CONTROL_WRITES": "1",
                "SITE_ENGINE_CONTROL_TOKENS": "ro=read",
                **ENV,
            },
        )
        ответ = api.handle(
            "POST", "/api/v1/content-ingest",
            headers={"Authorization": "Bearer ro"}, body={"siteId": САЙТ},
        )
        assert ответ.status == 403
