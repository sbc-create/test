"""REQ-FLEET-REGISTRY: у каждого показателя есть источник, время и состояние.

Центр управления существует ради одного: увидеть весь флот, не открывая семь
разных мест. Опасность у такого экрана ровно одна и она известна заранее —
показать неизвестное как ноль. «Ноль посетителей» и «счётчик не подключён»
выглядят одинаково, а означают противоположное: первое — что сайт никто не
открыл, второе — что мы не спрашивали.

Поэтому здесь проверяется не наличие полей, а честность их состояний.
"""

from __future__ import annotations

import json
import time

import pytest

from factory.site_engine import fleet_registry as fr


@pytest.fixture()
def корень(tmp_path):
    (tmp_path / "config" / "site-profiles").mkdir(parents=True)
    (tmp_path / "sites" / "site-1").mkdir(parents=True)
    (tmp_path / "config" / "site-profiles" / "site-1.json").write_text(
        json.dumps({"site_id": "site-1", "domains": ["site-1.test"],
                    "brand": {"name": "Витрина один"}}), encoding="utf-8")
    (tmp_path / "sites" / "site-1" / "package.yaml").write_text(
        "theme_ref: family_a\n"
        "environment: staging\n"
        "production_authorized: false\n"
        "seo_indexing_enabled: false\n"
        "content_source:\n  kind: provider\n"
        "analytics_profile:\n  counter_id: 12345\n"
        "runtime:\n  database:\n    password_secret_ref: file:var/db/pass\n",
        encoding="utf-8")
    рантайм = tmp_path / "runtime" / "site-1"
    релиз = рантайм / "releases" / "rel0001"
    релиз.mkdir(parents=True)
    (релиз / "release-manifest.json").write_text(json.dumps({
        "tenant_id": "site-1", "theme": "family_a", "template_digest": "a" * 64,
        "renderer_revision": "b" * 40, "tooling_revision": "c" * 40,
        "content_snapshot_id": "snap-1", "content_count": 100,
        "rollback_target": "rel0000", "release_reason": "content-refresh",
        "created_at": "2026-09-06T10:00:00Z",
    }), encoding="utf-8")
    (рантайм / "current").symlink_to(релиз)
    (tmp_path / "config" / "fleet-sources.yaml").write_text(
        f"version: 1\nruntime:\n  root: {tmp_path / 'runtime'}\n"
        "  manifest: release-manifest.json\nstaleness:\n  seconds: 3600\n",
        encoding="utf-8")
    return tmp_path


def _поле(запись, имя):
    return запись.fields[имя]


def test_объявленное_читается_с_источником(корень):
    з = fr.site_record(корень, "site-1")
    assert _поле(з, "templateFamily").value == "family_a"
    assert _поле(з, "templateFamily").state is fr.State.CONNECTED
    assert _поле(з, "templateFamily").source.startswith("site-package")
    assert _поле(з, "templateDigest").value == "a" * 64
    assert _поле(з, "currentRelease").value == "rel0001"


def test_неподключённый_источник_не_превращается_в_ноль(корень):
    з = fr.site_record(корень, "site-1")
    посетители = _поле(з, "visitors")
    assert посетители.value is None, "неизвестное показано числом"
    assert посетители.state is fr.State.NOT_CONNECTED
    assert посетители.reason


def test_несвежее_измерение_называется_несвежим(корень):
    давно = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 8 * 3600))
    (корень / fr.НАБЛЮДЕНИЯ).mkdir(parents=True)
    (корень / fr.НАБЛЮДЕНИЯ / "site-1.json").write_text(json.dumps({
        "visitors": {"value": 42, "state": "CONNECTED", "source": "metrika",
                     "observedAt": давно},
    }), encoding="utf-8")
    з = fr.site_record(корень, "site-1")
    посетители = _поле(з, "visitors")
    assert посетители.state is fr.State.STALE
    assert посетители.value == 42, "несвежее значение выброшено, хотя оно известно"
    assert "порог" in посетители.reason


def test_свежее_измерение_подключено(корень):
    сейчас = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (корень / fr.НАБЛЮДЕНИЯ).mkdir(parents=True)
    (корень / fr.НАБЛЮДЕНИЯ / "site-1.json").write_text(json.dumps({
        "visitors": {"value": 42, "state": "CONNECTED", "source": "metrika",
                     "observedAt": сейчас},
    }), encoding="utf-8")
    assert _поле(fr.site_record(корень, "site-1"), "visitors").state is fr.State.CONNECTED


