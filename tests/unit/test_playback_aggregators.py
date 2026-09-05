"""REQ-PLAYBACK: дескриптор строится по любому поддерживаемому агрегатору.

Дефект, который эти проверки воспроизводят: источник отдаёт запись только с
идентификатором IMDb, поставщик по нему возвращает поток, а мы дескриптор не
строим — карточка показывает «видео временно недоступно», хотя видео есть.

Измерено на боевом каталоге: 637 карточек из 53 203 попадали в этот класс.
Два названных владельцем адреса — из их числа.
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


def test_только_imdb_даёт_дескриптор(договор):
    """Ровно случай двух названных адресов: у записи только IMDb."""
    t = normalize_title(запись(external_ids={"imdb": "43670638"}), договор)
    assert t is not None
    pb = t.get("playback")
    assert pb, "дескриптор не построен, хотя IMDb есть и поставщик по нему отдаёт поток"
    assert pb["aggregator"] == "imdb"
    assert pb["title_id"] == "43670638"


def test_kinopoisk_остаётся_главнее_imdb(договор):
    """Порядок важен: у кого есть kp, поведение меняться не должно."""
    t = normalize_title(запись(external_ids={"imdb": "33256086", "kinopoisk": "13653289"}), договор)
    assert t["playback"]["aggregator"] == "kp"
    assert t["playback"]["title_id"] == "13653289"


@pytest.mark.parametrize("ключ,код,идентификатор", [
    ("kinopoisk", "kp", "13653289"),
    ("myanimelist", "mali", "52991"),
    ("mydramalist", "mdl", "700123"),
    ("imdb", "imdb", "40488636"),
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


def test_контракт_объявляет_imdb_в_приоритете():
    """Перечень агрегаторов ведётся в контракте, а не в коде."""
    raw = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    приоритет = raw["mapping"]["title"]["playback_aggregator_priority"]
    assert "imdb" in приоритет, "imdb не объявлен как агрегатор"
    assert приоритет.index("imdb") == len(приоритет) - 1, (
        "imdb обязан быть последним: у записей с kp поведение меняться не должно")
