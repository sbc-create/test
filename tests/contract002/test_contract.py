"""Регрессионные проверки сквозного контракта и backfill.

Всё на снимках и временных копиях в собственном каталоге. Ни одна проверка
не пишет в рабочие данные витрины и не трогает чужие процессы.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

from factory.lords.canonical_projection import спроецировать
from factory.lords.canonical_recommend import построить_корзины, подобрать

КОРЕНЬ = Path(__file__).resolve().parents[2]


def _загрузить_backfill():
    """Инструмент лежит в automation/host и пакетом не является."""
    путь = КОРЕНЬ / "automation/host/lords-details-backfill.py"
    спец = importlib.util.spec_from_file_location("lords_backfill", путь)
    модуль = importlib.util.module_from_spec(спец)
    sys.modules["lords_backfill"] = модуль
    спец.loader.exec_module(модуль)
    return модуль


BF = _загрузить_backfill()


@pytest.fixture()
def среда(tmp_path):
    """Маленький самодостаточный снимок: две записи, одна с деталью."""
    снимок = {"items": [
        {"external_id": "ent-1", "name": "Первый", "type": "movie", "year": 2020,
         "kinopoisk_rating": 7.4, "imdb_rating": 6.9,
         "poster_url": "https://poster/1.webp",
         "external_ids": {"kinopoisk": "111", "imdb": "tt111"},
         "playback": {"aggregator": "kp", "title_id": "555"}},
        {"external_id": "ent-2", "name": "Второй", "type": "tv", "year": 2021,
         "poster_url": "https://poster/2.webp",
         "external_ids": {"imdb": "tt222"},
         "playback": {"aggregator": "mali", "title_id": "777"}},
    ]}
    (tmp_path / "snapshot.json").write_text(json.dumps(снимок), encoding="utf-8")
    состояние = {"ent-1": {"slug": "pervyy", "digest": "d1"},
                 "ent-2": {"slug": "vtoroy", "digest": "d2"}}
    (tmp_path / "state.json").write_text(json.dumps(состояние), encoding="utf-8")
    детали = tmp_path / "detail"
    детали.mkdir()
    (детали / "ent-1.json").write_text(json.dumps({"status": "ok", "detail": {
        "id": "ent-1",
        "description": "Подробное описание первого произведения, достаточно "
                       "длинное, чтобы не считаться заглушкой.",
        "seasons": []}}), encoding="utf-8")
    return {"snapshot": tmp_path / "snapshot.json",
            "state": tmp_path / "state.json",
            "detail": детали,
            "target": tmp_path / "details.json",
            "backups": tmp_path / "backups"}


def прогон(среда, *, применить=False, run_id="t-1"):
    return BF.выполнить(снимок=среда["snapshot"], состояние=среда["state"],
                        детали=среда["detail"], цель=среда["target"],
                        применить=применить, копии=среда["backups"],
                        run_id=run_id)


# --- сухой прогон и запись ---------------------------------------------------

def test_сухой_прогон_ничего_не_пишет(среда):
    отчёт = прогон(среда)
    assert отчёт["mode"] == "dry-run"
    assert отчёт["production_mutations"] == 0
    assert not среда["target"].exists(), "сухой прогон создал файл"


def test_запись_только_по_явному_флагу(среда):
    прогон(среда)
    assert not среда["target"].exists()
    отчёт = прогон(среда, применить=True)
    assert отчёт["mode"] == "apply" and отчёт["written"] is True
    assert среда["target"].exists()


# --- идемпотентность ---------------------------------------------------------

def test_повторный_прогон_даёт_тот_же_результат(среда):
    прогон(среда, применить=True, run_id="t-a")
    первый = среда["target"].read_bytes()
    отчёт = прогон(среда, применить=True, run_id="t-b")
    второй = среда["target"].read_bytes()
    assert первый == второй, "повторный прогон изменил содержимое"
    assert отчёт["stats"]["изменено"] == 0
    assert отчёт["stats"]["сохранено_прежних"] == 2


def test_отпечаток_устойчив(среда):
    a = прогон(среда)["after_digest"]
    b = прогон(среда)["after_digest"]
    assert a == b


# --- защита от затирания -----------------------------------------------------

def test_пустое_значение_не_затирает_непустое(среда):
    прогон(среда, применить=True)
    # У второй записи описания нет; допишем его вручную, как если бы оно
    # пришло другим путём, и убедимся, что backfill его не снесёт.
    д = json.loads(среда["target"].read_text(encoding="utf-8"))
    д["details"]["vtoroy"]["description"] = "Ранее полученное описание, длинное."
    среда["target"].write_text(json.dumps(д), encoding="utf-8")
    прогон(среда, применить=True, run_id="t-c")
    после = json.loads(среда["target"].read_text(encoding="utf-8"))
    assert после["details"]["vtoroy"]["description"] == \
        "Ранее полученное описание, длинное.", "непустое значение затёрто"


def test_чужая_привязка_прекращает_работу(среда):
    прогон(среда, применить=True)
    д = json.loads(среда["target"].read_text(encoding="utf-8"))
    # slug занят другим произведением — это подмена сущности.
    д["details"]["pervyy"]["id"] = "ent-СОВСЕМ-ДРУГОЙ"
    среда["target"].write_text(json.dumps(д), encoding="utf-8")
    with pytest.raises(BF.ContractViolation) as ош:
        прогон(среда, применить=True, run_id="t-d")
    assert "менял бы произведение" in str(ош.value)


# --- сохранность полей -------------------------------------------------------

def test_оценки_доходят_до_бокового_файла(среда):
    прогон(среда, применить=True)
    д = json.loads(среда["target"].read_text(encoding="utf-8"))["details"]
    assert д["pervyy"]["kinopoisk_rating"] == 7.4
    assert д["pervyy"]["imdb_rating"] == 6.9
    assert д["pervyy"]["ratings_source"]["kinopoisk"] == "catalog"


def test_описание_и_постер_доходят(среда):
    прогон(среда, применить=True)
    д = json.loads(среда["target"].read_text(encoding="utf-8"))["details"]
    assert д["pervyy"]["description"].startswith("Подробное описание")
    assert д["pervyy"]["description_source"] == "detail"
    assert д["pervyy"]["poster_url"] == "https://poster/1.webp"
    assert д["vtoroy"]["poster_url"] == "https://poster/2.webp"


def test_привязка_к_источнику_с_провайдером(среда):
    прогон(среда, применить=True)
    д = json.loads(среда["target"].read_text(encoding="utf-8"))["details"]
    и = д["pervyy"]["sources"][0]
    assert и["provider"] == "kp" and и["source_id"] == "555"
    assert и["availability_status"] == "available"
    assert д["pervyy"]["playable"] is True
    # Канонический идентификатор источником не подставляется.
    assert и["source_id"] != "ent-1"


def test_идентичность_сущности_сохраняется(среда):
    прогон(среда, применить=True)
    д = json.loads(среда["target"].read_text(encoding="utf-8"))["details"]
    assert д["pervyy"]["id"] == "ent-1"
    assert д["vtoroy"]["id"] == "ent-2"
    assert len({v["id"] for v in д.values()}) == 2


# --- откат -------------------------------------------------------------------

def test_откат_возвращает_прежний_файл(среда):
    прогон(среда, применить=True, run_id="t-e")
    первая = среда["target"].read_bytes()
    # Меняем снимок так, чтобы второй прогон дал другой результат.
    снимок = json.loads(среда["snapshot"].read_text(encoding="utf-8"))
    снимок["items"][0]["kinopoisk_rating"] = 9.9
    среда["snapshot"].write_text(json.dumps(снимок), encoding="utf-8")
    отчёт = прогон(среда, применить=True, run_id="t-f")
    вторая = среда["target"].read_bytes()
    assert первая != вторая
    # Откат — возврат сохранённого образа, а не обратное вычисление.
    образ = Path(отчёт["before_image"])
    assert образ.is_file()
    shutil.copy2(образ, среда["target"])
    assert среда["target"].read_bytes() == первая


def test_образ_до_изменения_создаётся_с_run_id(среда):
    прогон(среда, применить=True, run_id="t-g")
    отчёт = прогон(среда, применить=True, run_id="t-h")
    assert "t-h" in отчёт["before_image"]


# --- рекомендации ------------------------------------------------------------

def test_рекомендации_не_включают_саму_карточку(среда):
    прогон(среда, применить=True)
    д = json.loads(среда["target"].read_text(encoding="utf-8"))["details"]
    for слаг, запись in д.items():
        assert запись["id"] not in (запись.get("recommendation_ids") or [])


def test_бедная_корзина_расширяется_до_каталога(среда):
    """У записи редкого вида корзина пуста — но лента пустой быть не должна.

    Это не придирка к малому набору: в живом каталоге есть виды и жанры с
    единичными записями, и для них корзина ведёт себя ровно так же.
    """
    снимок = json.loads(среда["snapshot"].read_text(encoding="utf-8"))["items"]
    проекции = [спроецировать(з, None) for з in снимок]
    корзины = построить_корзины(проекции)
    for п in проекции:
        по_корзинам = подобрать(п, проекции, корзины=корзины)
        полный = подобрать(п, проекции)
        assert п.id not in по_корзинам
        assert set(по_корзинам) <= {x.id for x in проекции}
        # Корзина не теряет кандидатов, которых нашёл бы полный перебор.
        assert set(по_корзинам) == set(полный), (
            f"корзина обеднила выдачу для {п.id}: "
            f"{sorted(set(полный) - set(по_корзинам))}")


def test_лента_не_короче_минимума_когда_каталог_позволяет(среда):
    """Шесть — это контракт, а не пожелание."""
    from factory.lords.canonical_recommend import МИНИМУМ
    записи = [{"external_id": f"ent-{i}", "name": f"Запись {i}",
               "type": "movie" if i % 2 else "tv", "year": 2000 + i}
              for i in range(12)]
    проекции = [спроецировать(з, None) for з in записи]
    корзины = построить_корзины(проекции)
    for п in проекции:
        r = подобрать(п, проекции, корзины=корзины)
        assert len(r) >= МИНИМУМ, f"{п.id}: выдано {len(r)}"
        assert п.id not in r and len(r) == len(set(r))


# --- контракт ----------------------------------------------------------------

def test_каждая_запись_имеет_канонический_идентификатор(среда):
    прогон(среда, применить=True)
    д = json.loads(среда["target"].read_text(encoding="utf-8"))["details"]
    assert all(v.get("id") for v in д.values())


def test_запись_без_идентификатора_прекращает_работу(среда, tmp_path):
    плохой = tmp_path / "bad.json"
    плохой.write_text(json.dumps({"items": [{"name": "без идентификатора"}]}),
                      encoding="utf-8")
    среда["snapshot"] = плохой
    with pytest.raises(BF.ContractViolation):
        прогон(среда, применить=True, run_id="t-i")
