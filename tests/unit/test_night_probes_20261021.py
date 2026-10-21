"""Проверки на ночные проходы: жанры для карты, перелинковка, редакция, год в тексте.

Четыре прохода, которыми за ночь сделаны выводы. У каждого проверяется та
граница, на которой он может соврать:

* **жанры для карты** — дубль каталога обязан отличаться от узкой выборки, иначе
  в карту уедет копия каталога;
* **перелинковка** — ссылки на СВОЮ работу и на фасеты не должны считаться
  ходами к другим работам, иначе ноль превратится в семнадцать;
* **редакция** — поиск по НАЧАЛУ замены дал бы «опубликовано» и для
  неопубликованного, поэтому ищется отличительный кусок;
* **год в тексте** — год из блока «похожее» и из подвала не является годом
  описания, и пустой год нельзя подставлять в регулярное выражение.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]


def _модуль(имя: str, файл: str):
    спец = importlib.util.spec_from_file_location(имя, КОРЕНЬ / файл)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


ЖАНРЫ = _модуль("genre_pages_for_sitemap",
                "automation/local/genre-pages-for-sitemap.py")
ССЫЛКИ = _модуль("title_page_linking", "automation/local/title-page-linking.py")
РЕДАКЦИЯ = _модуль("editorial_reaches_visitor",
                   "automation/local/editorial-reaches-visitor.py")
ГОД = _модуль("year_text_consistency",
              "automation/local/year-text-consistency.py")


# --- жанры для карты ------------------------------------------------------------


def _страница_жанра(карточек: int, найдено: int, путь: str,
                    robots: str = "index, follow") -> str:
    ссылки = "".join(f'<a href="/title/t{н}/">T{н}</a>' for н in range(карточек))
    return (f'<meta name="robots" content="{robots}">'
            f'<link rel="canonical" href="https://x.test{путь}">'
            f"<p>Найдено {найдено} записей</p>{ссылки}")


@pytest.fixture()
def сеть_жанров(monkeypatch):
    таблица: dict[str, str] = {}
    monkeypatch.setattr(ЖАНРЫ, "достать",
                        lambda адрес, таймаут=40: таблица.get(адрес))
    return таблица


def test_жанр_с_набором_всего_каталога_в_карту_не_идёт(сеть_жанров):
    """`?genre=anime` объявляет те же записи, что каталог — это дубль."""
    сеть_жанров["https://x.test/catalog/"] = (
        '<a href="/catalog/?genre=anime">аниме</a>'
        '<a href="/catalog/?genre=drama">драма</a>'
        "<p>Найдено 8228 записей</p>")
    сеть_жанров["https://x.test/catalog/?genre=anime"] = _страница_жанра(
        3, 8228, "/catalog/?genre=anime")
    сеть_жанров["https://x.test/catalog/?genre=drama"] = _страница_жанра(
        3, 1523, "/catalog/?genre=drama")
    итог = ЖАНРЫ.проверить("x.test", предел=None)
    состояния = {с["жанр"]: с["итог"] for с in итог["страницы"]}
    assert состояния["anime"].startswith("ДУБЛЬ КАТАЛОГА")
    assert состояния["drama"] == "годится"
    assert итог["годных"] == ["drama"]
    assert any("дубли каталога" in з for з in итог["замечания"])


def test_закрытый_и_пустой_жанр_в_карту_не_идут(сеть_жанров):
    сеть_жанров["https://x.test/catalog/"] = (
        '<a href="/catalog/?genre=closed">з</a><a href="/catalog/?genre=empty">п</a>'
        "<p>Найдено 8228 записей</p>")
    сеть_жанров["https://x.test/catalog/?genre=closed"] = _страница_жанра(
        3, 100, "/catalog/?genre=closed", robots="noindex, follow")
    сеть_жанров["https://x.test/catalog/?genre=empty"] = _страница_жанра(
        0, 0, "/catalog/?genre=empty")
    итог = ЖАНРЫ.проверить("x.test", предел=None)
    состояния = {с["жанр"]: с["итог"] for с in итог["страницы"]}
    assert "noindex" in состояния["closed"]
    assert "пустая" in состояния["empty"]
    assert итог["годных"] == []


def test_размер_из_листалки_когда_числа_нет():
    """Где витрина не печатает «Найдено», берётся номер последней страницы."""
    тело = '<a href="?page=2">2</a><a href="?page=1532">1532</a>'
    assert ЖАНРЫ.размер(тело) == (1532, "страниц листалки")
    assert ЖАНРЫ.размер("<p>Найдено 8 228 записей</p>")[0] == 8228
    assert ЖАНРЫ.размер("<p>ничего</p>") == (None, "не измерено")


# --- перелинковка ---------------------------------------------------------------


def test_ссылки_на_свою_работу_ходом_в_сторону_не_считаются():
    тело = ('<a href="/title/ao-asi-2/">сама</a>'
            '<a href="/title/ao-asi-2/season-1/episode-3">серия</a>'
            '<a href="/catalog/?year=2024">год</a>'
            '<a href="/title/другая/">другая</a>')
    итог = ССЫЛКИ.разобрать(тело, "/title/ao-asi-2/")
    assert итог["на_другие_работы"] == 1
    assert итог["на_свои_серии"] == 1
    assert итог["на_фасеты"] == 1


def test_ноль_ходов_в_сторону_это_замечание(monkeypatch):
    """Форма дефекта MOD-123: со страницы некуда идти, кроме фасетов."""
    таблица = {
        "https://x.test/": '<a href="/title/a/">A</a>',
        "https://x.test/title/a/": (
            '<a href="/title/a/season-1/episode-1">серия</a>'
            '<a href="/catalog/?year=2024">год</a>'
            '<nav class="breadcrumb"><a href="/">дом</a></nav>'),
    }
    monkeypatch.setattr(ССЫЛКИ, "достать",
                        lambda адрес, таймаут=40: таблица.get(адрес))
    итог = ССЫЛКИ.проверить("x.test", 1)
    assert итог["минимум_на_другие"] == 0
    assert any("идти некуда" in з for з in итог["замечания"])


def test_фасеты_не_подменяют_ходы_к_работам(monkeypatch):
    """Семнадцать фасетов не отменяют нуля ссылок на другие работы."""
    фасеты = "".join(f'<a href="/catalog/?year=20{н:02d}">г</a>' for н in range(17))
    таблица = {
        "https://x.test/": '<a href="/title/a/">A</a>',
        "https://x.test/title/a/": фасеты + '<a href="/title/a/">сама</a>',
    }
    monkeypatch.setattr(ССЫЛКИ, "достать",
                        lambda адрес, таймаут=40: таблица.get(адрес))
    итог = ССЫЛКИ.проверить("x.test", 1)
    страница = итог["страницы"][0]
    assert страница["на_фасеты"] == 17
    assert страница["на_другие_работы"] == 0


# --- редакционные материалы -----------------------------------------------------


def test_отличительный_кусок_берётся_не_с_начала():
    замена = ("Короткое начало. Это длинное предложение, по которому замену"
              " можно отличить от исходного описания точно.")
    кусок = РЕДАКЦИЯ.отличительный(замена)
    assert кусок is not None
    assert len(кусок) >= РЕДАКЦИЯ.МИН_КУСОК
    assert not замена.startswith(кусок)


def test_короткая_замена_не_проверяется():
    assert РЕДАКЦИЯ.отличительный("Коротко. Очень.") is None


def test_поле_текста_выбирает_первое_непустое():
    assert РЕДАКЦИЯ.поле_текста({"name": "Имя"}) == "Имя"
    assert РЕДАКЦИЯ.поле_текста({"description": "Описание", "name": "Имя"}) == "Описание"
    assert РЕДАКЦИЯ.поле_текста({"poster": "x"}) == ""


def test_ключ_разрешается_и_как_слаг(monkeypatch, tmp_path):
    """Ключ хранилища бывает двух видов, и слаг — такой же законный, как id.

    Первая редакция проверки разрешала только провайдерский идентификатор и
    объявила материал непривязанным; живая проверка показала обратное —
    заголовок страницы был заменён. Поэтому слаг теперь разрешается тоже.
    """
    хранилище = tmp_path / "editorial-slug"
    хранилище.mkdir()
    (хранилище / "zona-01.json").write_text(json.dumps({
        "overrides": {"мой-слаг": {"actor": "architect/x",
                                   "fields": {"name": "Новое имя"}}}}),
        encoding="utf-8")
    monkeypatch.setattr(РЕДАКЦИЯ, "ХРАНИЛИЩЕ", хранилище)
    monkeypatch.setattr(РЕДАКЦИЯ, "слаги", lambda ячейка: {"ид": "мой-слаг"})
    monkeypatch.setattr(РЕДАКЦИЯ, "достать",
                        lambda адрес, таймаут=40: "<h1>Новое имя</h1>")
    итог = РЕДАКЦИЯ.проверить("zona-01", {"domain": "x.test",
                                          "runtime": {"data_dir": str(tmp_path)}})
    assert итог["материалы"][0]["ключ"] == "по слагу"
    assert итог["материалы"][0]["итог"] == "дошло"
    assert итог["материалы"][0]["где"] == "h1"


def test_замена_названия_сверяется_по_узкой_поверхности(monkeypatch, tmp_path):
    """Название короче 40 символов, но `h1` и `title` сверяются целиком."""
    хранилище = tmp_path / "editorial-name"
    хранилище.mkdir()
    (хранилище / "zona-01.json").write_text(json.dumps({
        "overrides": {"ид": {"actor": "editor/x", "fields": {"name": "Имя"}}}}),
        encoding="utf-8")
    monkeypatch.setattr(РЕДАКЦИЯ, "ХРАНИЛИЩЕ", хранилище)
    monkeypatch.setattr(РЕДАКЦИЯ, "слаги", lambda ячейка: {"ид": "слаг"})
    monkeypatch.setattr(РЕДАКЦИЯ, "достать",
                        lambda адрес, таймаут=40: "<h1>Другое</h1><title>Другое</title>")
    итог = РЕДАКЦИЯ.проверить("zona-01", {"domain": "x.test",
                                          "runtime": {"data_dir": str(tmp_path)}})
    assert итог["материалы"][0]["итог"] == "НЕ ДОШЛО"


def test_неразрешимый_ключ_называется_прямо(monkeypatch, tmp_path):
    """Ключ, который не идентификатор и не слаг, — это не «дошло» и не «нет»."""
    хранилище = tmp_path / "editorial"
    хранилище.mkdir()
    (хранилище / "zona-01.json").write_text(json.dumps({
        "overrides": {"нет-такого-ид": {"actor": "editor/x",
                                        "fields": {"name": "Новое имя"}}}}),
        encoding="utf-8")
    monkeypatch.setattr(РЕДАКЦИЯ, "ХРАНИЛИЩЕ", хранилище)
    monkeypatch.setattr(РЕДАКЦИЯ, "слаги", lambda ячейка: {})
    итог = РЕДАКЦИЯ.проверить("zona-01", {"domain": "x.test",
                                          "runtime": {"data_dir": str(tmp_path)}})
    assert "не разрешён" in итог["материалы"][0]["итог"]


# --- год в тексте ---------------------------------------------------------------


def test_редакционный_текст_не_включает_блок_похожего():
    """Годы других произведений и подвала не являются годом описания."""
    тело = ('<meta name="description" content="Описание без года.">'
            '<script type="application/ld+json">'
            '{"@type":"TVSeries","description":"То же описание.",'
            '"datePublished":"2017"}</script>'
            '<section>Похожее аниме · 2004 · 2005</section>'
            '<footer>Годы 2026 2025 2024</footer>')
    текст = ГОД.редакционный_текст(тело)
    assert "Описание без года" in текст
    assert "2004" not in текст and "2026" not in текст
    assert ГОД.дата_разметки(тело) == "2017"


def test_пустой_год_поправки_не_превращается_в_совпадение(monkeypatch, tmp_path):
    """`\\b\\b` совпадает с чем угодно: пустой год надо отсеивать до поиска."""
    поправки = tmp_path / "поправки.json"
    поправки.write_text(json.dumps({"corrections": [
        {"slug_at_measure": "a", "type_provider": "tv", "type_source": "movie"}]}),
        encoding="utf-8")
    monkeypatch.setattr(ГОД, "ПОПРАВКИ", поправки)
    monkeypatch.setattr(ГОД, "достать", lambda адрес, таймаут=40: "<p>текст</p>")
    итог = ГОД.проверить("animedia-01")
    assert итог["записи"][0]["итог"].startswith("поправка ВИДА")


def test_неверный_год_в_описании_это_находка(monkeypatch, tmp_path):
    поправки = tmp_path / "поправки.json"
    поправки.write_text(json.dumps({"corrections": [
        {"slug_at_measure": "a", "year_provider": 2020, "year_source": 2024}]}),
        encoding="utf-8")
    monkeypatch.setattr(ГОД, "ПОПРАВКИ", поправки)
    monkeypatch.setattr(ГОД, "достать", lambda адрес, таймаут=40: (
        '<meta name="description" content="Сериал 2020 года о чём-то.">'))
    итог = ГОД.проверить("animedia-01")
    assert итог["записи"][0]["итог"] == "ТЕКСТ НЕСЁТ НЕВЕРНЫЙ ГОД"
