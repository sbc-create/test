"""REQ-PLAYBACK: дескриптор строится только по разрешённым агрегаторам.

Здесь закреплена граница, о которую разбилось первоначальное исправление.
Источник отдаёт часть записей только с идентификатором IMDb, и поставщик по
нему возвращает настоящий поток — проверено прямым запросом. Но правило PC-2
замороженного контракта плеера гласит: «IMDb не используется как playback
identifier». Согласие поставщика запрета не отменяет.

Измерено на боевом каталоге 2026-09-05: 645 карточек из 53 216 остаются без
видео именно по этой причине, и оба названных владельцем адреса — из их числа.
Это решение владельца контракта, а не пробел в коде.
"""
from pathlib import Path

import pytest
import yaml

from factory.lords.content_live import normalize_title

REPO = Path(__file__).resolve().parents[2]
CONTRACT = REPO / "knowledge" / "cdnvideohub" / "content-api.yaml"


@pytest.fixture
def договор():
    """Контракт собирается штатным загрузчиком, а не пересобирается в тесте."""
    from factory.lords import content_live

    return content_live.load_live_contract()


def запись(**over):
    d = {"id": "test-1", "name": "Проверочный тайтл", "type": "movie",
         "year": 2026, "external_ids": {}}
    d.update(over)
    return d


def test_только_imdb_не_даёт_дескриптора(договор):
    """Ровно случай двух названных адресов: у записи только IMDb.

    Дескриптора нет намеренно. Построить его значило бы нарушить PC-2, и
    сборщик элемента плеера всё равно отверг бы такой дескриптор — карточка
    получила бы видимость исправности вместо честной заглушки.
    """
    t = normalize_title(запись(external_ids={"imdb": "43670638"}), договор)
    assert t is not None
    assert t.get("playback") is None


def test_kinopoisk_остаётся_главнее_imdb(договор):
    """Порядок важен: у кого есть kp, поведение меняться не должно."""
    t = normalize_title(запись(external_ids={"imdb": "33256086", "kinopoisk": "13653289"}), договор)
    assert t["playback"]["aggregator"] == "kp"
    assert t["playback"]["title_id"] == "13653289"


@pytest.mark.parametrize("ключ,код,идентификатор", [
    ("kinopoisk", "kp", "13653289"),
    ("myanimelist", "mali", "52991"),
    ("mydramalist", "mdl", "700123"),
])
def test_каждый_объявленный_агрегатор_даёт_дескриптор(договор, ключ, код, идентификатор):
    t = normalize_title(запись(external_ids={ключ: идентификатор}), договор)
    assert t["playback"] == {"aggregator": код, "title_id": идентификатор}


def test_без_единого_идентификатора_дескриптора_нет(договор):
    """Выдумывать идентификатор нельзя: честное отсутствие лучше подмены."""
    t = normalize_title(запись(external_ids={}), договор)
    assert t["playback"] is None


def test_неизвестный_агрегатор_не_попадает_в_дескриптор(договор):
    """Поставщик отвечает 503 на неизвестный агрегатор — такое слать нельзя."""
    t = normalize_title(запись(external_ids={"tvdb": "12345"}), договор)
    assert t["playback"] is None


def test_контракт_не_объявляет_imdb():
    """Перечень ведётся в контракте, и IMDb в нём быть не должно.

    Проверка стоит здесь, а не только в согласованности контрактов: добавление
    imdb сюда выглядит безобидным расширением, а на деле нарушает PC-2.
    """
    raw = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    приоритет = raw["mapping"]["title"]["playback_aggregator_priority"]
    assert "imdb" not in приоритет, (
        "imdb в приоритете источника нарушает PC-2 контракта плеера")


def test_поставщик_принимает_imdb_но_это_не_разрешение():
    """Свидетельство измерения, сохранённое как знание.

    Прямой запрос плейлиста возвращал поток по aggr=imdb для обоих названных
    адресов, и названия совпадали. Запрет остаётся запретом: причина PC-2
    неизвестна этой итерации и может быть лицензионной.
    """
    from factory.lords.player import ALLOWED_AGGREGATORS

    assert "imdb" not in ALLOWED_AGGREGATORS
