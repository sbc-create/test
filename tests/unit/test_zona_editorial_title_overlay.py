"""Редакционное название накладывается, остальные поля записи не теряются.

Повод — передачи окна ZONA о сохранности постеров и названий при обновлении
каталога. Про сам каталог отвечает отдельное измерение
(`automation/local/catalog-field-retention.py`): на поколениях 08.10 → 10.10
потерянных постеров и русских названий нет. Здесь сторожится вторая половина
вопроса: накладка редактора заменяет НАЗВАННОЕ поле и не трогает остальные.

Проверяется ВЫЛОЖЕННЫЙ модуль ячейки (`editorial_overlay.py` из текущего
выпуска zonafilm.cc), а не копия в репозитории: на странице работает он.
Отсутствие выпуска на машине — пропуск с названной причиной, а не ложный успех.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

МОДУЛЬ = Path("/srv/zonafilm-cc/current/src/editorial_overlay.py")


@pytest.fixture()
def накладка(tmp_path):
    if not МОДУЛЬ.is_file():
        pytest.skip(f"выложенного модуля накладки нет: {МОДУЛЬ}")
    спец = importlib.util.spec_from_file_location("zona_editorial_overlay", МОДУЛЬ)
    модуль = importlib.util.module_from_spec(спец)
    sys.modules["zona_editorial_overlay"] = модуль
    спец.loader.exec_module(модуль)
    файл = tmp_path / "editorial-overrides.json"
    файл.write_text(json.dumps({
        "schema_version": 1,
        "site_id": "zona-02",
        "overrides": {
            "01a0e275-e7d6-7115-a9dc-b066b28183f1": {
                "fields": {"name": "Ад Джеффри (режиссёрская версия)"},
                "reason": "редакционное название",
            },
        },
    }, ensure_ascii=False), encoding="utf-8")
    н = модуль.Правки(str(файл), "zona-02") if hasattr(модуль, "Правки") else None
    if н is None:
        pytest.skip("в модуле нет класса Правки — форма изменилась")
    н.перечитать()
    return модуль, н


ЗАПИСЬ = {
    "id": "01a0e275-e7d6-7115-a9dc-b066b28183f1",
    "slug": "ad-dzheffri",
    "title": "Ад Джеффри",
    "original_title": "Jeffrey Hell",
    "poster": "https://poster.cdnvideohub.com/01a0e275.webp",
    "year": 2024,
    "kind": "Фильм",
    "url": "/title/ad-dzheffri/",
    "published_at": "2026-09-20T10:00:00Z",
}


def test_редакционное_название_подставляется(накладка):
    _, н = накладка
    новая = н.наложить_на_запись(dict(ЗАПИСЬ))
    assert новая["title"] == "Ад Джеффри (режиссёрская версия)"


def test_остальные_поля_записи_не_теряются(накладка):
    """Главное свойство: накладка меняет названное, а не подменяет запись."""
    _, н = накладка
    новая = н.наложить_на_запись(dict(ЗАПИСЬ))
    for поле in ("id", "slug", "original_title", "poster", "year", "kind",
                 "url", "published_at"):
        assert новая[поле] == ЗАПИСЬ[поле], поле
    # Признак правки добавляется — по нему витрина отличает редакционное.
    assert новая.get("_edited") is True


def test_запись_без_правки_возвращается_как_есть(накладка):
    _, н = накладка
    чужая = {**ЗАПИСЬ, "id": "ffffffff-0000-0000-0000-000000000000",
             "slug": "drugoe"}
    assert н.наложить_на_запись(dict(чужая)) == чужая


def test_правка_чужого_сайта_не_применяется(tmp_path):
    """Файл принадлежит другому сайту — правки не берутся, и причина названа."""
    if not МОДУЛЬ.is_file():
        pytest.skip(f"выложенного модуля накладки нет: {МОДУЛЬ}")
    спец = importlib.util.spec_from_file_location("zona_editorial_overlay2", МОДУЛЬ)
    модуль = importlib.util.module_from_spec(спец)
    sys.modules["zona_editorial_overlay2"] = модуль
    спец.loader.exec_module(модуль)
    файл = tmp_path / "editorial-overrides.json"
    файл.write_text(json.dumps({
        "site_id": "zona-03",
        "overrides": {ЗАПИСЬ["id"]: {"fields": {"name": "Чужое"}}},
    }, ensure_ascii=False), encoding="utf-8")
    н = модуль.Правки(str(файл), "zona-02")
    н.перечитать()
    assert н.наложить_на_запись(dict(ЗАПИСЬ))["title"] == ЗАПИСЬ["title"]
    assert "принадлежит сайту" in (н.причина or "")


def test_пустое_значение_правкой_не_считается(накладка, tmp_path):
    """Пустая строка в накладке не стирает настоящее название.

    Иначе случайно сохранённое пустое поле снесло бы название на странице, а
    выглядело бы как «редактор так решил».
    """
    модуль, _ = накладка
    файл = tmp_path / "пустая.json"
    файл.write_text(json.dumps({
        "site_id": "zona-02",
        "overrides": {ЗАПИСЬ["id"]: {"fields": {"name": "", "poster_url": None}}},
    }, ensure_ascii=False), encoding="utf-8")
    н = модуль.Правки(str(файл), "zona-02")
    н.перечитать()
    новая = н.наложить_на_запись(dict(ЗАПИСЬ))
    assert новая["title"] == ЗАПИСЬ["title"]
    assert новая["poster"] == ЗАПИСЬ["poster"]
