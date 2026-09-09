"""Контракт снимка маршрутов: пять дефектов, найденных потребителем.

Проверки написаны от отказов. Каждая соответствует одному пункту handoff
058 и падает, если пункт вернётся.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib

import pytest

from factory.site_engine import route_snapshot as rs
from factory.site_engine.route_snapshot import SnapshotRefused, build

СЕЙЧАС = dt.datetime(2026, 9, 9, 14, 0, tzinfo=dt.timezone.utc)
ПРОИЗВОДИТЕЛЬ = "1f29ed5a8d7c1f56f928d35171cedc548a615f01"
СХЕМА = pathlib.Path("schemas/site-engine/core-route-snapshot.schema.json")


def _адрес(name, external_id):
    from factory.lords.live_catalog import slugify
    return f"/title/{slugify(name) or external_id.lower()}/"


def _запись(**поля):
    основа = {"external_id": "w-1", "name": "Тишина", "type": "movie",
              "is_series": False, "tags": []}
    основа.update(поля)
    return основа


def _снимок(записи=None, **ещё):
    поля = {"site_id": "lords-01", "route_of": _адрес, "observed_at": СЕЙЧАС,
            "producer_sha": ПРОИЗВОДИТЕЛЬ, "source_digest": "abc",
            "generation_reason": "full-rebuild",
            "content_kind_of": rs.catalog_kind}
    поля.update(ещё)
    return build(записи if записи is not None else [_запись()], **поля)


# --- Д1: происхождение --------------------------------------------------------
def test_сокращённый_sha_производителя_отвергается():
    """Именно так в снимок и попала база вместо производителя."""
    with pytest.raises(SnapshotRefused, match="полный SHA"):
        _снимок(producer_sha="2ccfa102")


def test_пустой_sha_производителя_отвергается():
    with pytest.raises(SnapshotRefused):
        _снимок(producer_sha="")


def test_sha_не_в_нижнем_регистре_отвергается():
    with pytest.raises(SnapshotRefused):
        _снимок(producer_sha=ПРОИЗВОДИТЕЛЬ.upper())


def test_полный_sha_принимается():
    assert _снимок().producer_sha == ПРОИЗВОДИТЕЛЬ


def test_схема_ограничивает_длину_sha():
    """Ограничение обязано жить и в объявлении, а не только в коде."""
    объявлено = json.loads(СХЕМА.read_text(encoding="utf-8"))
    assert объявлено["properties"]["producerSha"]["pattern"] == "^[0-9a-f]{40}$"


# --- Д2: отпечаток заголовка --------------------------------------------------
def test_подмена_заголовка_меняет_отпечаток_заголовка():
    """Дефект был именно здесь: поля, которых нет в записях, отпечатком
    записей не покрыты вовсе.

    Витрина сюда не годится как пример: `siteId` лежит и в каждой записи,
    поэтому её подмену отпечаток записей как раз ловит. Ловит он её случайно —
    не потому, что заверяет заголовок, а потому что то же значение повторено
    внутри. `generationReason` не повторено нигде, и его можно было переписать
    молча.
    """
    a = _снимок().as_dict()
    b = _снимок(generation_reason="incremental").as_dict()
    assert a["digest"] == b["digest"], "записи те же — отпечаток записей совпал"
    assert a["envelopeDigest"] != b["envelopeDigest"]


def test_подмена_отпечатка_источника_меняет_отпечаток_заголовка():
    a = _снимок().as_dict()
    b = _снимок(source_digest="подменено").as_dict()
    assert a["digest"] == b["digest"]
    assert a["envelopeDigest"] != b["envelopeDigest"]


def test_витрину_отпечаток_записей_ловит_и_сам():
    """Полезно знать, что именно чем заверено."""
    a = _снимок().as_dict()
    b = _снимок(site_id="lords-02").as_dict()
    assert a["digest"] != b["digest"]


def test_подмена_происхождения_меняет_отпечаток_заголовка():
    a = _снимок().as_dict()
    b = _снимок(producer_sha="0" * 40).as_dict()
    assert a["envelopeDigest"] != b["envelopeDigest"]


def test_отпечаток_заголовка_воспроизводится():
    д = _снимок().as_dict()
    заголовок = {к: v for к, v in д.items()
                 if к not in ("envelopeDigest", "records", "collisions", "rejected")}
    assert rs.envelope_digest_of(заголовок) == д["envelopeDigest"]


# --- Д3: время наблюдения -----------------------------------------------------
def test_наблюдение_раньше_источника_отвергается():
    """Снимок не мог наблюдать то, что появилось позже него."""
    with pytest.raises(SnapshotRefused, match="раньше снятия источника"):
        _снимок(observed_at=dt.datetime(2026, 9, 9, 0, 0, tzinfo=dt.timezone.utc),
                source_observed_at="2026-09-09T05:55:44Z")


def test_наблюдение_после_источника_принимается():
    с = _снимок(source_observed_at="2026-09-09T05:55:44Z")
    assert с.as_dict()["sourceObservedAt"] == "2026-09-09T05:55:44Z"


# --- Д4: вид произведения -----------------------------------------------------
def test_вид_обязателен_и_умолчания_не_имеет():
    """Прежде он был необязательным, и его забыли — вид вышел пустым у всех
    47 684 записей, а потребитель не допустил ни одной страницы."""
    with pytest.raises(TypeError):
        build([_запись()], site_id="lords-01", route_of=_адрес,
              observed_at=СЕЙЧАС, producer_sha=ПРОИЗВОДИТЕЛЬ,
              source_digest="abc", generation_reason="full-rebuild")


def test_фильм_и_сериал_различаются():
    д = _снимок([_запись(external_id="w-1", name="Фильм", type="movie",
                         is_series=False),
                 _запись(external_id="w-2", name="Сериал", type="tv",
                         is_series=True)]).as_dict()
    виды = {з["stableWorkId"]: (з["contentKind"], з["contentKindState"])
            for з in д["records"]}
    assert виды["w-1"] == ("MOVIE", "AUTHORITATIVE")
    assert виды["w-2"] == ("SERIES", "AUTHORITATIVE")


def test_расхождение_type_и_is_series_объявляется_конфликтом():
    """Два поля описывают одну вещь. Разошлись — это испорченные данные, а не
    повод выбрать одно из двух."""
    вид, состояние = rs.catalog_kind({"type": "movie", "is_series": True})
    assert (вид, состояние) == ("UNKNOWN", "CONFLICT")


def test_отсутствие_типа_не_превращается_в_фильм():
    assert rs.catalog_kind({}) == ("UNKNOWN", "MISSING")


def test_анимация_без_метки_остаётся_неизвестной_а_не_ложной():
    """Теги заполнены у 2,4 % записей. Вернуть False значило бы превратить
    наше молчание в утверждение о мире."""
    assert rs.catalog_animation({"tags": ["anime"]}) is True
    assert rs.catalog_animation({"tags": ["13+"]}) is None
    assert rs.catalog_animation({"tags": []}) is None
    assert rs.catalog_animation({}) is None


def test_ложь_про_анимацию_не_выставляется_никогда():
    из_каталога = [{"tags": t} for t in ([], ["13+"], ["anime"], ["cartoon"],
                                         ["ona"], None)]
    assert False not in {rs.catalog_animation(з) for з in из_каталога}


def test_форма_берётся_из_тега_а_её_отсутствие_не_значит_обычное():
    assert rs.catalog_form({"tags": ["ona"]}) == "ONA"
    assert rs.catalog_form({"tags": ["ova"]}) == "OVA"
    assert rs.catalog_form({"tags": []}) == ""


def test_таксономия_объявлена_вместе_со_значением():
    """Два класса — это предел каталога, и он назван прямо."""
    assert _снимок().as_dict()["kindTaxonomy"] == "core-catalog/type:2"


def test_столкновение_не_получает_вида():
    """Неизвестно, чьей записи принадлежит адрес — значит неизвестен и вид."""
    д = _снимок([_запись(external_id="w-1", name="Тень", type="movie",
                         is_series=False),
                 _запись(external_id="w-2", name="Тень", type="tv",
                         is_series=True)]).as_dict()
    столкновение = [з for з in д["records"] if з["state"] == "COLLISION"]
    assert столкновение and столкновение[0]["contentKind"] == "UNKNOWN"


# --- Д5: правило отпечатка источника ------------------------------------------
def test_правило_отпечатка_источника_объявлено():
    д = _снимок().as_dict()
    assert д["sourceDigestAlgorithm"] == "blake2b-128/json-sorted-compact"


def test_версия_приведения_адреса_объявлена():
    assert _снимок().as_dict()["normalizationVersion"] == "core-route-normalization/1.0.0"


# --- схема и снимок не расходятся ---------------------------------------------
def test_снимок_проходит_объявленную_схему():
    jsonschema = pytest.importorskip("jsonschema")
    объявлено = json.loads(СХЕМА.read_text(encoding="utf-8"))
    jsonschema.validate(_снимок().as_dict(), объявлено)


def test_версия_в_схеме_и_в_коде_одна():
    объявлено = json.loads(СХЕМА.read_text(encoding="utf-8"))
    assert объявлено["properties"]["schemaVersion"]["const"] == rs.SNAPSHOT_SCHEMA


def test_все_обязательные_поля_схемы_снимок_отдаёт():
    объявлено = json.loads(СХЕМА.read_text(encoding="utf-8"))
    д = _снимок().as_dict()
    отсутствуют = [п for п in объявлено["required"] if п not in д]
    assert not отсутствуют, f"снимок не отдаёт объявленное: {отсутствуют}"
