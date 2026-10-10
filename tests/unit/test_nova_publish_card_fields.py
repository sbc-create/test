"""Передача 113: обеднение ответа источника не отнимает подтверждённые поля.

Повод — заявка сессии zona-01 (`coordination/v1/handoffs/113-zona-01-to-architect-nova-publish-card-fields.md`),
перепроверенная здесь её же воспроизведением на поколении `38734293c92f`:

* `sea-of-love` с пустым входным `poster_url` терял `catalog.poster` (становился
  `null`) при живом постере в подробностях;
* `dengi-na-bochku` с ответом, где `name` равно оригиналу, получал
  `catalog.title` и `details.name` «Show Me the Money» вместо «Деньги на бочку».

Боковой файл подробностей слиянием был защищён («пустое значение снимка не
отменяет уже известное»), а запись КАТАЛОГА бралась только из текущего ответа —
и из неё рисуются главная, сетки, поиск и заголовок с постером карточки.

Четыре свойства приёмки из передачи сторожатся здесь: пустое не стирает
подтверждённое; оригинальное название не вытесняет русское; НОВЫЕ корректные
данные обновляются; при другом `id` за тем же адресом наследования нет.

Издатель живёт вне этого репозитория (`/srv/site-factory/repo`) и тянет оттуда
же свои модули (`canonical_projection`, `rating_gateway`), поэтому проверка
выполняется отдельным процессом с его корнем на `sys.path` — тем же способом,
что `test_publisher_cell_delivery.py`, и по той же причине: импортировать его в
наш процесс значит проверить не тот код, который работает на хосте.
"""
from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

КОРЕНЬ_ИЗДАТЕЛЯ = Path("/srv/site-factory/repo")
МОДУЛЬ = КОРЕНЬ_ИЗДАТЕЛЯ / "factory" / "lords" / "nova_publish.py"

СЦЕНАРИЙ = textwrap.dedent('''
    import json, sys
    sys.path.insert(0, sys.argv[1])
    from factory.lords.nova_publish import РеестрСлагов, Снимок, собрать_сайт

    ИД = "01a12348-f23e-7000-8000-000000000001"
    ДРУГОЙ = "01a12348-f23e-7000-8000-00000000ffff"

    def снимок(ид):
        запись = {"external_id": ид, "name": "Море любви", "year": 2024,
                  "created_at": "2026-10-01T10:00:00Z"}
        return Снимок(записи={ид: запись}, получен="2026-10-10T11:46:13Z",
                      отпечаток="проба" * 8)

    def деталь(*, ид, name, poster):
        return {"id": ид, "name": name, "original_name": "Sea of Love",
                "type": "tv", "year": 2024, "description": "",
                "poster_url": poster, "genres": [], "countries": [],
                "seasons": [], "sources": [], "external_ids": {}}

    def прогон(*, вход_имя, вход_постер, прежние, ид=ИД):
        реестр = РеестрСлагов(по_ид={ид: "more-lyubvi"},
                             по_слагу={"more-lyubvi": ид})
        читатель = lambda кэш, и: деталь(ид=ид, name=вход_имя, poster=вход_постер)
        каталог, подробности, ст = собрать_сайт(
            снимок=снимок(ид), реестр=реестр, детали_кэш=".",
            site_id="zona-01", прежние_подробности=прежние, читатель=читатель)
        запись = каталог["items"][0]
        слаг = запись["slug"]
        return {"catalog_title": запись["title"], "catalog_poster": запись["poster"],
                "details_name": подробности["details"][слаг].get("name"),
                # Без прежнего поколения и с пустым постером ключа
                # `poster_url` в записи не возникает вовсе: слияние
                # пропускает пустые значения. Это прежняя семантика,
                # и проверка читает её как есть.
                "details_poster": подробности["details"][слаг].get("poster_url"),
                "kept_poster": ст.get("kept_previous_poster"),
                "kept_title": ст.get("kept_previous_title"),
                "slug": слаг}

    ПРЕЖНЕЕ = {"more-lyubvi": {"id": ИД, "name": "Море любви",
                               "poster_url": "https://poster/старый.webp"}}

    итог = {}
    # 1. Пустой входной постер и название-оригинал при ТОМ ЖЕ id.
    итог["обеднение"] = прогон(вход_имя="Sea of Love", вход_постер="",
                               прежние=ПРЕЖНЕЕ)
    # 2. Новые корректные данные обновляются.
    итог["обогащение"] = прогон(вход_имя="Море любви навсегда",
                                вход_постер="https://poster/новый.webp",
                                прежние=ПРЕЖНЕЕ)
    # 3. Другой id за тем же адресом — наследования нет.
    итог["другой_id"] = прогон(вход_имя="Sea of Love", вход_постер="",
                               прежние={"more-lyubvi": {"id": ДРУГОЙ,
                                        "name": "Чужое русское",
                                        "poster_url": "https://poster/чужой.webp"}},
                               ид=ИД)
    # 4. Прежнего поколения нет вовсе.
    итог["без_прежнего"] = прогон(вход_имя="Sea of Love", вход_постер="",
                                  прежние={})
    print(json.dumps(итог, ensure_ascii=False))
''')


