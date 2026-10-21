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


# --- объявленный режим индексации против действительного (MOD-55) ---------------
#
# Измерено 21.10: у ДЕВЯТИ витрин паспорт объявляет CLOSED, а живые страницы
# отдают `index, follow` — an1meg0.site, an1mego.site, animedia.icu,
# animedia.space, animeg0.site, lordserials22.info, yummyani7.info,
# yummyani7.site, zonafilm12.site. У всех есть якорь согласия владельца.
# Открытых БЕЗ разрешения — ноль, и это вторая половина измерения: правка
# приводит ЗАПИСЬ к действительности, а не открывает что-либо.

СОГЛАСИЕ = {
    "schema_version": 1, "domain": "lordfilm.group", "site_id": "lords-10",
    "authorized": True, "by": "claude", "at": "2026-10-05T04:58:31Z",
    "id": "6f18e2e8-9ff2-476b-8327-9325d3dd6664",
}


def _согласие(tmp_path, **поля) -> pathlib.Path:
    import json as _json
    import os
    корень = tmp_path / "owner-consent"
    корень.mkdir(exist_ok=True)
    данные = dict(СОГЛАСИЕ)
    данные.update(поля)
    ф = корень / f"{данные['domain']}.json"
    ф.write_text(_json.dumps(данные, ensure_ascii=False), encoding="utf-8")
    os.chmod(ф, 0o444)
    return корень


def _замер(meta="index, follow", xrt="index, follow", код=200):
    return lambda домен: {"код": код, "meta": meta, "x_robots_tag": xrt,
                          "адрес": f"https://{домен}/"}


def _паспорт(tmp_path, **поля):
    инд = {"desired_state": "CLOSED", "open_authorized": True,
           "reason": "Сейчас закрыто: noindex отдают и рантайм, и nginx"}
    инд.update(поля)
    return _реестр(tmp_path, indexing=инд)


def test_правка_составляется_но_не_применяется(tmp_path, monkeypatch):
    """Точечный путь не пускает блок `indexing` — и это защита, а не поломка.

    `registry.update` намеренно не содержит `indexing` в перечне полей,
    обновляемых точечно. Проверено вызовом: RegistryError «эти поля паспорта не
    обновляются точечно: ['indexing']». Единственный писатель блока —
    `newsite.py` при создании ячейки. Значит девять устаревших паспортов
    (MOD-55) штатно не исправить, и это сама находка.
    """
    ф = _паспорт(tmp_path)
    корень = _согласие(tmp_path)
    monkeypatch.setattr(live_record.owner_consent, "_права",
                        lambda п: (True, ""))
    итог = live_record.записать_индексацию(
        "lords-10", путь=ф, замер=_замер(), согласие_корень=корень,
        когда="2026-10-21T06:00:00Z", применять=False)
    assert итог["применено"] is False
    assert "не пускает блок `indexing`" in итог["почему_не_применено"]
    пред = итог["предложение"]["indexing"]
    assert пред["desired_state"] == "OPEN"
    assert "живым замером 2026-10-21T06:00:00Z" in пред["reason"]
    assert пред["open_authorization_id"] == СОГЛАСИЕ["id"]
    # Паспорт на диске не изменился ни в чём.
    д = json.loads(ф.read_text(encoding="utf-8"))["cells"][0]["indexing"]
    assert д["desired_state"] == "CLOSED"


def test_применять_истина_даёт_отказ_с_причиной(tmp_path, monkeypatch):
    ф = _паспорт(tmp_path)
    корень = _согласие(tmp_path)
    monkeypatch.setattr(live_record.owner_consent, "_права", lambda п: (True, ""))
    with pytest.raises(live_record.ЗаписьОтклонена) as ош:
        # Намеренно БЕЗ `применять=False`: значение по умолчанию обязано дать
        # отказ с названной причиной, а не тихо ничего не сделать.
        live_record.записать_индексацию("lords-10", путь=ф, замер=_замер(),
                                        согласие_корень=корень)
    assert "применить её нечем" in str(ош.value)


def test_точечный_путь_действительно_отвергает_indexing(tmp_path):
    """Это проверка на ЗАЩИТУ: если её откроют, тест обязан упасть."""
    ф = _реестр(tmp_path)
    with pytest.raises(registry.RegistryError) as ош:
        registry.update("lords-10", {"indexing": {"desired_state": "OPEN"}},
                        path=ф)
    assert "не обновляются точечно" in str(ош.value)


def test_прежняя_причина_заменяется_в_предложении(tmp_path, monkeypatch):
    """Устаревшая причина правдоподобна — её нельзя оставлять рядом с OPEN."""
    ф = _паспорт(tmp_path)
    корень = _согласие(tmp_path)
    monkeypatch.setattr(live_record.owner_consent, "_права", lambda п: (True, ""))
    итог = live_record.записать_индексацию("lords-10", путь=ф, замер=_замер(),
                                           согласие_корень=корень,
                                           применять=False)
    assert "Сейчас закрыто" not in итог["предложение"]["indexing"]["reason"]


