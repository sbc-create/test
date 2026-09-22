"""Переработка интерфейса Animedia: поиск, топ по оценкам, пути данных.

Каждая проверка здесь закрывает дефект, найденный на живом снимке, а не
воображаемый. Поэтому в названиях сказано, что именно ломалось.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

СНИМОК_КАТАЛОГА = Path("/srv/lords/.frontend/animedia-01-catalog.json")
СНИМОК_ПОДРОБНОСТЕЙ = Path("/srv/lords/.frontend/animedia-01-details.json")


def _загрузить(имя: str, путь: Path, окружение: dict | None = None):
    прежнее = {к: os.environ.get(к) for к in (окружение or {})}
    os.environ.update(окружение or {})
    try:
        спец = importlib.util.spec_from_file_location(имя, путь)
        модуль = importlib.util.module_from_spec(спец)
        sys.modules[имя] = модуль
        спец.loader.exec_module(модуль)
        return модуль
    finally:
        for к, з in прежнее.items():
            if з is None:
                os.environ.pop(к, None)
            else:
                os.environ[к] = з


@pytest.fixture(scope="module")
def манифест(tmp_path_factory) -> Path:
    путь = tmp_path_factory.mktemp("манифест") / "m.json"
    путь.write_text(json.dumps({
        "schema_version": 1, "template_family": "animedia", "design_version": "1.2.4",
        "source_commit": "0" * 40, "build_id": "test", "artifact_sha256": "0" * 64,
        "profile": "animedia-icu", "built_at": "2026-09-21T00:00:00Z"}), encoding="utf-8")
    return путь


@pytest.fixture(scope="module")
def рантайм(манифест):
    прежний = os.environ.get("LORDS_TEMPLATE_MANIFEST")
    os.environ.pop("LORDS_TEMPLATE_MANIFEST", None)
    модуль = _загрузить("animedia_runtime_ui", ROOT / "automation/host/animedia-frontend.py",
                        {"ANIMEDIA_TEMPLATE_MANIFEST": str(манифест)})
    yield модуль
    if прежний is not None:
        os.environ["LORDS_TEMPLATE_MANIFEST"] = прежний


@pytest.fixture(scope="module")
def снимок(рантайм):
    """Живой снимок каталога с достроенным указателем."""
    if not СНИМОК_КАТАЛОГА.is_file() or not СНИМОК_ПОДРОБНОСТЕЙ.is_file():
        pytest.skip("снимка каталога нет на этом хосте")
    данные = рантайм.Данные(str(СНИМОК_КАТАЛОГА))
    подробности = рантайм.Подробности(str(СНИМОК_ПОДРОБНОСТЕЙ))
    учтено = данные.обогатить_подробностями(подробности)
    return данные, подробности, учтено


# --- поиск --------------------------------------------------------------------

def test_запрос_латиницей_перестал_быть_заведомо_пустым(снимок):
    """Любое одно слово латиницей давало ноль — и не из-за данных.

    Строка «как есть» и строка, прочитанная в другой раскладке, сваливались в
    один набор токенов, а правило требовало совпадения со всеми сразу. Для
    латиницы второе прочтение — «тфкгещ», и совпасть с ним не мог никто.
    """
    данные, _, _ = снимок
    assert данные.искать("naruto"), "оригинальное написание снова не находится"
    assert данные.искать("zvezda"), "слово из slug снова не находится"


def test_оригинальное_написание_приходит_из_подробностей(снимок, рантайм):
    """Обещание формы поиска стало правдой, и правда взята из данных."""
    данные, подробности, учтено = снимок
    assert учтено > 0, "ни одного оригинального названия не подключено"
    # Без обогащения оригинального написания в снимке каталога нет вовсе.
    голые = рантайм.Данные(str(СНИМОК_КАТАЛОГА))
    assert all("original_name" not in з for з in голые.items)
    assert any("original_name" in з for з in данные.items)


def test_оригинальное_написание_не_придумывается(снимок, рантайм):
    """Там, где подробностей нет, в указателе не появляется ничего."""
    данные = рантайм.Данные(str(СНИМОК_КАТАЛОГА))
    пусто = рантайм.Подробности("/несуществующий/путь.json")
    assert данные.обогатить_подробностями(пусто) == 0
    assert all("original_name" not in з for з in данные.items)


def test_чужая_раскладка_всё_ещё_работает(снимок):
    """Исправление не должно было отнять то, ради чего раскладка заводилась."""
    данные, _, _ = снимок
    найдено = данные.искать("vfnhbwf")  # «матрица» латинскими клавишами
    assert найдено, "запрос в чужой раскладке перестал находиться"
    assert any("атрица" in з["title"] for з in найдено)


def test_слово_из_названия_ищется_отдельно_от_склеенной_формы(рантайм):
    """`нормализовать` склеивает название, и часть его переставала искаться."""
    слова = рантайм._слова_записи(
        {"title": "Цветущая звезда Парижа", "slug": "cvetuschaya-zvezda-parizha"})
    assert "zvezda" in слова and "звезда" in слова
    формы = рантайм._написания(
        {"title": "Цветущая звезда Парижа", "slug": "cvetuschaya-zvezda-parizha"})
    assert "cvetuschayazvezdaparizha" in формы


def test_короткие_слова_в_указатель_не_берутся(рантайм):
    """«на», «и», «the» совпадают почти со всем и только портят выдачу."""
    слова = рантайм._слова_записи({"title": "И в горе и в радости", "slug": "i-v-gore"})
    assert all(len(с) >= рантайм.ДЛИНА_СЛОВА_УКАЗАТЕЛЯ for с in слова)


def test_бессмысленный_запрос_остаётся_пустым(снимок):
    """Терпимость к опечаткам не должна превращаться в «найдётся всё»."""
    данные, _, _ = снимок
    assert данные.искать("ъыьщзхжэ") == []


def test_мягкое_совпадение_не_принимает_ложных_соседей(рантайм):
    """Перестановка проверок ради скорости не должна менять решение."""
    assert рантайм._мягкое_совпадение("matrix", "matrica")
    assert not рантайм._мягкое_совпадение("matrix", "maori")
    assert рантайм._мягкое_совпадение("matrix", "matrica1999")


# --- пути данных --------------------------------------------------------------

def test_идентификатор_витрины_берётся_из_имени_снимка(рантайм, манифест, tmp_path):
    """Прежде он выводился из профиля заменой и давал `animedia-0icu`."""
    второй = _загрузить(
        "animedia_runtime_ui_02", ROOT / "automation/host/animedia-frontend.py",
        {"ANIMEDIA_TEMPLATE_MANIFEST": str(манифест),
         "ANIMEDIA_CATALOG": "/srv/lords/.frontend/animedia-02-catalog.json"})
    assert второй.САЙТ_ID == "animedia-02"
    assert рантайм.САЙТ_ID == "animedia-01"


def test_реестр_серий_ищется_рядом_со_снимком_а_не_внутри_релиза(рантайм):
    """Путь от файла релиза указывал в неизменяемый каталог, где данных нет."""
    путь = Path(рантайм.АНИМЕДИА_EPISODE_LEDGER_PATH)
    assert путь.parent == Path(рантайм._КОРЕНЬ_РАНТАЙМА)
    assert путь.name == f"{рантайм.САЙТ_ID}-episode-events.json"
    assert "0icu" not in str(путь)


def test_хранилище_сообщества_лежит_в_каталоге_данных_витрины(рантайм):
    """Корень рантайма принадлежит другой учётной записи: служба туда не пишет."""
    путь = Path(рантайм.АНИМЕДИА_СООБЩЕСТВО_ПУТЬ)
    assert путь.parent.name == "data"
    assert рантайм.САЙТ_ID in str(путь)


def test_реестр_серий_читается_когда_он_есть(манифест, tmp_path):
    """Плумбинг проверяется на подложенном файле, а не на боевых событиях."""
    реестр = tmp_path / "animedia-01-episode-events.json"
    реестр.write_text(json.dumps({
        "schema_version": 1, "site": "animedia-01", "source": "snapshot-diff",
        "events": [{"slug": "нет-такого", "title": "Нет такого", "url": "/title/нет-такого/",
                    "season": 1, "episode_from": 1, "episode_to": 2, "episodes_total": 12,
                    "episode_published_at": "2026-09-22T03:19:43Z",
                    "detected_from": "snapshot-diff"}]}), encoding="utf-8")
    модуль = _загрузить(
        "animedia_runtime_ledger", ROOT / "automation/host/animedia-frontend.py",
        {"ANIMEDIA_TEMPLATE_MANIFEST": str(манифест),
         "ANIMEDIA_EPISODE_LEDGER": str(реестр)})
    assert Path(модуль.АНИМЕДИА_EPISODE_LEDGER_PATH) == реестр


# --- топ по оценкам -----------------------------------------------------------

@pytest.fixture(scope="module")
def топ_инструмент():
    return _загрузить("animedia_ratings_top_tool",
                      ROOT / "automation/host/animedia-ratings-top.py")


def _деталь(значение: float, голоса: int) -> dict:
    return {"ratings_by_source": {"imdb": {"value": значение, "scale": 10.0,
                                           "votes": голоса, "source": "imdb"}}}


def test_топ_отсекает_записи_ниже_порога_голосов(топ_инструмент, рантайм):
    """Без порога наверх встают десятки от шести голосов."""
    детали = {"много": _деталь(8.0, 5000), "мало": _деталь(10.0, 6)}
    каталог = {s: {"title": s, "url": f"/title/{s}/"} for s in детали}
    места, сводка = топ_инструмент.собрать(детали, каталог, рантайм.сводная_оценка,
                                           порог=500, мест=10)
    assert [м["slug"] for м in места] == ["много"]
    assert сводка["below_threshold"] == 1


def test_топ_не_придумывает_оценку_там_где_её_нет(топ_инструмент, рантайм):
    детали = {"без": {}, "с": _деталь(7.5, 900)}
    каталог = {s: {"title": s, "url": f"/title/{s}/"} for s in детали}
    места, сводка = топ_инструмент.собрать(детали, каталог, рантайм.сводная_оценка,
                                           порог=500, мест=10)
    assert [м["slug"] for м in места] == ["с"]
    assert сводка["without_ratings"] == 1


def test_порядок_топа_устойчив_между_сборками(топ_инструмент, рантайм):
    """Одинаковые оценки не должны менять места от запуска к запуску."""
    детали = {f"t{i}": _деталь(8.0, 1000) for i in range(12)}
    каталог = {s: {"title": s, "url": f"/title/{s}/"} for s in детали}
    первый = [м["slug"] for м in топ_инструмент.собрать(
        детали, каталог, рантайм.сводная_оценка, порог=500, мест=12)[0]]
    второй = [м["slug"] for м in топ_инструмент.собрать(
        dict(reversed(list(детали.items()))), каталог, рантайм.сводная_оценка,
        порог=500, мест=12)[0]]
    assert первый == второй


def test_топ_не_выдаёт_себя_за_популярность(рантайм, tmp_path):
    """Файл с другим основанием под этим именем показывать нельзя."""
    чужой = tmp_path / "animedia-01-ratings-top.json"
    чужой.write_text(json.dumps({"basis": "popularity", "places": [{"slug": "x"}]}),
                     encoding="utf-8")
    assert рантайм.загрузить_топ_по_оценкам(path=str(чужой)) is None


def test_без_файла_топа_блок_не_появляется(рантайм, tmp_path):
    assert рантайм.загрузить_топ_по_оценкам(path=str(tmp_path / "нет.json")) is None


def test_пробел_популярности_остаётся_объявленным(рантайм):
    """Топ по оценкам — соседний блок, а не заглушка вместо «Топ‑100»."""
    исходник = (ROOT / "automation/host/animedia-frontend.py").read_text(encoding="utf-8")
    assert 'data-top-basis="ratings-aggregate"' in исходник
    assert 'data-b06-top100="gap"' in исходник
    # Заголовок блока не называет его популярностью.
    assert "Лучшее по оценкам" in исходник