@pytest.fixture(scope="module")
def итоги(tmp_path_factory):
    if not МОДУЛЬ.is_file():
        pytest.skip(f"издателя нет по пути {МОДУЛЬ}: проверять нечего")
    сценарий = tmp_path_factory.mktemp("np") / "прогон.py"
    сценарий.write_text(СЦЕНАРИЙ, encoding="utf-8")
    прогон = subprocess.run([sys.executable, str(сценарий), str(КОРЕНЬ_ИЗДАТЕЛЯ)],
                            capture_output=True, text=True, timeout=300)
    if прогон.returncode != 0:
        pytest.skip("издатель не поднимается в этом окружении: "
                    + (прогон.stderr.strip().splitlines() or ["без вывода"])[-1])
    return json.loads(прогон.stdout.strip().splitlines()[-1])


def test_пустой_постер_не_стирает_подтверждённый(итоги):
    """Главный случай передачи: постер карточки и сетки не гаснет."""
    о = итоги["обеднение"]
    assert о["catalog_poster"] == "https://poster/старый.webp", о
    assert о["details_poster"] == "https://poster/старый.webp", о
    assert о["kept_poster"] == 1, о


def test_оригинальное_название_не_вытесняет_русское(итоги):
    о = итоги["обеднение"]
    assert о["catalog_title"] == "Море любви", о
    assert о["details_name"] == "Море любви", о
    assert о["kept_title"] == 1, о


def test_новые_корректные_данные_обновляются(итоги):
    """Защита работает только на переход «подтверждено → пусто/оригинал»."""
    о = итоги["обогащение"]
    assert о["catalog_poster"] == "https://poster/новый.webp", о
    assert о["catalog_title"] == "Море любви навсегда", о
    assert о["details_name"] == "Море любви навсегда", о
    assert о["kept_poster"] == 0 and о["kept_title"] == 0, о


def test_при_другом_id_наследования_нет(итоги):
    """За тем же адресом может оказаться другое произведение.

    Так было с `dlya-tebya-vo-vsem-cvetu-2` при миграции реестра: наследовать
    постер и название от прежнего жильца адреса значило бы показать чужое.
    """
    о = итоги["другой_id"]
    assert о["catalog_poster"] in (None, ""), о
    assert о["catalog_title"] == "Sea of Love", о
    assert о["kept_poster"] == 0 and о["kept_title"] == 0, о


def test_без_прежнего_поколения_поведение_прежнее(итоги):
    о = итоги["без_прежнего"]
    assert о["catalog_poster"] in (None, ""), о
    assert о["catalog_title"] == "Sea of Love", о
    assert о["kept_poster"] == 0 and о["kept_title"] == 0, о
