"""SUITE_6 — быстрый подбор похожего равен полному перебору.

Замена сделана не ради красоты: полный перебор сортировал весь каталог на
каждой из 53 344 страниц, и полная сборка не завершалась. Ускорение имеет
право на существование только пока даёт тот же результат, поэтому здесь
сравнивается именно результат, а не время.
"""
from __future__ import annotations

import json
import pathlib
import random

import pytest

from factory.lords import detail_enrichment as enrich_mod
from factory.lords import live_catalog as live_mod
from factory.lords import render as R

СНИМОК = pathlib.Path(
    "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-02.json")
ВИДЫ = {"animation", "movies", "series", "anime"}


@pytest.fixture(scope="module")
def каталог():
    if not СНИМОК.is_file():
        pytest.skip(f"снимка каталога нет: {СНИМОК}")
    сырое = json.loads(СНИМОК.read_text(encoding="utf-8"))
    элементы = сырое["items"] if isinstance(сырое, dict) else сырое
    детали, _ = enrich_mod.load_cached_details(
        pathlib.Path("/srv/site-factory/repo/var/lords/detail-cache"))
    слитые, _ = enrich_mod.merge_cached(элементы, детали)
    return live_mod.catalog_from_live(слитые)


class TestРавенствоПолномуПеребору:
    def test_случайная_выборка(self, каталог):
        выборка = random.Random(20260912).sample(list(каталог.titles), 40)
        расхождения = []
        for т in выборка:
            быстро = [x.slug for x in R._похожие(каталог, т, ВИДЫ, 8)]
            полно = [x.slug for x in R._related_полным_перебором(каталог, т, ВИДЫ, 8)]
            if быстро != полно:
                расхождения.append((т.slug, быстро[:3], полно[:3]))
        assert расхождения == [], f"порядок изменился: {расхождения[:3]}"

    def test_запись_без_жанров(self, каталог):
        """Самый опасный случай: общих жанров нет, порядок решают тип и год."""
        без = [t for t in каталог.titles if not t.genre_slugs][:12]
        assert без, "в каталоге нет записей без жанров — проверять нечего"
        for т in без:
            assert ([x.slug for x in R._похожие(каталог, т, ВИДЫ, 8)]
                    == [x.slug for x in R._related_полным_перебором(каталог, т, ВИДЫ, 8)])

    def test_запись_с_редким_жанром(self, каталог):
        """Жанровых соседей меньше лимита — добор идёт из остальных."""
        по_жанру = {}
        for т in каталог.titles:
            for ж in т.genre_slugs:
                по_жанру.setdefault(ж, []).append(т)
        редкие = sorted(по_жанру.items(), key=lambda п: len(п[1]))[:5]
        проверено = 0
        for _, записи in редкие:
            for т in записи[:3]:
                assert ([x.slug for x in R._похожие(каталог, т, ВИДЫ, 8)]
                        == [x.slug for x in R._related_полным_перебором(каталог, т, ВИДЫ, 8)])
                проверено += 1
        assert проверено >= 5

    def test_подборка_не_содержит_саму_запись(self, каталог):
        for т in list(каталог.titles)[:50]:
            слаги = [x.slug for x in R._похожие(каталог, т, ВИДЫ, 8)]
            assert т.slug not in слаги
            assert len(set(слаги)) == len(слаги)

    def test_все_подобранные_существуют_в_каталоге(self, каталог):
        известные = {t.slug for t in каталог.titles}
        for т in list(каталог.titles)[:50]:
            for x in R._похожие(каталог, т, ВИДЫ, 8):
                assert x.slug in известные
