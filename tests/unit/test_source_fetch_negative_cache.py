"""REQ-EDITORIAL-SOURCE-CACHE: отказ источника не перезапрашивается в окне.

Измерено 19.10 по журналу обращений (30 745 записей, 09–19.10):

    src-shikimori   27 277 обращений, успех 98.8 %
    src-wikipedia    2 311 обращений, успех 17.0 % (1 917 отказов)

Из 2 311 обращений к Википедии ЛИШНИХ не менее 1 296 (56.1 %):
  * 961 (41.6 %) — повтор адреса, уже ответившего 404; из них 382 в тот же час,
    508 в пределах суток, 56 через 1–3 суток, 15 позже;
  * 335 (14.5 %) — попытки после первого успеха по тому же заголовку.

Причина повторов не в порядке перебора: `film()` уже пробует чистый заголовок
первым и возвращается на первом успехе. Повторяются ОДНИ И ТЕ ЖЕ названия в
разных заданиях и прогонах — один фильм живёт на шести витринах Lords/Zona, и
каждая витрина спрашивает заново до десяти вариантов адреса.

Окно выбрано 24 часа по этим же числам: оно снимает 890 повторов из 961 и
задерживает находку ВНОВЬ созданной статьи не больше чем на сутки. Запоминается
только 404: 429 и сетевые сбои временные, а успех кэшировать нельзя вовсе —
редактор обязан читать живой текст.

Отказ из кэша по-прежнему пишется в журнал (`cached: true`), иначе измерение
линии потеряло бы сам факт попытки и экономию нельзя было бы проверить.
"""
from __future__ import annotations

import calendar
import importlib.util
import json
import pathlib
import time

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation/local/source_fetch.py"
_спец = importlib.util.spec_from_file_location("source_fetch_cache", _путь)
ИСТ = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(ИСТ)

АДРЕС = "https://ru.wikipedia.org/wiki/Нет_такой_статьи"


@pytest.fixture
def среда(tmp_path, monkeypatch):
    """Журнал и кэш в своём каталоге; сеть заменена счётчиком обращений."""
    monkeypatch.setattr(ИСТ, "LOG", tmp_path / "sources.jsonl")
    monkeypatch.setattr(ИСТ, "КЭШ_404", tmp_path / "source-404-cache.json")
    monkeypatch.setattr(ИСТ, "_robots_allows", lambda url: (True, ""))
    обращения: list[str] = []

    def сеть(url, timeout=20):
        обращения.append(url)
        return 404, b""

    monkeypatch.setattr(ИСТ, "_get", сеть)
    return обращения


def журнал(tmp_path_или_путь) -> list[dict]:
    п = ИСТ.LOG
    if not п.is_file():
        return []
    return [json.loads(с) for с in п.read_text(encoding="utf-8").splitlines() if с.strip()]


# --- запоминание отказа -------------------------------------------------------

def test_повторный_отказ_не_идёт_в_сеть(среда):
    код1, _, _ = ИСТ._allowed_get(АДРЕС, "src-wikipedia")
    код2, _, _ = ИСТ._allowed_get(АДРЕС, "src-wikipedia")
    assert (код1, код2) == (404, 404)
    assert len(среда) == 1, "второе обращение должно было прийти из кэша"


def test_отказ_из_кэша_остаётся_в_журнале(среда):
    ИСТ._allowed_get(АДРЕС, "src-wikipedia")
    ИСТ._allowed_get(АДРЕС, "src-wikipedia")
    записи = журнал(None)
    assert len(записи) == 2, "кэш не имеет права скрывать попытку"
    assert записи[0].get("cached") in (None, False)
    assert записи[1].get("cached") is True
    assert записи[1]["status"] == 404


def test_другой_адрес_кэшем_не_закрыт(среда):
    """Отрицательный контроль: кэш не отвечает за адреса, которых в нём нет."""
    ИСТ._allowed_get(АДРЕС, "src-wikipedia")
    ИСТ._allowed_get(АДРЕС + "_2", "src-wikipedia")
    assert len(среда) == 2


# --- что НЕ кэшируется --------------------------------------------------------

