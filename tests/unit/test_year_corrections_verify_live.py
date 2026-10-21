"""Проверка поправок года ДО и ПОСЛЕ выпуска: по снимку витрины и по странице.

Одна команда на оба состояния — до выпуска она обязана честно говорить «НЕ
применены», после выпуска «применены». Без этого «выпустили» и «работает»
сливаются в одно слово.

Отрицательные контроли, названные заранее:

* **признак на странице обязан РАЗЛИЧАТЬ.** Первая версия искала само число
  года в теле страницы и дала «год есть» у 13 записей из 15 ДО всякого
  выпуска: четырёхзначное число встречается на странице где угодно. Теперь
  проверяется ссылка фасета `/catalog/?year=N`, и обязательно ОТСУТСТВИЕ
  прежней — одного наличия новой мало;
* **контрольная запись с поправкой — отказ прохода целиком** (код 2): если
  правка задела запись, год которой сверка подтвердила верным, остальное уже
  неважно;
* **частичное применение успехом не считается** и печатается отдельной
  строкой: «применены ЧАСТИЧНО — разбирать поимённо».
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_с = importlib.util.spec_from_file_location(
    "year_corrections_verify_live",
    КОРЕНЬ / "automation/local/year-corrections-verify-live.py")
ИНСТР = importlib.util.module_from_spec(_с)
_с.loader.exec_module(ИНСТР)

ИД = "01918cd7-61fd-75e3-8410-67fe2f763a0d"


def _поправки(tmp_path, **п) -> pathlib.Path:
    з = {
        "id": ИД, "slug_at_measure": "rukovodstvo-soten-demonov-4",
        "source_id": "57995",
        "source_url": "https://shikimori.io/animes/57995",
        "measured_at": "2026-10-20T13:39:06Z",
        "matching": "external_id_from_record+title_verified",
        "year_provider": 2020, "year_source": 2024,
    }
    з.update(п)
    ф = tmp_path / "corrections.json"
    ф.write_text(json.dumps({"schema_version": 1, "corrections": [з]}),
                 encoding="utf-8")
    return ф


def _витрина(tmp_path, запись: dict, *, контроль_год_источник: str = "provider"):
    каталог = tmp_path / "data"
    каталог.mkdir(exist_ok=True)
    подробности = {"rukovodstvo-soten-demonov-4": запись}
    for слаг in ИНСТР.КОНТРОЛЬ:
        подробности[слаг] = {"id": f"ид-{слаг}", "year": 2024, "type": "tv",
                             "year_source": контроль_год_источник}
    (каталог / "animedia-01-details.json").write_text(
        json.dumps({"catalog_built_at": "2026-10-21T03:15:26Z",
                    "details": подробности}), encoding="utf-8")
    return str(каталог)


def _подготовить(monkeypatch, tmp_path, запись, *, поправки=None,
                 контроль_год_источник="provider"):
    monkeypatch.setattr(ИНСТР, "ПОПРАВКИ", поправки or _поправки(tmp_path))
    monkeypatch.setitem(
        ИНСТР.ВИТРИНЫ, "animedia-01",
        (_витрина(tmp_path, запись,
                  контроль_год_источник=контроль_год_источник),
         "animedia.icu"))


# --- снимок витрины -------------------------------------------------------------

def test_до_выпуска_честно_не_применено(monkeypatch, tmp_path, capsys):
    _подготовить(monkeypatch, tmp_path,
                 {"id": ИД, "year": 2020, "type": "tv"})
    код = ИНСТР.главное(["--site", "animedia-01"])
    вывод = capsys.readouterr().out
    assert код == 1
    assert "НЕ ПРИМЕНЕНО" in вывод
    assert "поправки НЕ применены — это состояние ДО выпуска" in вывод


def test_после_выпуска_применено(monkeypatch, tmp_path, capsys):
    _подготовить(monkeypatch, tmp_path,
                 {"id": ИД, "year": 2024, "type": "tv",
                  "year_source": "https://shikimori.io/animes/57995 (2026-10-20)"})
    код = ИНСТР.главное(["--site", "animedia-01"])
    вывод = capsys.readouterr().out
    assert код == 0
    assert "все поправки применены" in вывод


def test_запись_без_id_в_снимке_называется(monkeypatch, tmp_path, capsys):
    _подготовить(monkeypatch, tmp_path, {"id": "другой", "year": 2020})
    ИНСТР.главное(["--site", "animedia-01"])
    assert "НЕ НАЙДЕНА" in capsys.readouterr().out


def test_поправка_вида_учитывается(monkeypatch, tmp_path, capsys):
    _подготовить(monkeypatch, tmp_path,
                 {"id": ИД, "year": 2024, "type": "tv", "year_source": "u"},
                 поправки=_поправки(tmp_path, year_source=None,
                                    year_provider=None,
                                    type_provider="tv", type_source="movie"))
    код = ИНСТР.главное(["--site", "animedia-01"])
    assert код == 1, capsys.readouterr().out


# --- отрицательный контроль -----------------------------------------------------

def test_поправка_на_контрольной_записи_это_отказ(monkeypatch, tmp_path, capsys):
    _подготовить(monkeypatch, tmp_path,
                 {"id": ИД, "year": 2024, "type": "tv", "year_source": "u"},
                 контроль_год_источник="https://shikimori.io/animes/1 (x)")
    код = ИНСТР.главное(["--site", "animedia-01"])
    вывод = capsys.readouterr().out
    assert код == 2
    assert "ПРОВАЛ: контрольной записи поставлена поправка" in вывод


# --- признак на странице --------------------------------------------------------
#
# ТРЕТЬЯ редакция признака. Две первые давали один и тот же ответ на
# исправленной и неисправленной странице:
#   1) поиск самого числа года в теле — «год есть» у 13 записей из 15 ДО
#      выпуска: четырёхзначное число встречается где угодно;
#   2) поиск `year=N` во всём теле — в меню каждой страницы animedia.icu стоит
#      фасет годов со ВСЕМИ годами 2015-2026 (30 вхождений `year=` на одной
#      странице, перемерено мной). Тогда «новый год есть» верно до выпуска, а
#      «прежний есть» — после, и исправный выпуск читался бы провалом.
# Различает только блок фактов записи.

ФАСЕТ_МЕНЮ = "".join(
    f'<a href="/catalog/?year={г}"><span>{г}</span></a>' for г in range(2015, 2027))


def _страница(год: int, *, вид: str = "сериал") -> str:
    """Страница записи: блок фактов, JSON-LD и ФАСЕТ МЕНЮ со всеми годами."""
    return (f'<html><body><p>аниме-{вид} {год} года</p>{ФАСЕТ_МЕНЮ}'
            f'<dl><dt>Тип</dt><dd>Аниме</dd>'
            f'<dt>Год</dt><dd><a href="/catalog/?year={год}">{год}</a></dd></dl>'
            f'<script type="application/ld+json">{{"datePublished": "{год}"}}'
            f'</script></body></html>')


def test_фасет_меню_не_обманывает_признак(monkeypatch, tmp_path):
    """Главный контроль: все годы 2015-2026 есть в меню — и признак молчит."""
    _подготовить(monkeypatch, tmp_path,
                 {"id": ИД, "year": 2020, "type": "tv"})
    итог = ИНСТР.разобрать("animedia-01", сеть=True,
                           загрузчик=lambda url: _страница(2020))
    (строка,) = итог["записи"]
    assert строка["год_в_фактах"] == 2020
    assert строка["страница"] == "НЕ ПРИМЕНЕНО", (
        "в фактах прежний год — значит выпуск до страницы не доехал,"
        " сколько бы годов ни стояло в меню")


def test_страница_ок_когда_в_фактах_новый_год(monkeypatch, tmp_path):
    _подготовить(monkeypatch, tmp_path,
                 {"id": ИД, "year": 2024, "type": "tv", "year_source": "u"})
    итог = ИНСТР.разобрать("animedia-01", сеть=True,
                           загрузчик=lambda url: _страница(2024))
    assert итог["записи"][0]["страница"] == "ок"


def test_третье_значение_называется_отдельно(monkeypatch, tmp_path):
    """Ни сверенный, ни прежний — это не «не применено», а расхождение."""
    _подготовить(monkeypatch, tmp_path,
                 {"id": ИД, "year": 2024, "type": "tv", "year_source": "u"})
    итог = ИНСТР.разобрать("animedia-01", сеть=True,
                           загрузчик=lambda url: _страница(1999))
    (строка,) = итог["записи"]
    assert строка["страница"] == "ТРЕТЬЕ ЗНАЧЕНИЕ"
    assert "ни прежний" in строка["страница_почему"]


def test_расхождение_фактов_и_json_ld_это_не_измерено(monkeypatch, tmp_path):
    _подготовить(monkeypatch, tmp_path,
                 {"id": ИД, "year": 2024, "type": "tv", "year_source": "u"})
    тело = _страница(2024).replace('"datePublished": "2024"',
                                   '"datePublished": "2020"')
    итог = ИНСТР.разобрать("animedia-01", сеть=True, загрузчик=lambda url: тело)
    (строка,) = итог["записи"]
    assert строка["страница"] == "не измерено"
    assert "расходятся между собой" in строка["страница_почему"]


def test_без_блока_фактов_это_не_измерено(monkeypatch, tmp_path):
    _подготовить(monkeypatch, tmp_path,
                 {"id": ИД, "year": 2024, "type": "tv", "year_source": "u"})
    итог = ИНСТР.разобрать("animedia-01", сеть=True,
                           загрузчик=lambda url: f"<html>{ФАСЕТ_МЕНЮ}</html>")
    (строка,) = итог["записи"]
    assert строка["страница"] == "не измерено"
    assert "блок фактов" in строка["страница_почему"]


def test_вид_проверяется_подписью_а_не_полем_тип(monkeypatch, tmp_path):
    """`<dt>Тип</dt>` печатает «Аниме» и для tv, и для movie — он не различает.

    Различает подпись «аниме-сериал» / «аниме-фильм». Проверено на живых
    страницах: у `kulak-severnoy-zvezdy-rao` стоит «аниме-сериал 2007», а
    поправка ждёт `movie`.
    """
    _подготовить(monkeypatch, tmp_path,
                 {"id": ИД, "year": 2007, "type": "tv"},
                 поправки=_поправки(tmp_path, year_source=None,
                                    year_provider=None,
                                    type_provider="tv", type_source="movie"))
    итог = ИНСТР.разобрать("animedia-01", сеть=True,
                           загрузчик=lambda url: _страница(2007, вид="сериал"))
    (строка,) = итог["записи"]
    assert строка["вид_подписью"] == "tv"
    assert строка["вид_на_странице"] == "НЕ ПРИМЕНЕНО"
    итог2 = ИНСТР.разобрать("animedia-01", сеть=True,
                            загрузчик=lambda url: _страница(2007, вид="фильм"))
    assert итог2["записи"][0]["вид_на_странице"] == "ок"


def test_основание_признака_страницы_названо():
    текст = " ".join(
        pathlib.Path(ИНСТР.__file__).read_text(encoding="utf-8").split())
    assert "13 записей из 15" in текст
    assert "30 вхождений" in текст
    assert "фасеты меню" in текст


# --- пределы --------------------------------------------------------------------

def test_незнакомая_витрина_отвергается(capsys):
    assert ИНСТР.главное(["--site", "нет-такой"]) == 2
    assert "нет в перечне" in capsys.readouterr().out


def test_нет_снимка_это_не_измерено(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(ИНСТР, "ПОПРАВКИ", _поправки(tmp_path))
    monkeypatch.setitem(ИНСТР.ВИТРИНЫ, "animedia-01",
                        (str(tmp_path / "пусто"), "animedia.icu"))
    assert ИНСТР.главное(["--site", "animedia-01"]) == 2
    assert "НЕ ИЗМЕРЕНО" in capsys.readouterr().out
