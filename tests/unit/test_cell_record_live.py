"""Запись о выпуске витрины с ДРУГОЙ цели — по живому замеру (MOD-107).

Повод, измеренный 20.10 и подтверждённый 21.10: восемь витрин партии K2
выложены на цель `k2-zomro-01`, выпуск прошёл мимо `factory cell release`
(он пишет `deployed` только при сборке НА ЭТОМ узле), и у всех восьми `status`
остался `planned`, `deployed` пуст, `last_update` — 2026-10-13. При этом каждая
витрина отдаёт 200 и СВОЙ build-id: `9d516ae97730-lords-10`,
`a1e296bbce04-lords-11`, … То есть запись о восьми живых выпусках отсутствует.

Отрицательные контроли, названные заранее, — каждый защищает от своей неправды:

* **нет живого build-id — отказ**, а не пустая запись. Иначе `status: live`
  появился бы у витрины, которой нет;
* **`release_digest` остаётся `null`**: артефакта у нас нет, и придумывать
  отпечаток нельзя. Тест на это отдельный, потому что соблазн заполнить поле
  «чем-нибудь» возникает первым;
* **расхождение индексации важнее записи о выпуске**: паспорт говорит `CLOSED`,
  а витрина отдаёт `index` — запись не делается, пока это не разобрано;
* **цель — этот узел → отказ**: тогда выпуск обязан идти штатным путём, и
  обходить его замером нельзя;
* **`dry_run` ничего не меняет** в реестре.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from factory.cell import live_record, registry

ЗАПИСЬ = {
    "site_id": "lords-10",
    "domain": "lordfilm.group",
    "status": "planned",
    "deployed": {},
    "release": {},
    "deploy_target": {"ref": "k2-zomro-01"},
    "indexing": {"desired_state": "CLOSED"},
    "promotion": {"excluded": True},
    "analytics": {"metrika_counter_id": None},
    "runtime": {"unit": "nova-lordfilm-group.service"},
}


def _реестр(tmp_path, **поля) -> pathlib.Path:
    запись = dict(ЗАПИСЬ)
    запись.update(поля)
    ф = tmp_path / "site-cells.json"
    ф.write_text(json.dumps({"schema_version": 1, "cells": [запись]},
                            ensure_ascii=False), encoding="utf-8")
    return ф


def _страница(build_id: str = "9d516ae97730-lords-10",
              robots: str = "noindex, nofollow") -> str:
    return (f'<html data-build-id="{build_id}">'
            f'<meta name="robots" content="{robots}">'
            f'<body><h1>Проба</h1></body></html>')


def _забрать(код=200, тело: str | None = None):
    return lambda адрес: (код, тело if тело is not None else _страница())


# --- запись ---------------------------------------------------------------------

def test_живой_выпуск_записывается(tmp_path):
    ф = _реестр(tmp_path)
    итог = live_record.записать("lords-10", путь=ф, забрать=_забрать(),
                                когда="2026-10-21T06:00:00Z")
    assert итог["применено"] is True
    assert итог["было"]["status"] == "planned"
    д = json.loads(ф.read_text(encoding="utf-8"))["cells"][0]
    assert д["status"] == "live"
    assert д["deployed"]["build_id"] == "9d516ae97730-lords-10"
    assert д["deployed"]["source"] == "live-probe"
    assert д["deployed"]["evidence"] == "https://lordfilm.group/"
    assert д["deployed"]["probed_at"] == "2026-10-21T06:00:00Z"


def test_отпечаток_релиза_остаётся_пустым(tmp_path):
    """Артефакта нет — значит и отпечатка нет. Заполнять его нечем."""
    ф = _реестр(tmp_path)
    live_record.записать("lords-10", путь=ф, забрать=_забрать())
    д = json.loads(ф.read_text(encoding="utf-8"))["cells"][0]
    assert д["deployed"]["release_digest"] is None
    assert д["deployed"]["artifact"] is None
    assert д["deployed"]["source_commit"] is None


def test_dry_run_ничего_не_меняет(tmp_path):
    ф = _реестр(tmp_path)
    итог = live_record.записать("lords-10", путь=ф, забрать=_забрать(),
                                применять=False)
    assert итог["применено"] is False
    д = json.loads(ф.read_text(encoding="utf-8"))["cells"][0]
    assert д["status"] == "planned"
    assert д["deployed"] == {}


def test_robots_живой_витрины_сохраняется_в_записи(tmp_path):
    ф = _реестр(tmp_path)
    live_record.записать("lords-10", путь=ф, забрать=_забрать())
    д = json.loads(ф.read_text(encoding="utf-8"))["cells"][0]
    assert д["deployed"]["robots_seen"] == "noindex, nofollow"


# --- отказы ---------------------------------------------------------------------

def test_без_build_id_отказ(tmp_path):
    ф = _реестр(tmp_path)
    with pytest.raises(live_record.ЗаписьОтклонена) as ош:
        live_record.записать("lords-10", путь=ф,
                             забрать=_забрать(тело="<html>нет сборки</html>"))
    assert "живого build-id нет" in str(ош.value)
    assert json.loads(ф.read_text(encoding="utf-8"))["cells"][0]["status"] == "planned"


def test_код_не_двести_отказ(tmp_path):
    ф = _реестр(tmp_path)
    with pytest.raises(live_record.ЗаписьОтклонена):
        live_record.записать("lords-10", путь=ф, забрать=_забрать(код=503, тело=""))


def test_расхождение_индексации_отказ(tmp_path):
    """Паспорт CLOSED, витрина отдаёт index — сначала расхождение, потом запись."""
    ф = _реестр(tmp_path)
    with pytest.raises(live_record.ЗаписьОтклонена) as ош:
        live_record.записать(
            "lords-10", путь=ф,
            забрать=_забрать(тело=_страница(robots="index, follow")))
    assert "индексацию CLOSED" in str(ош.value)


def test_открытая_витрина_записывается_несмотря_на_index(tmp_path):
    """Отрицательный контроль к предыдущему: если паспорт не CLOSED, запрета нет."""
    ф = _реестр(tmp_path, indexing={"desired_state": "OPEN"})
    итог = live_record.записать(
        "lords-10", путь=ф,
        забрать=_забрать(тело=_страница(robots="index, follow")))
    assert итог["применено"] is True


def test_цель_этот_узел_отказ(tmp_path):
    ф = _реестр(tmp_path, deploy_target={"ref": live_record.ЭТОТ_УЗЕЛ})
    with pytest.raises(live_record.ЗаписьОтклонена) as ош:
        live_record.записать("lords-10", путь=ф, забрать=_забрать())
    assert "штатным путём" in str(ош.value)


def test_неизвестная_ячейка_это_ошибка_реестра(tmp_path):
    ф = _реестр(tmp_path)
    with pytest.raises(registry.UnknownCell):
        live_record.записать("lords-99", путь=ф, забрать=_забрать())


# --- что запись НЕ трогает ------------------------------------------------------

def test_индексация_и_продвижение_не_меняются(tmp_path):
    ф = _реестр(tmp_path)
    live_record.записать("lords-10", путь=ф, забрать=_забрать())
    д = json.loads(ф.read_text(encoding="utf-8"))["cells"][0]
    assert д["indexing"] == {"desired_state": "CLOSED"}
    assert д["promotion"] == {"excluded": True}
    assert д["analytics"] == {"metrika_counter_id": None}


def test_изменения_только_двух_полей(tmp_path):
    изм = live_record.изменения(
        {"build_id": "x", "адрес": "https://п/", "robots": "noindex"},
        когда="2026-10-21T06:00:00Z")
    assert set(изм) == {"status", "deployed"}


def test_основание_записи_названо_в_модуле():
    текст = " ".join(
        pathlib.Path(live_record.__file__).read_text(encoding="utf-8").split())
    assert "MOD-107" in текст
    assert "9d516ae97730-lords-10" in текст
    assert "release_digest` остаётся `null`" in текст