def test_закрытый_доступ_отличается_от_поломки(корень):
    (корень / fr.НАБЛЮДЕНИЯ).mkdir(parents=True)
    (корень / fr.НАБЛЮДЕНИЯ / "site-1.json").write_text(json.dumps({
        "indexedPages": {"state": "ACCESS_BLOCKED", "source": "search-console",
                         "reason": "доступ не выдан"},
        "visits": {"state": "ERROR", "source": "metrika", "reason": "счётчик ответил 500"},
    }), encoding="utf-8")
    з = fr.site_record(корень, "site-1")
    assert _поле(з, "indexedPages").state is fr.State.ACCESS_BLOCKED
    assert _поле(з, "visits").state is fr.State.ERROR
    assert "500" in _поле(з, "visits").reason


def test_неразвёрнутая_витрина_не_отказ(корень):
    (корень / "config" / "site-profiles" / "site-2.json").write_text(
        json.dumps({"site_id": "site-2", "domains": []}), encoding="utf-8")
    з = fr.site_record(корень, "site-2")
    assert _поле(з, "currentRelease").state is fr.State.NOT_CONNECTED
    assert _поле(з, "deployment").value == "NOT_DEPLOYED"


def test_идентификаторы_показываются_а_секреты_нет(корень):
    з = fr.site_record(корень, "site-1")
    assert _поле(з, "analytics.counter_id").value == 12345, (
        "номер счётчика скрыт — без него не понять, куда уходит статистика")
    ссылки = _поле(з, "secretRefs")
    assert ссылки.state is fr.State.CONNECTED
    assert ссылки.value == ["runtime.database.password_secret_ref"]
    # Значение секрета не читается даже для проверки существования.
    выдача = json.dumps(з.as_dict(), ensure_ascii=False)
    assert "file:var/db/pass" not in выдача


def test_весь_флот_одной_выборкой(корень):
    (корень / "config" / "site-profiles" / "site-2.json").write_text(
        json.dumps({"site_id": "site-2"}), encoding="utf-8")
    из = fr.fleet(корень)
    assert из["total"] == 2
    assert из["stateCounts"], "сводка по состояниям пуста — экран не покажет, чего не хватает"
    assert {з["siteId"] for з in из["sites"]} == {"site-1", "site-2"}


def test_испорченный_манифест_называет_причину(корень):
    релиз = (корень / "runtime" / "site-1" / "current").resolve()
    (релиз / "release-manifest.json").write_text("{не json", encoding="utf-8")
    з = fr.site_record(корень, "site-1")
    поле = _поле(з, "templateDigest")
    assert поле.state is fr.State.ERROR
    assert "не читается" in поле.reason


def test_каждое_поле_несёт_источник(корень):
    з = fr.site_record(корень, "site-1")
    без_источника = [и for и, н in з.fields.items() if not н.source]
    assert без_источника == [], f"поля без источника: {без_источника}"


# --- серверный поиск выложенного релиза --------------------------------------

def test_релиз_без_указателя_честно_говорит_что_поиска_нет(корень):
    поле = _поле(fr.site_record(корень, "site-1"), "serverSearch")
    assert поле.state is fr.State.NOT_CONNECTED
    assert поле.value is None
    assert "серверного поиска нет" in поле.reason


def test_релиз_с_указателем_называет_число_записей(корень):
    релиз = (корень / "runtime" / "site-1" / "current").resolve()
    (релиз / "search-index.json").write_text(
        '{"version": "lords-search-index/1.0.0", "size": 52517, "gram": 3, '
        '"postings": {}, "items": []}', encoding="utf-8")
    поле = _поле(fr.site_record(корень, "site-1"), "serverSearch")
    assert поле.state is fr.State.CONNECTED
    assert поле.value["records"] == 52517
    assert поле.value["megabytes"] >= 0


def test_указатель_не_разбирается_целиком(корень, monkeypatch):
    """Указатель весит десятки мегабайт: экран флота не должен его читать.

    Проверяется тем, что после заголовка лежит заведомо неразбираемый хвост —
    попытка разобрать файл целиком упала бы.
    """
    релиз = (корень / "runtime" / "site-1" / "current").resolve()
    (релиз / "search-index.json").write_text(
        '{"version": "lords-search-index/1.0.0", "size": 100, ' + "не json" * 5000,
        encoding="utf-8")
    поле = _поле(fr.site_record(корень, "site-1"), "serverSearch")
    assert поле.state is fr.State.CONNECTED
    assert поле.value["records"] == 100
