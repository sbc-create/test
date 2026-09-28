"""Золотая фикстура: сериал с 210 сериями.

Повод — известный дефект соседнего семейства: селектор обрывался на сотой
серии при двухстах десяти в данных. Зритель, дошедший до сто первой, упирался
в пустоту, и страница об этом молчала.

В боевом каталоге сезона ровно с 210 сериями нет (есть 32 сезона с двумя
сотнями и больше, крупнейший — 1212). Поэтому фикстура синтетическая: она
проверяет поведение шаблона на заданной границе, а не наличие записи.

Чего этот набор НЕ проверяет и почему
-------------------------------------

Требования к адресу серии — свой URL, свой `<title>`, свой canonical,
переходы «предыдущая/следующая» — на этом шаблоне невыполнимы: у серий нет
собственных адресов, они перечислены списком на странице произведения.
Сделать их адресуемыми означает выпустить отдельную страницу на каждую серию:
в каталоге 8855 записей с сериями, и это решение о размере витрины, времени
сборки и поисковой поверхности, а не правка вёрстки.

Здесь это зафиксировано отдельным тестом, чтобы отсутствие адресации нельзя
было принять за выполненное требование.
"""
from __future__ import annotations

import pathlib
import re

import pytest

from factory.lords import fixtures as fx
from factory.lords import preview as preview_mod
from factory.lords import render as render_mod

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ВСЕГО = 210
ГРАНИЦЫ = (1, 2, 99, 100, 101, 209, 210)

СЕРИЯ = re.compile(r'<li class="episode"><span>Серия (\d+)</span>')
СЕЗОН = re.compile(r"<summary>Сезон (\d+) · ([^<]*)</summary>")


@pytest.fixture(scope="module")
def каталог_210():
    """Каталог из одной записи: сериал с 210 сериями в одном сезоне."""
    базовый = fx.build_catalog()
    образец = next((t for t in базовый.titles if getattr(t, "episodic", False)), None)
    if образец is None:
        образец = базовый.titles[0]
    серии = tuple(fx.Episode(number=n, name=f"Серия {n}", runtime_min=24)
                  for n in range(1, ВСЕГО + 1))
    сезон = fx.Season(number=1, episodes=серии, declared_episodes=ВСЕГО)
    from dataclasses import replace
    запись = replace(образец, slug="golden-210", name="Золотая фикстура: 210 серий",
                     seasons=(сезон,))
    return type(базовый)(titles=(запись,), collections=(),
                         _by_slug={запись.slug: запись})


@pytest.fixture(scope="module")
def страница(каталог_210) -> str:
    пакет, _ = preview_mod._package("lords-02")
    сайт = render_mod.render_site(пакет, catalog=каталог_210, environ={},
                                  publisher_id="1",
                                  only_title_slugs=frozenset({"golden-210"}))
    стр = сайт.pages.get("/title/golden-210/")
    assert стр is not None, "страница фикстуры не собралась"
    тело = стр.body
    return тело if isinstance(тело, str) else тело.decode("utf-8", "replace")


class TestВсе210СерийНаМесте:
    def test_данные_содержат_210(self, каталог_210):
        запись = каталог_210.titles[0]
        assert sum(len(с.episodes) for с in запись.seasons) == ВСЕГО

    def test_отрисованы_все_210(self, страница):
        серии = [int(n) for n in СЕРИЯ.findall(страница)]
        assert len(серии) == ВСЕГО, (
            f"отрисовано {len(серии)} серий из {ВСЕГО}: список обрезан")

    def test_нет_обрыва_на_сотой(self, страница):
        серии = {int(n) for n in СЕРИЯ.findall(страница)}
        assert 100 in серии and 101 in серии, (
            "сто первой серии нет: ровно тот дефект, ради которого заведена "
            "эта фикстура")

    @pytest.mark.parametrize("номер", ГРАНИЦЫ)
    def test_граничная_серия_на_месте(self, страница, номер):
        серии = {int(n) for n in СЕРИЯ.findall(страница)}
        assert номер in серии

    def test_номера_подряд_и_без_повторов(self, страница):
        серии = [int(n) for n in СЕРИЯ.findall(страница)]
        assert серии == list(range(1, ВСЕГО + 1)), (
            "номера серий не образуют сплошной ряд от 1 до 210")

    def test_номер_не_подменяется_позицией(self, страница):
        серии = [int(n) for n in СЕРИЯ.findall(страница)]
        assert серии[100] == 101 and серии[209] == 210

    def test_объявленное_число_совпадает_с_отрисованным(self, страница):
        м = СЕЗОН.search(страница)
        assert м, "заголовок сезона не найден"
        объявлено = re.search(r"(\d+)", м.group(2))
        assert объявлено and int(объявлено.group(1)) == ВСЕГО
        assert len(СЕРИЯ.findall(страница)) == ВСЕГО


class TestЗаголовкиИМетаданные:
    def test_заголовок_страницы_о_произведении(self, страница):
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", страница, re.S)
        assert h1 and "210 серий" in re.sub(r"<[^>]+>", " ", h1.group(1))

    def test_число_серий_не_застревает_от_прошлой_записи(self, каталог_210):
        """Прежний дефект соседнего семейства: «100 серия» оставалась в
        описании другой записи. Проверяем, что число берётся из своей."""
        запись = каталог_210.titles[0]
        assert sum(len(с.episodes) for с in запись.seasons) == ВСЕГО
        assert "100" not in запись.slug


class TestСписокДостижимБезПрокруткиВбок:
    def test_разметка_не_задаёт_фиксированную_ширину_списка(self, страница):
        """Горизонтальная прокрутка проверяется браузером отдельно; здесь —
        что список не объявляет непереносимую ширину прямо в разметке."""
        блок = re.search(r'<section class="seasons">.*?</section>', страница, re.S)
        assert блок
        assert "white-space:nowrap" not in блок.group(0).replace(" ", "")
        assert "width:" not in блок.group(0).replace(" ", "")[:4000]

    def test_серии_в_упорядоченном_списке(self, страница):
        """`<ol>` даёт экранному диктору номер позиции и порядок."""
        assert re.search(r"<details class=\"season\"[^>]*>.*?<ol>", страница, re.S)


class TestАдресацииСерийПокаНет:
    """Граница, которую нельзя потерять из виду."""

    def test_у_серий_нет_собственных_адресов(self, страница):
        блок = re.search(r'<section class="seasons">.*?</section>', страница, re.S)
        assert блок
        assert re.findall(r"<a\b", блок.group(0)) == [], (
            "у серий появились ссылки: требования к адресу, canonical и "
            "переходам стали выполнимы — проверки нужно расширить")

    def test_отсутствие_адресации_не_выдаётся_за_выполненное(self):
        отчёт = КОРЕНЬ / "docs" / "product" / "LORDS-210-EPISODES-REPORT.md"
        assert отчёт.is_file(), "отчёт о фикстуре не написан"
        текст = отчёт.read_text("utf-8")
        assert "NOT_IMPLEMENTED" in текст or "не адресуемы" in текст
