"""Контракт SEO-слоя: то, что обязано выполняться после любой сборки.

Проверки написаны против слоя, а не против шаблона. Шаблон может смениться
целиком — слой обязан остаться, и именно это здесь и удерживается.
"""
from __future__ import annotations

import importlib.util
import pathlib
import re
import xml.etree.ElementTree as ET

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
СЛОЙ = КОРЕНЬ / "automation/host/seo_layer.py"
РЕНДЕРЕР = КОРЕНЬ / "automation/host/lords-frontend.py"

spec = importlib.util.spec_from_file_location("_seo_layer", СЛОЙ)
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

КАРТА = {"lordfilm47.space": "112010269", "lordserial33.biz": "112010274",
         "1lordserials1.online": "112010277", "zonafilm.space": "112582938"}
ЧИСТАЯ = b"<html><head><title>t</title></head><body>b</body></html>"


def о(тело=ЧИСТАЯ, **kw):
    основа = dict(хост="lordfilm47.space", путь="/", counter="112010269",
                  имя_сайта="Lordfilm", код=200)
    return S.обогатить(тело, "text/html; charset=utf-8", **(основа | kw))


# --- аналитика -------------------------------------------------------------
def test_рендерер_зовёт_слой_из_отдачи_ответа():
    т = РЕНДЕРЕР.read_text(encoding="utf-8")
    assert "import seo_layer as SEO" in т
    assert т.count("SEO.обогатить(") == 1, "слой должен вызываться ровно из одного места"
    assert т.index("SEO.обогатить(") > т.index("def _отдать("), "вызов не из отдачи"


@pytest.mark.parametrize("домен,счёт", sorted(КАРТА.items()))
def test_у_каждого_домена_свой_счётчик(домен, счёт):
    в = о(хост=домен, counter=счёт).decode()
    assert f'ym({счёт},"init"' in в
    чужие = [c for c in КАРТА.values() if c != счёт and f"ym({c}," in в]
    assert чужие == [], f"{домен}: чужой счётчик {чужие}"


def test_счётчик_одного_домена_не_попадает_на_другой():
    assert len(set(КАРТА.values())) == 4


def test_тег_ровно_один_и_повтор_не_добавляет_второго():
    один = о()
    два = S.обогатить(один, "text/html", хост="lordfilm47.space", путь="/",
                      counter="112010269", имя_сайта="L")
    assert один.count(b"metrika/tag.js") == 1
    assert два.count(b"metrika/tag.js") == 1
    assert два.count(b'ym(112010269,"init"') == 1


@pytest.mark.parametrize("мусор", ["", "  ", "abc", "-5", "1 2", "0x1b"])
def test_негодный_счётчик_не_даёт_тега(мусор):
    assert b"mc.yandex" not in о(counter=мусор)


def test_не_html_не_размечается():
    тело = b'{"a":1}'
    assert S.обогатить(тело, "application/json", хост="d.ru", путь="/",
                       counter="112010269", имя_сайта="L") == тело


def test_страница_без_head_не_трогается():
    тело = b"<svg><g/></svg>"
    assert S.обогатить(тело, "text/html", хост="d.ru", путь="/",
                       counter="112010269", имя_сайта="L") == тело


def test_тег_не_задерживает_отрисовку():
    assert "k.async=1" in S.тег_метрики("112010269")


def test_вебвизор_выключен_в_теге():
    assert "webvisor:false" in S.тег_метрики("112010269")
    assert "trackLinks:true" in S.тег_метрики("112010269")
    assert "accurateTrackBounce:true" in S.тег_метрики("112010269")


def test_инициализация_защёлкнута():
    assert "__sfMetrikaReady" in S.тег_метрики("1")
    assert S.тег_метрики("1").count('"init"') == 1


@pytest.mark.parametrize("маршрут", ["/", "/catalog/", "/new/", "/title/x/"])
def test_тег_на_обязательных_маршрутах(маршрут):
    assert о(путь=маршрут).count(b"metrika/tag.js") == 1


# --- canonical -------------------------------------------------------------
def test_каноникал_абсолютный_и_свой():
    в = о(путь="/catalog/").decode()
    assert '<link rel="canonical" href="https://lordfilm47.space/catalog/">' in в


def test_каноникал_срезает_сортировку_но_хранит_фильтр():
    assert S.канонический_путь("/catalog/?kind=Фильм&sort=year&utm_source=a") == "/catalog/?kind=Фильм"


def test_каноникал_не_межсайтовый():
    в = о(хост="zonafilm.space", путь="/").decode()
    ссылки = re.findall(r'rel="canonical" href="https://([^/"]+)', в)
    assert ссылки == ["zonafilm.space"]


