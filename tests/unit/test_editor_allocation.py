"""Распределение плановой работы редактора: 50 % аниме, 50 % Lordfilm/Lordserial.

Что ловится. 13.10 из 77 опубликованных страниц 76 пришлись на аниме, одна на
Zona, Lords — ни одной: ротация шла по доменам, и девять аниме-доменов против
четырёх Lords забирали цикл. Владелец 13.10 закрепил доли по НАПРАВЛЕНИЯМ:
партии чередуются, отставшее направление идёт первым; пока у Lords нет работы
(пауза публикаций), партия уходит аниме — но с названной причиной, а не молча;
Zona в долю Lords не засчитывается; восемь новых доменов Lords в редакционную
работу не входят вовсе.
"""
from __future__ import annotations

import datetime as dt
import json

from seo_operator import editor_run

СЕЙЧАС = dt.datetime(2026, 10, 13, 12, 0, tzinfo=dt.timezone.utc)


def _стенд(tmp_path, кандидаты, журнал=()):
    (tmp_path / "registry.json").write_text(json.dumps({"items": []}), encoding="utf-8")
    (tmp_path / "candidates.json").write_text(json.dumps({"candidates": кандидаты}), encoding="utf-8")
    (tmp_path / "queue_events.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "leases.json").write_text(json.dumps({"leases": []}), encoding="utf-8")
    состояние = tmp_path / "state"
    состояние.mkdir()
    (состояние / "gate.jsonl").write_text(
        "".join(json.dumps({"at": at, "gate": {"run": True, "allocated": куда}}) + "\n"
                for at, куда in журнал), encoding="utf-8")
    return {"registry": tmp_path / "registry.json", "candidates": tmp_path / "candidates.json",
            "events": tmp_path / "queue_events.jsonl", "leases": tmp_path / "leases.json",
            "state": состояние}


def _работа(стенд):
    return editor_run._work(СЕЙЧАС, refresh=False, recent={}, **стенд)


def _к(домен, slug):
    return {"url": f"https://{домен}/title/{slug}/", "domain": домен}


КАНДИДАТЫ = [_к("yummyani.site", "a"), _к("animeg0.site", "b"), _к("lordfilm47.space", "c"),
             _к("lordserial33.biz", "d"), _к("zonafilm.space", "e")]


def _без_пауз(monkeypatch):
    monkeypatch.setattr(editor_run, "переданные_черновики", lambda: [])
    monkeypatch.setattr(editor_run, "PAUSED_PUBLISH", {})


def test_при_равенстве_первой_идёт_партия_lords(tmp_path, monkeypatch):
    _без_пауз(monkeypatch)
    итог = _работа(_стенд(tmp_path, КАНДИДАТЫ))
    assert итог["run"] and итог["allocated"] == "lords"
    домены = {editor_run._домен(c) for c in итог["next"]}
    assert домены <= {"lordfilm47.space", "lordserial33.biz", "zonafilm.space"}
    assert "yummyani.site" not in итог["domains"] and "lordfilm47.space" in итог["domains"]


def test_отставшее_направление_получает_партию(tmp_path, monkeypatch):
    _без_пауз(monkeypatch)
    журнал = [("2026-10-13T08:00:00Z", "lords"), ("2026-10-13T09:00:00Z", "lords"),
              ("2026-10-13T10:00:00Z", "anime")]
    итог = _работа(_стенд(tmp_path, КАНДИДАТЫ, журнал))
    assert итог["allocated"] == "anime"
    assert {editor_run._домен(c) for c in итог["next"]} <= {"yummyani.site", "animeg0.site",
                                                           "zonafilm.space"}


def test_вне_окна_партии_не_считаются(tmp_path, monkeypatch):
    _без_пауз(monkeypatch)
    журнал = [("2026-10-11T08:00:00Z", "lords")] * 5
    итог = _работа(_стенд(tmp_path, КАНДИДАТЫ, журнал))
    assert итог["allocated"] == "lords"


def test_пауза_lords_отдаёт_партию_аниме_с_причиной(tmp_path, monkeypatch):
    monkeypatch.setattr(editor_run, "переданные_черновики", lambda: [])
    итог = _работа(_стенд(tmp_path, КАНДИДАТЫ, [("2026-10-13T10:00:00Z", "anime")]))
    assert итог["direction"] == "lords" and итог["allocated"] == "anime"
    assert "PAUSED_PUBLISH" in итог["allocation_note"] and "техработу" in итог["allocation_note"]
    assert not any(editor_run._домен(c) in editor_run.НАПРАВЛЕНИЯ["lords"] for c in итог["next"])


def test_zona_не_засчитывается_в_lords():
    assert editor_run.направление_домена("zonafilm.space") is None
    assert editor_run.направление_домена("zonafilm.cc") is None
    assert editor_run.направление_домена("lordserials22.info") == "lords"


def test_новые_домены_lords_вне_редакционной_работы():
    вне = set(editor_run.ВНЕ_ПРОДВИЖЕНИЯ)
    assert len(вне) == 8
    assert not вне & set(editor_run.allowed_domains())
    assert not вне & set().union(*editor_run.НАПРАВЛЕНИЯ.values())


def test_доли_из_конфигурации():
    доли = editor_run.cadence()["allocation"]
    assert доли["anime"] == 0.5 and доли["lords"] == 0.5


def _шлюз(стенд, сейчас):
    return editor_run.gate(сейчас, refresh=False, recent={},
                           resources_fn=lambda: {"ok": True, "measured": {}, "problems": []},
                           **стенд)


def _записать(стенд, сейчас, решение):
    with (стенд["state"] / "gate.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": сейчас.strftime("%Y-%m-%dT%H:%M:%SZ"), "gate": решение},
                           ensure_ascii=False) + "\n")


