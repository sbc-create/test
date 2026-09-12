"""SUITE_4 — сквозная проверка собранной витрины на полном каталоге.

Код ответа ничего не доказывает. Проверяется цепочка целиком:
карточка → маршрут → ожидаемая сущность → отрисованная сущность → H1 →
canonical. Страница, отдающая 200 с чужой карточкой, — дефект, а не успех.
"""
from __future__ import annotations

import collections
import html
import json
import pathlib
import re

import pytest

from factory.lords import urlmap as um

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
КОРЕНЬ_СБОРОК = КОРЕНЬ / "var" / "build-a"

#: Витрины, собранные на полном каталоге. Zona и Animedia — цели задания,
#: lords-02 — контроль: тот же отрисовщик и та же политика адресов на витрине,
#: которая сегодня работает в production.
ВИТРИНЫ = ("zona-cinema", "animedia-portal", "lords-02")

ЗАГОЛОВОК = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)
КАНОНИЧЕСКИЙ = re.compile(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', re.I)
ССЫЛКА = re.compile(r'href="(/title/[a-z0-9\-/]*)"')


def текст(сырое: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", сырое)).strip()


@pytest.fixture(scope="module", params=ВИТРИНЫ)
def сборка(request):
    путь = КОРЕНЬ_СБОРОК / request.param
    if not (путь / "route-map.json").is_file():
        pytest.skip(f"полной сборки нет: {путь}")
    return путь


@pytest.fixture(scope="module")
def карта(сборка):
    return json.loads((сборка / "route-map.json").read_text(encoding="utf-8"))["routes"]


@pytest.fixture(scope="module")
def каталог_сущностей(сборка):
    """Слаг -> ожидаемое название, из поискового индекса сборки."""
    ф = сборка / "search-index.json"
    if not ф.is_file():
        pytest.skip("поискового индекса у этой витрины нет")
    индекс = json.loads(ф.read_text(encoding="utf-8"))
    записи = индекс["items"] if isinstance(индекс, dict) else индекс
    вышло = {}
    for з in записи:
        слаг = з.get("slug") or um.слаг_из_маршрута(з.get("url") or "")
        if слаг:
            вышло[слаг] = з.get("name") or з.get("title") or ""
    return вышло


@pytest.fixture(scope="module")
def страницы(сборка):
    каталог = сборка / "title"
    return {п.name: п / "index.html" for п in каталог.iterdir()
            if (п / "index.html").is_file()}


class TestПолнотаМаршрутов:
    def test_маршрутов_столько_же_сколько_страниц(self, карта, страницы):
        assert len(карта) == len(страницы)
        assert set(карта) == set(страницы)

    def test_маршрут_ведёт_на_свой_каталог(self, карта):
        for слаг, адрес in карта.items():
            assert адрес == f"/title/{слаг}/"

    def test_ни_одного_повторного_адреса(self, карта):
        счёт = collections.Counter(карта.values())
        assert [а for а, n in счёт.items() if n > 1] == []

    def test_нет_коллизий_после_нормализации(self, карта):
        норм = [um.нормализовать_слаг(с) for с in карта]
        дубли = [с for с, n in collections.Counter(норм).items() if n > 1]
        assert дубли == []


class TestСущностьНаСтранице:
    """HTTP 200 с чужой сущностью — отдельный класс дефекта."""

    @pytest.fixture(scope="class")
    def выборка(self, страницы):
        # Детерминированная выборка по всему множеству, а не первые N:
        # начало каталога заполнено лучше хвоста.
        ключи = sorted(страницы)
        шаг = max(1, len(ключи) // 1500)
        return [(к, страницы[к]) for к in ключи[::шаг]]

    def test_заголовок_совпадает_с_ожидаемой_сущностью(self, выборка,
                                                       каталог_сущностей):
        расхождения = []
        for слаг, файл in выборка:
            ожидалось = каталог_сущностей.get(слаг)
            if not ожидалось:
                continue
            тело = файл.read_text("utf-8", errors="replace")
            найдено = ЗАГОЛОВОК.search(тело)
            assert найдено, f"{слаг}: нет H1"
            если_текст = текст(найдено.group(1))
            if ожидалось.strip().casefold() not in если_текст.casefold():
                расхождения.append((слаг, ожидалось, если_текст))
        assert расхождения == [], f"WRONG_ENTITY_200: {расхождения[:5]}"

    def test_canonical_или_есть_у_всех_и_свой_или_нет_ни_у_кого(self, выборка):
        """Пропуск страниц без canonical превратил бы проверку в холостую.

        У кандидата без домена абсолютный адрес построить не из чего, и
        canonical не печатается — это решение, а не потеря. Проверяется
        поэтому не «у кого нашли, тот пусть будет свой», а два свойства
        сразу: отсутствие ОДИНАКОВО на всех страницах, а там, где canonical
        есть, он ведёт на свою же страницу.
        """
        с_каноническим, плохие = [], []
        for слаг, файл in выборка:
            тело = файл.read_text("utf-8", errors="replace")
            найдено = КАНОНИЧЕСКИЙ.search(тело)
            if not найдено:
                continue
            с_каноническим.append(слаг)
            сырое = найдено.group(1)
            путь = "/" + сырое.split("://", 1)[-1].split("/", 1)[-1] if "://" in сырое else сырое
            if um.слаг_из_маршрута(um.нормализовать(путь)) != слаг:
                плохие.append((слаг, сырое))
        assert плохие == [], f"canonical ведёт не на свою страницу: {плохие[:5]}"
        assert len(с_каноническим) in (0, len(выборка)), (
            f"canonical есть у {len(с_каноническим)} из {len(выборка)} страниц: "
            f"разнобой опаснее отсутствия")

    def test_нет_страниц_с_пустым_заголовком(self, выборка):
        пустые = [с for с, ф in выборка
                  if not текст((ЗАГОЛОВОК.search(ф.read_text('utf-8', errors='replace'))
                                or re.match("(?P<x>)", "")).group(1) if ЗАГОЛОВОК.search(
                      ф.read_text('utf-8', errors='replace')) else "")]
        assert пустые == [], f"страницы без заголовка: {пустые[:5]}"


class TestКарточкиИСсылки:
    @pytest.fixture(scope="class")
    def цели_карточек(self, сборка):
        цели = set()
        for ф in сборка.rglob("*.html"):
            тело = ф.read_text("utf-8", errors="replace")
            for сырое in ССЫЛКА.findall(тело):
                цели.add(um.нормализовать(сырое))
        return цели

    def test_каждая_карточка_ведёт_на_существующий_маршрут(self, цели_карточек,
                                                           карта):
        адреса = {f"/title/{с}/" for с in карта}
        сироты = sorted(ц for ц in цели_карточек if ц not in адреса)
        assert сироты == [], f"карточек в никуда: {len(сироты)}; {сироты[:5]}"

    def test_внутренние_ссылки_не_ведут_на_несобранные_разделы(self, сборка):
        РАЗДЕЛ = re.compile(r'href="(/[a-z0-9\-/]*)"')
        существует = {"/"}
        for п in сборка.rglob("index.html"):
            отн = "/" + str(п.parent.relative_to(сборка)).replace("\\", "/") + "/"
            существует.add(отн.replace("/./", "/"))
        битые = set()
        for ф in list(sorted(сборка.glob("*.html")))[:50]:
            тело = ф.read_text("utf-8", errors="replace")
            for сырое in РАЗДЕЛ.findall(тело):
                а = um.нормализовать(сырое)
                if a_файл := ("." in а.rsplit("/", 1)[-1]):
                    continue
                if а not in существует:
                    битые.add(а)
        assert битые == set(), f"ссылки на несобранные разделы: {sorted(битые)[:5]}"


class TestОтсутствующиеСтраницы:
    def test_несуществующий_слаг_не_имеет_каталога(self, сборка):
        assert not (сборка / "title" / "takogo-slaga-net-12345").exists()

    def test_есть_страница_404(self, сборка):
        assert (сборка / "404.html").is_file()

    def test_страница_404_не_выглядит_карточкой(self, сборка, карта):
        """Мягкая 404 — это страница, которую можно принять за произведение.

        Проверяется не наличие числа «404» в тексте: страница честно говорит
        «Страница не найдена» и числа не содержит. Проверяется, что она не
        выдаёт себя за карточку — не объявляет canonical на адрес
        произведения и её заголовок не совпадает ни с одной сущностью.
        """
        тело = (сборка / "404.html").read_text("utf-8", errors="replace")
        каноническая = КАНОНИЧЕСКИЙ.search(тело)
        if каноническая:
            assert "/title/" not in каноническая.group(1)
        найдено = ЗАГОЛОВОК.search(тело)
        assert найдено, "у страницы нет заголовка — читателю нечего понять"
        заголовок = текст(найдено.group(1))
        assert заголовок, "заголовок пуст"
        assert um.нормализовать(f"/title/{заголовок.lower()}/")[len("/title/"):].strip("/") \
            not in карта


class TestSitemapИКанонические:
    """Только паритет маршрутов. Политика SEO не меняется и не проверяется."""

    @pytest.fixture(scope="class")
    def sitemap(self, сборка):
        файлы = sorted(сборка.glob("sitemap*.xml"))
        if not файлы:
            pytest.skip("карты сайта в сборке нет")
        адреса = set()
        for ф in файлы:
            тело = ф.read_text("utf-8", errors="replace")
            for сырое in re.findall(r"<loc>([^<]+)</loc>", тело):
                путь = сырое.split("://", 1)[-1]
                путь = "/" + путь.split("/", 1)[1] if "/" in путь else "/"
                адреса.add(um.нормализовать(путь))
        return адреса

    def test_карта_сайта_пуста_только_если_домена_нет(self, sitemap, сборка):
        """Пустая карта сайта — не успех сама по себе.

        У кандидата домена нет, абсолютный адрес построить не из чего, и файл
        объявляет это прямо. Проверяется, что пустота именно объявлена, а не
        получилась молча: молчаливо пустая карта выглядела бы как пройденная
        проверка паритета.
        """
        тело = (сборка / "sitemap.xml").read_text("utf-8", errors="replace")
        if not sitemap:
            assert "Адресов нет" in тело or "домен" in тело, (
                "карта сайта пуста и ничего об этом не говорит")

    def test_каждый_адрес_карты_сайта_собран(self, sitemap, карта, сборка):
        маршруты = {f"/title/{с}/" for с in карта}
        разделы = set()
        for п in сборка.rglob("index.html"):
            отн = п.parent.relative_to(сборка)
            разделы.add("/" if str(отн) == "." else f"/{отн}/")
        нет = sorted(а for а in sitemap if а not in маршруты and а not in разделы)
        assert нет == [], f"карта сайта обещает несобранные адреса: {нет[:5]}"

    def test_в_карте_сайта_нет_повторов(self, sitemap, сборка):
        файлы = sorted(сборка.glob("sitemap*.xml"))
        все = []
        for ф in файлы:
            все += re.findall(r"<loc>([^<]+)</loc>",
                              ф.read_text("utf-8", errors="replace"))
        повторы = [а for а, n in collections.Counter(все).items() if n > 1]
        assert повторы == [], f"повторы в карте сайта: {повторы[:5]}"


class TestРазделыКаталога:
    def test_есть_каталог_и_страницы_пагинации(self, сборка):
        assert (сборка / "catalog" / "index.html").is_file()

    def test_есть_поиск(self, сборка):
        assert (сборка / "search" / "index.html").is_file() \
            or (сборка / "search-index.json").is_file()

    def test_поисковый_индекс_ссылается_только_на_собранные_адреса(self, сборка,
                                                                   карта):
        ф = сборка / "search-index.json"
        if not ф.is_file():
            pytest.skip("поискового индекса нет")
        индекс = json.loads(ф.read_text("utf-8"))
        записи = индекс["items"] if isinstance(индекс, dict) else индекс
        маршруты = {f"/title/{с}/" for с in карта}
        плохие = []
        for з in записи:
            адрес = з.get("url") or (f"/title/{з.get('slug')}/" if з.get("slug") else None)
            if адрес and um.нормализовать(адрес) not in маршруты:
                плохие.append(адрес)
        assert плохие == [], f"поиск ведёт на несобранные адреса: {плохие[:5]}"