def test_на_404_нет_ни_каноникала_ни_схемы():
    """Канонический адрес у страницы, которой нет, — указание считать ошибку
    содержимым."""
    в = о(код=404)
    assert b'rel="canonical"' not in в
    assert b"ld+json" not in в
    assert в.count(b"metrika/tag.js") == 1, "просмотр 404 — тоже факт, тег остаётся"


def test_чужой_каноникал_не_перебивается():
    тело = b'<html><head><link rel="canonical" href="https://x/"></head><body></body></html>'
    assert о(тело=тело).count(b'rel="canonical"') == 1


# --- схема -----------------------------------------------------------------
def test_на_чистой_странице_есть_сайт_и_крошки():
    типы = set(re.findall(r'"@type":"([A-Za-z]+)"', о(путь="/catalog/").decode()))
    assert {"WebSite", "BreadcrumbList"} <= типы


def test_сущность_добавляется_по_виду():
    for вид, ожидание in (("Фильм", "Movie"), ("Мультфильм", "Movie"),
                          ("Сериал", "TVSeries")):
        в = о(путь="/title/x/", сущность={"kind": вид, "title": "T", "slug": "x"}).decode()
        assert f'"@type":"{ожидание}"' in в, вид


def test_чужая_схема_не_дублируется_но_дополняется():
    тело = (b'<html><head><script type="application/ld+json">'
            b'{"@type":"Movie","name":"x"}</script></head><body></body></html>')
    типы = re.findall(r'"@type":"([A-Za-z]+)"', о(тело=тело, путь="/title/x/").decode())
    assert типы.count("Movie") == 1, "Movie задублирован"
    assert "WebSite" in типы and "BreadcrumbList" in типы


def test_поиск_объявляется_только_когда_передан():
    без = о().decode()
    assert "SearchAction" not in без
    с = о(поиск="/search/?q={search_term_string}").decode()
    assert "SearchAction" in с


def test_в_схеме_нет_выдуманных_величин():
    """Ни рейтинга, ни числа голосов, ни актёров: их в каталоге нет."""
    в = о(путь="/title/x/", сущность={"kind": "Фильм", "title": "T", "slug": "x",
                                      "year": 2011}).decode()
    for выдумка in ("aggregateRating", "ratingValue", "reviewCount", "actor",
                    "director", "duration"):
        assert выдумка not in в, выдумка


# --- sitemap ---------------------------------------------------------------
def test_карта_дробится_на_части_под_пределом():
    ф = S.построить_sitemap("d.ru", [{"slug": f"s{i}"} for i in range(95_000)], ["/"])
    части = [(и, д) for и, д in ф if not S.это_индекс(д)]
    assert len(части) == 3
    for _, д in части:
        assert д.count(b"<loc>") <= S.ПРЕДЕЛ_URL
    индекс = next(д for _, д in ф if S.это_индекс(д))
    assert индекс.count(b"<loc>") == 3


def test_в_карте_только_свой_домен_и_https():
    ф = S.построить_sitemap("d.ru", [{"slug": "a"}, {"url": "/title/b/"}], ["/"])
    for _, д in ф:
        for loc in re.findall(rb"<loc>([^<]+)</loc>", д):
            assert loc.startswith(b"https://d.ru/"), loc


def test_дубли_в_карту_не_попадают():
    ф = S.построить_sitemap("d.ru", [{"slug": "a"}, {"slug": "a"},
                                     {"url": "/title/a/"}], ["/", "/"])
    части = [д for и, д in ф if not S.это_индекс(д)]
    все = [l for д in части for l in re.findall(rb"<loc>([^<]+)</loc>", д)]
    assert len(все) == len(set(все))


def test_lastmod_только_когда_дата_известна():
    ф = S.построить_sitemap("d.ru", [{"slug": "a", "lastmod": "2026-01-02"},
                                     {"slug": "b"}], [])
    часть = next(д for и, д in ф if not S.это_индекс(д))
    assert часть.count(b"<lastmod>") == 1


def test_карта_разбирается_как_xml():
    for _, д in S.построить_sitemap("d.ru", [{"slug": "a"}], ["/"]):
        ET.fromstring(д)


def test_запись_атомарна(tmp_path):
    """Сбой посреди записи не оставляет половину карты."""
    плохие = [("sitemap-1.xml", b"<a/>"), ("sitemap.xml", None)]
    with pytest.raises(TypeError):
        S.записать_атомарно(tmp_path, плохие)
    assert list(tmp_path.glob("sitemap*.xml")) == [], "остались части неудачной записи"
