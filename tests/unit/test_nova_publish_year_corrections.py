"""Сверенная поправка года доезжает до каталога и до карточки — в том корне,
куда её выложат.

Повод. Год записи приезжает из ответа поставщика, и у продолжений он несёт дату
ПЕРВОЙ части франшизы. Измерено 20.10 штатным путём к источнику (D199): у
`rukovodstvo-soten-demonov-4` поставщик даёт 2020 (`premiere_date` 2020-04-25),
источник — `aired_on` 2024-02-23. Из 14 строгих кандидатов внутреннего признака
сверка подтвердила 7 неверных; на случайном образце из 300 записей расхождение
года нашлось у 7 из 282 измеренных (≈2,5 %).

Как проверяется и почему именно так. Издатель живёт в своём дереве
(`/srv/site-factory/repo`), часть его зависимостей есть только там, а выложен
там ПРЕЖНИЙ код. Поэтому проверка идёт подпроцессом: корень издателя впереди в
`sys.path` — для зависимостей, а проверяемый файл берётся ИЗ ВЕТКИ. Иначе
проверка смотрела бы на выложенный код и о правке молчала.

Отрицательные контроли, названные заранее:

* **запись без поправки не меняется** — иначе механизм трогал бы весь каталог;
* **поправка не применяется, если поставщик сменил значение после замера** — он
  мог исправиться сам, возможно на третье значение;
* **отсутствие файла поправок рядом с издателем ВИДНО в статистике**
  (`year_corrections_unavailable`). Молчание здесь было бы ровно той ошибкой,
  из-за которой правка «есть в ветке, но не установлена» остаётся незамеченной.
"""
from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
КОРЕНЬ_ИЗДАТЕЛЯ = Path("/srv/site-factory/repo")
МОДУЛЬ_ВЕТКИ = КОРЕНЬ / "factory" / "lords" / "nova_publish.py"

pytestmark = pytest.mark.skipif(
    not (КОРЕНЬ_ИЗДАТЕЛЯ / "factory" / "lords" / "canonical_projection.py").is_file(),
    reason="зависимостей издателя нет в этом окружении")

СЦЕНАРИЙ = textwrap.dedent('''
    import importlib.util, json, sys
    from pathlib import Path
    корень_издателя, модуль_ветки, вид = sys.argv[1], sys.argv[2], sys.argv[3]
    sys.path.insert(0, корень_издателя)

    спец = importlib.util.spec_from_file_location("nova_publish_ветка", модуль_ветки)
    м = importlib.util.module_from_spec(спец)
    sys.modules["nova_publish_ветка"] = м
    спец.loader.exec_module(м)

    ИД = "01918cd7-61fd-75e3-8410-67fe2f763a0d"

    def снимок(тип="tv", год=2020):
        запись = {"external_id": ИД, "name": "Руководство сотен демонов 4",
                  "year": год, "type": тип,
                  "created_at": "2024-11-12T12:20:11Z"}
        return м.Снимок(записи={ИД: запись}, получен="2026-10-20T03:16:43Z",
                        отпечаток="проба" * 8)

    def деталь(тип="tv", год=2020):
        return {"id": ИД, "name": "Руководство сотен демонов 4",
                "original_name": "Bai yao pu", "type": тип, "year": год,
                "description": "", "poster_url": "https://poster/x.webp",
                "genres": ["аниме"], "countries": ["Китай"], "seasons": [],
                "sources": [], "external_ids": {"mal": "57995"}}

    ПОПРАВКА = {"corrections": [{
        "id": ИД, "slug_at_measure": "rukovodstvo-soten-demonov-4",
        "source_id": "57995",
        "source_url": "https://shikimori.io/animes/57995",
        "measured_at": "2026-10-20T13:39:06Z",
        "matching": "external_id_from_record+title_verified",
        "aired_on": "2024-02-23", "year_provider": 2020, "year_source": 2024}]}

    ПОПРАВКА_ВИДА = {"corrections": [{
        "id": ИД, "slug_at_measure": "rukovodstvo-soten-demonov-4",
        "source_id": "57995",
        "source_url": "https://shikimori.io/animes/57995",
        "measured_at": "2026-10-20T13:39:06Z",
        "matching": "external_id_from_record+title_verified",
        "aired_on": "2024-02-23", "type_provider": "tv",
        "type_source": "movie"}]}

    def поправки(документ):
        мод = м._модуль_поправок()
        return мод.разобрать(документ)

    def собрать(*, набор, тип="tv", год=2020, аниме_видом=False):
        реестр = м.РеестрСлагов(по_ид={ИД: "rukovodstvo-soten-demonov-4"},
                                по_слагу={"rukovodstvo-soten-demonov-4": ИД})
        каталог, подробности, ст = м.собрать_сайт(
            снимок=снимок(тип, год), реестр=реестр, детали_кэш=".",
            site_id="animedia-01", читатель=lambda к, и: деталь(тип, год),
            аниме_видом=аниме_видом, поправки_года=набор)
        (запись,) = подробности["details"].values()
        return {"catalog_year": каталог["items"][0]["year"],
                "catalog_kind": каталог["items"][0]["kind"],
                "details_year": запись.get("year"),
                "details_type": запись.get("type"),
                "year_source": запись.get("year_source"),
                "ст": {к: з for к, з in ст.items()
                       if к.startswith(("year_", "type_"))}}

    if вид == "поправка":
        итог = собрать(набор=поправки(ПОПРАВКА))
    elif вид == "без-поправки":
        итог = собрать(набор={})
    elif вид == "поставщик-сменил-год":
        итог = собрать(набор=поправки(ПОПРАВКА), год=2023)
    elif вид == "поправка-вида":
        итог = собрать(набор=поправки(ПОПРАВКА_ВИДА))
    elif вид == "нет-файла-поправок":
        м._ПУТЬ_ПОПРАВОК = Path("/такого/файла/нет/year_corrections.py")
        м._ПОПРАВКИ_МОДУЛЬ = None
        реестр = м.РеестрСлагов(по_ид={ИД: "r"}, по_слагу={"r": ИД})
        каталог, подробности, ст = м.собрать_сайт(
            снимок=снимок(), реестр=реестр, детали_кэш=".",
            site_id="animedia-01", читатель=lambda к, и: деталь())
        (запись,) = подробности["details"].values()
        итог = {"catalog_year": каталог["items"][0]["year"],
                "details_year": запись.get("year"),
                "year_source": запись.get("year_source"),
                "недоступны": ст.get("year_corrections_unavailable")}
    else:
        raise SystemExit(f"неизвестный вид {вид}")
    print(json.dumps(итог, ensure_ascii=False))
''')


