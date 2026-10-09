"""REQ-SEO-REGULAR: снимок подробностей читается по записи, а не целиком.

2026-10-09: json.loads снимка lords-01 (112 МБ) давал пик 574 МБ при
MemoryMax=512M у моста — prepare_material для lordfilm47.space убивал мост.
"""

from __future__ import annotations

import json

import pytest

from factory.qwen import editorial


def _снимок(tmp_path, записи, **шапка):
    п = tmp_path / "x-details.json"
    данные = {"catalog_built_at": "2026-10-08T03:15:24Z", "catalog_revision": "rev1",
              "details": записи, "details_total": len(записи), **шапка}
    п.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")
    return п


def _записи():
    return {
        f"slug-{i}": {"id": i, "description": "Описание «тайтла» — " + "ж" * (i % 50)
                      if i % 3 else "", "playable": True, "imdb_rating": 7.25 + i,
                      "nested": {"slug-0": [1, 2, {"a": None}]}}
        for i in range(400)
    }


@pytest.mark.parametrize("размер", [1, 7, 64, 1 << 22])
def test_полный_обход_совпадает_с_загрузкой_целиком(tmp_path, размер):
    записи = _записи()
    п = _снимок(tmp_path, записи, items_total=12345)
    увидено = {}
    шапка = editorial._обойти_снимок(
        п, lambda k, v: увидено.__setitem__(k, v) or False, размер=размер)
    assert увидено == записи
    assert шапка == {"catalog_built_at": "2026-10-08T03:15:24Z", "catalog_revision": "rev1",
                     "details_total": 400, "items_total": 12345}


def test_поиск_останавливается_на_нужной_записи(tmp_path):
    п = _снимок(tmp_path, _записи())
    шаги = []

    def на_запись(k, v):
        шаги.append(k)
        return k == "slug-5"

    editorial._обойти_снимок(п, на_запись, размер=16)
    assert шаги[-1] == "slug-5" and len(шаги) == 6


def test_вложенный_ключ_со_слагом_не_принимается_за_запись(tmp_path):
    п = _снимок(tmp_path, _записи())
    найдено = []
    editorial._обойти_снимок(
        п, lambda k, v: найдено.append(v["id"]) or False, размер=32)
    assert найдено.count(0) == 1


def test_оборванный_снимок_даёт_ошибку_а_не_пустой_результат(tmp_path):
    п = _снимок(tmp_path, _записи())
    п.write_bytes(п.read_bytes()[:-500])
    with pytest.raises(ValueError):
        editorial._обойти_снимок(п, lambda k, v: False, размер=64)


def test_факты_по_слагу_и_сводка(tmp_path, monkeypatch):
    записи = _записи()
    п = _снимок(tmp_path, записи)
    реальный_path = editorial.pathlib.Path

    class Сайт:
        domain, site_id = "example.test", "x"

    monkeypatch.setattr(editorial, "_сайт", lambda site, **kw: Сайт)
    monkeypatch.setattr(editorial, "_требует", lambda s, op: None)
    monkeypatch.setattr(editorial.registry, "адрес_тайтла",
                        lambda s, slug: f"https://example.test/title/{slug}/")
    monkeypatch.setattr(
        editorial.pathlib, "Path",
        lambda p: п if str(p).endswith("x-details.json") else реальный_path(p))

    ф = editorial.факты("example.test", "slug-7")
    assert ф["title_id"] == 7 and ф["facts"]["imdb_rating"] == 14.25
    with pytest.raises(editorial.ОперацияОтклонена):
        editorial.факты("example.test", "нет-такого")
    сводка = editorial.факты("example.test")
    без = [k for k, v in записи.items() if not v["description"]]
    assert сводка["titles_total"] == 400
    assert сводка["without_description_playable"] == len(без)
    assert сводка["sample"] == без[:10] and сводка["catalog_revision"] == "rev1"


def test_ожидание_исполнителя_не_принимает_прошлый_результат_той_же_заявки(tmp_path, monkeypatch):
    """lords-01 2026-10-09: отказ 08:19 вернулся за новую подачу 09:16."""
    from factory.cell import queue as q

    база = tmp_path / "q"
    (база / "results").mkdir(parents=True)
    (база / "results" / "lords-01-edit-c43f.json").write_text(
        json.dumps({"status": "finished", "started_at": "2026-10-09T08:19:00+00:00",
                    "outcome": {"status": "rejected"}}), encoding="utf-8")
    настоящее = q.состояние
    monkeypatch.setattr(q, "состояние",
                        lambda rid, **кв: настоящее(rid, база=база, **кв))
    monkeypatch.setattr(editorial, "ОЖИДАНИЕ_ИСПОЛНИТЕЛЯ_С", 0.3)
    monkeypatch.setattr(editorial, "ШАГ_ИСПОЛНИТЕЛЯ_С", 0.1)
    with pytest.raises(editorial.ОперацияОтклонена):
        editorial._дождаться_исполнителя(
            "lords-01-edit-c43f", {"status": "requeued-after-failure"},
            не_раньше="2026-10-09T09:16:00+00:00")
    # без времени подачи прошлый результат принимается — так было до исправления
    итог = editorial._дождаться_исполнителя(
        "lords-01-edit-c43f", {"status": "requeued-after-failure"})
    assert итог["result"]["status"] == "finished"
