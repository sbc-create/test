"""Zona: слайдер героя — контракт разметки и вырожденные случаи.

Переключение слайдов — поведение скрипта, и оно снимается браузером
(`artifacts/evidence/zona-slider-real/`). Здесь проверяется то, что браузер
проверить не может дёшево: что слайды РАЗНЫЕ, что органы управления
появляются ровно тогда, когда есть что листать, и что витрина не разваливается
на одном, двух, трёх и восьми элементах.

Отдельно закреплены отрицательные случаи, ради которых этот блок и
переписывался: одна картинка вместо слайдера, повтор одного тайтла под видом
нескольких слайдов, запись без постера в героe, мёртвая кнопка при одном
слайде.
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

import pytest

from tests.lords.zona_kit import (ЗАПИСИ, НЕДЕЛЬНЫЙ_СНИМОК, ПОДРОБНОСТИ,
                                  поднять, запросить)


@pytest.fixture(scope="module")
def зона():
    return поднять(Path(tempfile.mkdtemp()), имя_модуля="nova_zona_hero")


def слайды(тело: str) -> list[str]:
    return re.findall(r"<article class=\"zhero__slide\".*?</article>", тело, re.S)


def поле(слайд: str, имя: str) -> str:
    m = re.search(r'%s="([^"]*)"' % re.escape(имя), слайд)
    return m.group(1) if m else ""


@pytest.fixture(scope="module")
def главная(зона):
    о = запросить(зона, "/")
    assert о.статус == 200
    return о.тело


# --------------------------------------------------------------------------
# Слайды разные
# --------------------------------------------------------------------------

def test_слайдер_не_одна_картинка(главная):
    """Отрицательный тест: ради которого блок и переписывался."""
    assert "data-zhero-slider" in главная, "слайдера нет вовсе"
    assert len(слайды(главная)) >= 2, (
        "в героe меньше двух слайдов — это картинка, а не слайдер")


def test_слайдов_восемь(главная):
    assert len(слайды(главная)) == 8


def test_идентификаторы_названия_и_картинки_уникальны(главная):
    набор = слайды(главная)
    for имя in ("data-slide-id", "data-slide-title"):
        значения = [поле(с, имя) for с in набор]
        assert all(значения), f"пустое {имя} у одного из слайдов"
        assert len(set(значения)) == len(значения), (
            f"повтор {имя}: {[з for з in значения if значения.count(з) > 1]}")
    картинки = re.findall(r'<img src="([^"]+)"[^>]*data-zhero-img>', главная)
    assert len(картинки) == len(набор), "не у каждого слайда своя картинка"
    assert len(set(картинки)) == len(картинки), (
        "одна картинка размножена по слайдам — иллюзия слайдера")


def test_каждый_слайд_ведёт_на_свою_страницу(зона, главная):
    for с in слайды(главная):
        href = поле(с, "data-slide-href")
        assert href.startswith("/title/"), f"слайд ведёт не на произведение: {href}"
        assert запросить(зона, href).статус == 200, f"слайд ведёт в никуда: {href}"


def test_в_героe_нет_записи_без_постера(главная):
    """Запись без постера дала бы пустой слайд."""
    без_постера = {з["slug"] for з in ЗАПИСИ if not з["poster"]}
    показаны = {поле(с, "data-slide-id") for с in слайды(главная)}
    assert показаны & без_постера == set(), (
        f"в героe запись без постера: {показаны & без_постера}")


# --------------------------------------------------------------------------
# Органы управления
# --------------------------------------------------------------------------

def test_управление_есть_и_доступно(главная):
    assert "data-zhero-prev" in главная and "data-zhero-next" in главная
    assert главная.count("data-zhero-dot") - главная.count("[data-zhero-dot]") >= 8
    for подпись in ("Предыдущий слайд", "Следующий слайд"):
        assert подпись in главная, f"кнопка без имени: {подпись}"


def test_кнопки_это_button_а_не_ссылка(главная):
    for направление in ("prev", "next"):
        m = re.search(r"<(\w+)[^>]*data-zhero-%s" % направление, главная)
        assert m and m.group(1) == "button", (
            f"орган управления {направление} — не button")


def test_точки_размечены_как_вкладки(главная):
    точки = re.findall(r"<button[^>]*data-zhero-dot[^>]*>", главная)
    assert len(точки) == 8
    assert all('role="tab"' in т for т in точки)
    assert sum('aria-selected="true"' in т for т in точки) == 1, (
        "активной должна быть ровно одна точка")
    assert all("aria-label=" in т for т in точки), "точка без имени"


def test_карусель_объявлена_ассистивным_технологиям(главная):
    assert 'aria-roledescription="карусель"' in главная
    assert главная.count('aria-roledescription="слайд"') == 8


def test_скрипт_включает_управление_только_после_готовности(главная):
    assert 'data-zhero-ready="0"' in главная, (
        "готовность не объявлена: управление показалось бы до скрипта")
    assert "data-zhero-ready" in главная


def test_ровно_один_h1_на_главной(главная):
    h1 = re.findall(r"<h1\b", главная)
    assert len(h1) == 1, f"H1 на главной: {len(h1)}"


def test_панель_одна_а_не_по_одной_на_слайд(главная):
    assert главная.count("data-zhero-title") - главная.count("[data-zhero-title]") == 1


# --------------------------------------------------------------------------
# Вырожденные случаи: 1, 2, 3 элемента и пустой каталог
# --------------------------------------------------------------------------

def _урезанный(tmp_path, сколько: int, метка: str):
    slugs = [s for s in НЕДЕЛЬНЫЙ_СНИМОК["shelves"]["pop-films"]
             + НЕДЕЛЬНЫЙ_СНИМОК["shelves"]["pop-series"]][:сколько]
    записи = [з for з in ЗАПИСИ if з["slug"] in slugs]
    assert len(записи) == сколько
    weekly = {"week_id": "2026-W38", "digest": "d",
              "shelves": {"pop-films": slugs, "pop-series": [], "pop-anim": []}}
    return поднять(tmp_path, записи=записи,
                   подробности={s: ПОДРОБНОСТИ[s] for s in slugs},
                   weekly=weekly, имя_модуля=f"nova_zona_hero_{метка}")


@pytest.mark.parametrize("сколько", [1, 2, 3])
def test_слайдер_на_малом_наборе(tmp_path, сколько):
    м = _урезанный(tmp_path, сколько, f"n{сколько}")
    тело = запросить(м, "/").тело
    набор = слайды(тело)
    assert len(набор) == сколько, f"{сколько} записей → {len(набор)} слайдов"
    assert len(re.findall(r"<h1\b", тело)) == 1
    if сколько == 1:
        assert "data-zhero-prev" not in тело, (
            "мёртвая кнопка при одном слайде — обещание действия, которого нет")
        assert "data-zhero-dot" not in тело.replace("[data-zhero-dot]", "")
    else:
        assert "data-zhero-prev" in тело and "data-zhero-next" in тело
        точки = re.findall(r"<button[^>]*data-zhero-dot[^>]*>", тело)
        assert len(точки) == сколько


def test_пустой_каталог_даёт_осмысленный_запасной_вариант(tmp_path):
    """Отрицательный тест: без годных записей герой не должен ломаться."""
    м = поднять(tmp_path, записи=[], подробности={}, weekly=None,
                имя_модуля="nova_zona_hero_empty")
    о = запросить(м, "/")
    assert о.статус == 200
    assert "zhero--compact" in о.тело, "нет запасного героя"
    assert len(re.findall(r"<h1\b", о.тело)) == 1
    assert "data-zhero-prev" not in о.тело


def test_повторный_слаг_не_даёт_два_слайда(tmp_path):
    """Отрицательный тест: повтор тайтла — не способ набрать слайды."""
    slugs = ["svezhiy", "svezhiy", "samyy-svezhiy"]
    weekly = {"week_id": "2026-W38", "digest": "d",
              "shelves": {"pop-films": slugs, "pop-series": [], "pop-anim": []}}
    м = поднять(tmp_path, weekly=weekly, имя_модуля="nova_zona_hero_dup")
    набор = слайды(запросить(м, "/").тело)
    ид = [поле(с, "data-slide-id") for с in набор]
    assert len(ид) == len(set(ид)), f"повтор слайда: {ид}"


def test_картинка_слайда_не_перетаскивается_и_имеет_альтернативу(главная):
    картинки = re.findall(r"<img[^>]*data-zhero-img>", главная)
    assert картинки
    for и in картинки:
        assert 'draggable="false"' in и, "нативный drag перехватывает свайп"
        assert "alt=" in и, "картинка слайда без альтернативы"
    assert sum('loading="eager"' in и for и in картинки) == 1, (
        "первый слайд обязан грузиться сразу, остальные — лениво")