def прогон(вид: str) -> dict:
    г = subprocess.run([sys.executable, "-c", СЦЕНАРИЙ, str(КОРЕНЬ_ИЗДАТЕЛЯ),
                        str(МОДУЛЬ_ВЕТКИ), вид],
                       capture_output=True, text=True, timeout=300,
                       cwd=str(КОРЕНЬ))
    assert г.returncode == 0, г.stdout + г.stderr
    return json.loads(г.stdout.strip().splitlines()[-1])


def test_поправка_доезжает_до_каталога_и_карточки():
    итог = прогон("поправка")
    assert итог["catalog_year"] == 2024, "сетка печатает год из каталога"
    assert итог["details_year"] == 2024, "заголовок карточки — из подробностей"
    assert "shikimori.io/animes/57995" in итог["year_source"]
    assert итог["ст"]["year_corrected"] == 1
    assert итог["ст"]["year_correction_stale"] == 0


def test_без_поправки_год_поставщика_остаётся():
    итог = прогон("без-поправки")
    assert итог["catalog_year"] == 2020
    assert итог["details_year"] == 2020
    assert итог["year_source"] == "provider"
    assert итог["ст"]["year_corrected"] == 0


def test_поставщик_сменил_год_поправка_отступает_и_это_видно():
    итог = прогон("поставщик-сменил-год")
    assert итог["catalog_year"] == 2023, "новое значение поставщика не перетирается"
    assert итог["year_source"] == "provider/stale-correction"
    assert итог["ст"]["year_correction_stale"] == 1
    assert итог["ст"]["year_corrected"] == 0


def test_поправка_вида_меняет_и_тип_и_вид_в_сетке():
    итог = прогон("поправка-вида")
    assert итог["details_type"] == "movie"
    assert итог["catalog_kind"] == "Фильм", итог["catalog_kind"]
    assert итог["ст"]["type_corrected"] == 1


def test_отсутствие_файла_поправок_видно_в_статистике():
    """Иначе «правка в ветке, но не установлена» осталась бы незамеченной."""
    итог = прогон("нет-файла-поправок")
    assert итог["недоступны"], "статистика обязана назвать недоступный файл"
    assert "year_corrections.py" in итог["недоступны"]
    assert итог["catalog_year"] == 2020
    assert итог["year_source"] == "provider"