@pytest.mark.parametrize("код", [200, 429, 500, 503, None])
def test_кэшируется_только_404(код, среда, monkeypatch):
    """429 и сбои временные, а успех обязан читаться живым."""
    monkeypatch.setattr(ИСТ, "_get", lambda url, timeout=20: (код, b"<html></html>"))
    ИСТ._allowed_get(АДРЕС, "src-wikipedia")
    ИСТ._allowed_get(АДРЕС, "src-wikipedia")
    assert not ИСТ.КЭШ_404.is_file() or не_в_кэше(АДРЕС)


def не_в_кэше(адрес: str) -> bool:
    try:
        д = json.loads(ИСТ.КЭШ_404.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    return адрес not in д


# --- окно ---------------------------------------------------------------------

def test_просроченная_запись_кэша_не_держит(среда):
    """Статья могла появиться: за окном адрес спрашивается снова."""
    ИСТ.КЭШ_404.write_text(json.dumps({
        АДРЕС: time.strftime("%Y-%m-%dT%H:%M:%SZ",
                             time.gmtime(time.time() - (ИСТ.ОКНО_КЭША_Ч + 1) * 3600))
    }), encoding="utf-8")
    ИСТ._allowed_get(АДРЕС, "src-wikipedia")
    assert len(среда) == 1


def test_свежая_запись_кэша_держит(среда):
    ИСТ.КЭШ_404.write_text(json.dumps({
        АДРЕС: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3600))
    }), encoding="utf-8")
    ИСТ._allowed_get(АДРЕС, "src-wikipedia")
    assert среда == [], "свежий отказ не должен идти в сеть"


def test_окно_сутки():
    """Окно названо числом, а не «на всякий случай»: 890 повторов из 961."""
    assert ИСТ.ОКНО_КЭША_Ч == 24


# --- устойчивость -------------------------------------------------------------

def test_битый_кэш_не_ломает_обращение(среда):
    ИСТ.КЭШ_404.write_text("{не json", encoding="utf-8")
    код, _, _ = ИСТ._allowed_get(АДРЕС, "src-wikipedia")
    assert код == 404 and len(среда) == 1


def test_кэш_не_растёт_без_предела(среда, monkeypatch):
    """Старые записи выбрасываются при записи, иначе файл растёт вечно."""
    старое = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                           time.gmtime(time.time() - 30 * 24 * 3600))
    ИСТ.КЭШ_404.write_text(json.dumps({f"{АДРЕС}/{н}": старое for н in range(50)}),
                           encoding="utf-8")
    ИСТ._allowed_get(АДРЕС, "src-wikipedia")
    д = json.loads(ИСТ.КЭШ_404.read_text(encoding="utf-8"))
    assert len(д) == 1 and АДРЕС in д


def test_запрет_robots_в_кэш_не_попадает(среда, monkeypatch):
    """Запрет robots.txt — не ответ источника, и кэшировать его нечего."""
    monkeypatch.setattr(ИСТ, "_robots_allows", lambda url: (False, "robots.txt запрещает"))
    код, _, почему = ИСТ._allowed_get(АДРЕС, "src-wikipedia")
    assert код is None and "robots" in почему
    assert не_в_кэше(АДРЕС)
    assert среда == []

def test_граница_окна_считается_в_utc(среда, monkeypatch):
    """Граница окна не зависит от зоны хоста.

    Прежняя арифметика переводила метку через `time.mktime`, то есть трактовала
    UTC-метку как местное время. На этом хосте зона UTC, и ответ был верным
    СЛУЧАЙНО — ровно та же ловушка, что у директивы robots на страницах 404.
    Здесь граница проверяется подстановкой часов, без обращения к зоне.
    """
    отметка = "2026-10-19T00:00:00Z"
    ИСТ.КЭШ_404.write_text(json.dumps({АДРЕС: отметка}), encoding="utf-8")
    час = 3600
    полдень = calendar.timegm(time.strptime(отметка, "%Y-%m-%dT%H:%M:%SZ"))

    monkeypatch.setattr(ИСТ.time, "time", lambda: полдень + ИСТ.ОКНО_КЭША_Ч * час - 1)
    assert ИСТ.кэш_отказа(АДРЕС) == отметка, "за секунду до границы кэш держит"

    monkeypatch.setattr(ИСТ.time, "time", lambda: полдень + ИСТ.ОКНО_КЭША_Ч * час + 1)
    assert ИСТ.кэш_отказа(АДРЕС) == "", "за границей кэш обязан отпустить адрес"