def test_доля_lords_на_паузе_удерживается_а_не_отдаётся_аниме(tmp_path, monkeypatch):
    """Пауза Lords: шлюз не запускает аниме вместо Lords, а выдерживает слот
    Lords; повтор вызова в окне слот не пересчитывает; после окна — партия аниме."""
    monkeypatch.setattr(editor_run, "переданные_черновики", lambda: [])
    стенд = _стенд(tmp_path, КАНДИДАТЫ)
    нулевое = _шлюз(стенд, СЕЙЧАС - dt.timedelta(minutes=30))
    assert нулевое["run"] is True and нулевое["allocated"] == "anime"   # ничья: долга нет
    _записать(стенд, СЕЙЧАС - dt.timedelta(minutes=30), нулевое)
    первое = _шлюз(стенд, СЕЙЧАС)
    assert первое["run"] is False and первое["state"] == "allocation_hold"
    assert первое["allocated"] == "lords" and "PAUSED_PUBLISH" in первое["reason"]
    _записать(стенд, СЕЙЧАС, первое)

    через_5 = СЕЙЧАС + dt.timedelta(minutes=5)
    второе = _шлюз(стенд, через_5)
    assert второе["state"] == "allocation_hold" and "allocated" not in второе
    _записать(стенд, через_5, второе)
    assert editor_run.партии_по_направлениям(стенд["state"], через_5) == {"anime": 1, "lords": 1}

    после = СЕЙЧАС + dt.timedelta(minutes=25)
    третье = _шлюз(стенд, после)
    assert третье["run"] is True and третье["allocated"] == "anime"   # ничья 1:1


def test_длительность_удержания_по_медиане_партий(tmp_path):
    состояние = tmp_path
    (состояние / "runs.jsonl").write_text("".join(
        json.dumps({"started_at": f"2026-10-13T0{ч}:00:00Z",
                    "finished_at": f"2026-10-13T0{ч}:{м:02d}:00Z"}) + "\n"
        for ч, м in ((1, 10), (2, 18), (3, 30))), encoding="utf-8")
    assert editor_run._длительность_партии(состояние) == 18 * 60
    assert editor_run._длительность_партии(tmp_path / "нет") == 1200
