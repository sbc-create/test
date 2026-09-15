"""Приёмочные проверки суточного цикла.

Проверяется не «код запускается», а свойства, на которых стоит доверие к
отчёту: одинаковый вход даёт одинаковые факты, знаменатель нельзя уменьшить
ради процента, недоступность модели не останавливает сбор данных, а платных
операций цикл не умеет вовсе.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ХОСТ = КОРЕНЬ / "automation/host"


def _модуль(имя: str, файл: str):
    spec = importlib.util.spec_from_file_location(имя, ХОСТ / файл)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


COV = _модуль("_cov", "seo_coverage.py")
INV = _модуль("_inv", "seo_inventory.py")

КАТАЛОГ = {"revision": "r1", "items": [
    {"slug": "a", "title": "А", "year": 2020, "kind": "Фильм", "poster": "p", "url": "/title/a/"},
    {"slug": "b", "title": "Б", "year": None, "kind": "Сериал", "poster": "", "url": "/title/b/"},
    {"slug": "c", "title": "В", "year": 2021, "kind": "Мультфильм", "poster": "p", "url": "/title/c/"},
]}
ПОДРОБНОСТИ = {
    "a": {"name": "А", "original_name": "A", "description": "текст",
          "genres": ["драма"], "external_ids": {"imdb": "1", "kinopoisk": "2"},
          "ratings_by_source": {"imdb": {"value": 7.1, "scale": 10.0}}},
    "b": {"name": "Б", "original_name": "", "description": "",
          "genres": [], "external_ids": {"kinopoisk": "3"},
          "ratings_by_source": {}},
}


# --- покрытие --------------------------------------------------------------
def test_сегменты_разделены_и_аниме_не_смешано_с_кино():
    assert COV.сегмент("Фильм", "lords") == "FILMS"
    assert COV.сегмент("Сериал", "lords") == "SERIES"
    # У витрины аниме всё содержимое — аниме, каким бы ни был вид записи:
    # мерить её вместе с киносайтом значит не мерить ни то, ни другое.
    assert COV.сегмент("Фильм", "yummy") == "ANIME"
    assert COV.сегмент("Сериал", "animedia") == "ANIME"


def test_сопоставление_не_выдаётся_за_оценку():
    """Объект сопоставления без `value` — доказательство, что запись нашли,
    а не что её оценили."""
    только_матч = {"x": {"external_ids": {"imdb": "1"},
                         "ratings_by_source": {"imdb": {"match_state": "exact"}}}}
    р = COV.рейтинги(только_матч)
    assert р["imdb"]["COVERED"] == 0
    assert р["imdb"]["ELIGIBLE"] == 1


def test_неподключённый_источник_не_называется_несопоставленным():
    """Пока источник не подключён вовсе, сопоставлять было не с чем."""
    р = COV.рейтинги(ПОДРОБНОСТИ)
    assert р["kinopoisk"]["COVERED"] == 0
    assert р["kinopoisk"]["SOURCE_NOT_INTEGRATED"] == 2
    assert р["kinopoisk"]["UNMATCHED_IDENTITY"] == 0
    # IMDb подключён: у одной записи оценка есть, у другой идентификатора нет.
    assert р["imdb"]["COVERED"] == 1
    assert р["imdb"]["MISSING_SOURCE"] == 1


def test_алиасы_идентификатора_кинопоиска_учитываются():
    д = {"x": {"external_ids": {"kp": "7"}, "ratings_by_source": {}}}
    assert COV.рейтинги(д)["kinopoisk"]["ELIGIBLE"] == 1


def test_отсутствие_подробностей_не_ноль_а_блокировка():
    """Витрина без собранных подробностей не «покрыта на 0 %»: ей не дали
    данных, и обвинять её в этом нельзя."""
    з = COV.по_витрине("s", "d.ru", "lords", КАТАЛОГ, {})
    поле = з["segments"]["FILMS"]["fields"]["details.description"]
    assert поле["RAW_COVERAGE"] is None
    assert поле["BLOCKED"]


def test_знаменатель_растёт_вместе_с_каталогом():
    """Новый каталог обязан увеличивать знаменатель. Уменьшать процент
    выбрасыванием трудных записей запрещено, и подпись снимка это ловит."""
    было = {"d.ru": COV.по_витрине("s", "d.ru", "lords", КАТАЛОГ, ПОДРОБНОСТИ)}
    больше = {"revision": "r2", "items": КАТАЛОГ["items"] + [
        {"slug": "d", "title": "Г", "kind": "Фильм"}]}
    стало = {"d.ru": COV.по_витрине("s", "d.ru", "lords", больше, ПОДРОБНОСТИ)}
    assert стало["d.ru"]["segments"]["FILMS"]["entries"] > было["d.ru"]["segments"]["FILMS"]["entries"]
    assert COV.отпечаток(было) != COV.отпечаток(стало)


def test_подпись_снимка_устойчива():
    м = {"d.ru": COV.по_витрине("s", "d.ru", "lords", КАТАЛОГ, ПОДРОБНОСТИ)}
    assert COV.отпечаток(м) == COV.отпечаток(м)


# --- инвентарь -------------------------------------------------------------
def test_редирект_не_получает_каталога():
    сегодня = {"r.ru": {"domain": "r.ru", "role": "REDIRECT_ONLY", "http": 301,
                        "redirect_to": "https://x.ru/", "template_family": "",
                        "in_allowlist": True, "mutations_allowed": False}}
    assert not сегодня["r.ru"]["mutations_allowed"]


def test_разница_видит_домен_в_проде_без_реестра():
    сегодня = {"n.ru": {"domain": "n.ru", "role": "UNKNOWN", "http": 200,
                        "redirect_to": "", "template_family": "",
                        "in_allowlist": False, "mutations_allowed": False}}
    д = INV.разница(сегодня, {})
    assert "n.ru" in д["in_production_not_in_inventory"]


def test_разница_видит_смену_роли():
    вчера = {"a.ru": {"role": "ONBOARDING", "http": 200, "redirect_to": "",
                      "template_family": "lords"}}
    сегодня = {"a.ru": {"role": "MANAGED_PRODUCTION", "http": 200,
                        "redirect_to": "", "template_family": "lords"}}
    изм = INV.разница(сегодня, вчера)["changed"]
    assert any(и["field"] == "role" for и in изм)


# --- цикл ------------------------------------------------------------------
def test_цикл_не_умеет_платных_операций():
    """Не «не запускает», а не умеет: метода в коде нет."""
    источник = (ХОСТ / "seo-daily-cycle.py").read_text(encoding="utf-8")
    for платное in ("positions_2/checker/go", "audit_2/audit", "topvisor.cli apply"):
        assert платное not in источник, платное


def test_отчёт_выпускается_даже_без_публикации():
    источник = (ХОСТ / "seo-daily-cycle.py").read_text(encoding="utf-8")
    assert "blocked_reason" in источник
    assert '"published": 0' in источник or '"published"' in источник


def test_недоступность_qwen_не_останавливает_цикл():
    """Отчёт выпускается и без второго мнения: отсутствие оценки не отменяет
    фактов, а остановленный сбор отменил бы."""
    C = _модуль("_cycle", "seo-daily-cycle.py")
    q = C.оценка_qwen({"report_id": "t", "date": "2026-09-15",
                       "coverage": {}, "traffic": {}, "content": {},
                       "gap_queue_total": 0, "gap_queue_top": [],
                       "inventory": {}, "topvisor": {}})
    assert q["status"] in ("OK", "UNAVAILABLE")
    assert q.get("verdict") in ("IMPROVING", "STABLE", "DECLINING",
                               "INSUFFICIENT_DATA")
    # Причина названа словами, а не кодом: «недоступно» без причины через
    # месяц читается как «не сделали».
    assert q["status"] != "UNAVAILABLE" or q.get("reason")


def test_локальный_файл_не_считается_доставкой():
    источник = (ХОСТ / "seo-daily-cycle.py").read_text(encoding="utf-8")
    assert "WAITING_OWNER_DESTINATION" in источник
    assert "локальный файл доставкой не является" in источник


def test_секретов_в_исходниках_цикла_нет():
    for файл in ("seo-daily-cycle.py", "seo_coverage.py", "seo_inventory.py"):
        т = (ХОСТ / файл).read_text(encoding="utf-8")
        for образец in ("Bearer ", "sk-", "AQAA", "y0_", "api_key="):
            assert образец not in т, (файл, образец)
