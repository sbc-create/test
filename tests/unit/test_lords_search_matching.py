"""Нестрогое сопоставление запроса с названием.

Заявленный дефект: «поиск работает только по точному совпадению». На боевой
витрине он не работал вовсе, но требование к сопоставлению от этого не
меняется: зритель набирает с опечаткой, в чужой раскладке, латиницей вместо
кириллицы — и ожидает, что его поймут.

Проверяются свойства, а не реализация. Каждое требование директивы получает
свой случай: нормализация, русские и оригинальные названия, опечатки,
транслитерация, неверная раскладка, детерминированный порядок.

Отдельно проверяется то, чего делать НЕЛЬЗЯ: нестрогость не должна находить
всё подряд. Поиск, отвечающий на «зззззз» половиной каталога, бесполезен ровно
так же, как поиск, не отвечающий ничем.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.lords import search as search_mod  # noqa: E402

CATALOG = [
    {"slug": "100-povarov", "name": "100 поваров", "original": ""},
    {"slug": "temnyy-rycar", "name": "Тёмный рыцарь", "original": "The Dark Knight"},
    {"slug": "zvezdnye-voyny", "name": "Звёздные войны", "original": "Star Wars"},
    {"slug": "matrica", "name": "Матрица", "original": "The Matrix"},
    {"slug": "vlastelin-kolec", "name": "Властелин колец", "original": "The Lord of the Rings"},
]


def найти(query: str, limit: int = 10):
    return [m["slug"] for m in search_mod.search(CATALOG, query, limit=limit)]


class TestНормализация:
    def test_регистр_не_важен(self):
        assert "100-povarov" in найти("ПОВАРОВ")

    def test_лишние_пробелы_не_важны(self):
        assert "100-povarov" in найти("   поваров  ")

    def test_ё_и_е_считаются_одной_буквой(self):
        # Зритель почти никогда не набирает «ё»: раскладка её прячет.
        assert "temnyy-rycar" in найти("темный рыцарь")
        assert "zvezdnye-voyny" in найти("звездные войны")

    def test_знаки_препинания_не_мешают(self):
        assert "vlastelin-kolec" in найти("властелин, колец!")


class TestОригинальныеНазвания:
    def test_поиск_по_оригинальному_названию(self):
        assert "matrica" in найти("matrix")

    def test_частичное_оригинальное_название(self):
        assert "temnyy-rycar" in найти("dark knight")


class TestОпечатки:
    def test_одна_перепутанная_буква(self):
        assert "100-povarov" in найти("поворов")

    def test_пропущенная_буква(self):
        assert "matrica" in найти("матрца")

    def test_лишняя_буква(self):
        assert "matrica" in найти("матррица")

    def test_переставленные_соседние_буквы(self):
        assert "matrica" in найти("мтарица")


class TestРаскладкаИТранслитерация:
    def test_набрано_в_латинской_раскладке(self):
        # «ghbdtn» на русской раскладке — «привет». Здесь: «vfnhbwf» → «матрица».
        assert "matrica" in найти("vfnhbwf")

    def test_транслитерация_латиницей(self):
        assert "matrica" in найти("matrica")
        assert "100-povarov" in найти("povarov")


class TestНестрогостьНеПревращаетсяВоВсё:
    def test_бессмысленный_запрос_не_находит_ничего(self):
        assert найти("зззззз") == [], "нестрогий поиск нашёл несуществующее"

    def test_пустой_запрос_не_находит_ничего(self):
        assert найти("") == []
        assert найти("   ") == []

    def test_одна_буква_не_возвращает_каталог(self):
        # Один символ совпадает почти с чем угодно: выдача по нему — шум.
        assert найти("м") == []


class TestПорядокДетерминирован:
    def test_точное_совпадение_впереди_приблизительного(self):
        results = найти("матрица")
        assert results[0] == "matrica"

    def test_повторный_запрос_даёт_тот_же_порядок(self):
        assert найти("во") == найти("во")

    def test_предел_соблюдается(self):
        assert len(найти("а", limit=2)) <= 2


class TestПодсказкаПриОпечатке:
    """Подсказка уместна ровно в одном случае: выдача пуста, а близкое есть.

    Первая редакция предлагала исправление при отсутствии ТОЧНОГО совпадения,
    и на запрос «поворов», который прекрасно находит «100 поваров» нестрогим
    сравнением, советовала искать «поворот». Подсказка поверх непустой выдачи
    сбивает: зритель видит нужное и рядом совет искать другое.
    """

    def test_при_непустой_выдаче_подсказки_нет(self):
        assert найти("поворов"), "предусловие: запрос находит записи"
        assert search_mod.did_you_mean(CATALOG, "поворов") is None

    def test_подсказывает_когда_выдача_пуста(self):
        # «матрза» отстоит от «матрица» на две правки: выдача такого не берёт,
        # подсказка — берёт.
        assert найти("матрза") == [], "предусловие: выдача пуста"
        suggestion = search_mod.did_you_mean(CATALOG, "матрза")
        assert suggestion and "матриц" in suggestion.lower(), (
            f"подсказка не предложена: {suggestion!r}")

    def test_при_точном_совпадении_подсказки_нет(self):
        assert search_mod.did_you_mean(CATALOG, "матрица") is None

    def test_при_бессмысленном_запросе_подсказки_нет(self):
        assert search_mod.did_you_mean(CATALOG, "зззззз") is None