def test_живой_noindex_это_отказ(tmp_path, monkeypatch):
    """Если витрина отдаёт noindex, объявленный CLOSED ВЕРЕН."""
    ф = _паспорт(tmp_path)
    корень = _согласие(tmp_path)
    monkeypatch.setattr(live_record.owner_consent, "_права", lambda п: (True, ""))
    with pytest.raises(live_record.ЗаписьОтклонена) as ош:
        live_record.записать_индексацию(
            "lords-10", путь=ф, замер=_замер(meta="noindex, nofollow"),
            согласие_корень=корень, применять=False)
    assert "объявленный CLOSED ВЕРЕН" in str(ош.value)


def test_noindex_в_заголовке_тоже_отказ(tmp_path, monkeypatch):
    """Мета и заголовок проверяются ОБА: одного чистого мало."""
    ф = _паспорт(tmp_path)
    корень = _согласие(tmp_path)
    monkeypatch.setattr(live_record.owner_consent, "_права", lambda п: (True, ""))
    with pytest.raises(live_record.ЗаписьОтклонена):
        live_record.записать_индексацию(
            "lords-10", путь=ф,
            замер=_замер(meta="index, follow", xrt="noindex"),
            согласие_корень=корень, применять=False)


def test_без_якоря_согласия_отказ(tmp_path):
    ф = _паспорт(tmp_path)
    пусто = tmp_path / "нет-согласий"
    пусто.mkdir()
    with pytest.raises(live_record.ЗаписьОтклонена) as ош:
        live_record.записать_индексацию("lords-10", путь=ф, замер=_замер(),
                                        согласие_корень=пусто,
                                        применять=False)
    assert "решение, которого не было" in str(ош.value)


def test_согласие_не_authorized_отказ(tmp_path, monkeypatch):
    ф = _паспорт(tmp_path)
    корень = _согласие(tmp_path, authorized=False)
    monkeypatch.setattr(live_record.owner_consent, "_права", lambda п: (True, ""))
    with pytest.raises(live_record.ЗаписьОтклонена):
        live_record.записать_индексацию("lords-10", путь=ф, замер=_замер(),
                                        согласие_корень=корень,
                                        применять=False)


def test_open_authorized_false_отказ(tmp_path, monkeypatch):
    ф = _паспорт(tmp_path, open_authorized=False)
    корень = _согласие(tmp_path)
    monkeypatch.setattr(live_record.owner_consent, "_права", lambda п: (True, ""))
    with pytest.raises(live_record.ЗаписьОтклонена) as ош:
        live_record.записать_индексацию("lords-10", путь=ф, замер=_замер(),
                                        согласие_корень=корень,
                                        применять=False)
    assert "open_authorized" in str(ош.value)


def test_уже_open_это_отказ(tmp_path, monkeypatch):
    ф = _паспорт(tmp_path, desired_state="OPEN")
    корень = _согласие(tmp_path)
    monkeypatch.setattr(live_record.owner_consent, "_права", lambda п: (True, ""))
    with pytest.raises(live_record.ЗаписьОтклонена) as ош:
        live_record.записать_индексацию("lords-10", путь=ф, замер=_замер(),
                                        согласие_корень=корень,
                                        применять=False)
    assert "обновлять нечего" in str(ош.value)


def test_код_не_двести_отказ_индексации(tmp_path, monkeypatch):
    ф = _паспорт(tmp_path)
    корень = _согласие(tmp_path)
    monkeypatch.setattr(live_record.owner_consent, "_права", lambda п: (True, ""))
    with pytest.raises(live_record.ЗаписьОтклонена) as ош:
        live_record.записать_индексацию(
            "lords-10", путь=ф, замер=_замер(код=503), согласие_корень=корень,
            применять=False)
    assert "не измерен" in str(ош.value)


def test_изменения_только_блока_индексации(tmp_path, monkeypatch):
    ф = _паспорт(tmp_path)
    корень = _согласие(tmp_path)
    monkeypatch.setattr(live_record.owner_consent, "_права", lambda п: (True, ""))
    итог = live_record.записать_индексацию("lords-10", путь=ф, замер=_замер(),
                                           согласие_корень=корень,
                                           применять=False)
    assert set(итог["предложение"]) == {"indexing"}


def test_поля_блока_не_выходят_за_схему(tmp_path, monkeypatch):
    """У блока `indexing` в схеме `additionalProperties: false`."""
    import json as _json
    корень_репо = pathlib.Path(__file__).resolve().parents[2]
    схема = _json.loads((корень_репо / "schemas/site-cells.schema.json")
                        .read_text(encoding="utf-8"))
    разрешено = set(схема["properties"]["cells"]["items"]["properties"]
                    ["indexing"]["properties"])
    ф = _паспорт(tmp_path)
    корень = _согласие(tmp_path)
    monkeypatch.setattr(live_record.owner_consent, "_права", lambda п: (True, ""))
    итог = live_record.записать_индексацию("lords-10", путь=ф, замер=_замер(),
                                           согласие_корень=корень,
                                           применять=False)
    лишние = set(итог["предложение"]["indexing"]) - разрешено
    assert not лишние, f"схема такие поля отвергнет: {sorted(лишние)}"
