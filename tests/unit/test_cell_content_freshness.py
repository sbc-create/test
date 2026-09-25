"""Свежесть содержимого: расхождение ревизий и НАЗВАННАЯ причина.

Трое суток четыре витрины показывали каталог от 23 сентября при источнике от
25-го, и ни одна проверка этого не называла: сайты отвечали 200, службы стояли,
`mtime` снимков был свежайшим. Свежий `mtime` при неизменной ревизии — это и
есть та неисправность: пятиминутный проход честно перезаписывал хранилище
ячейки содержимым отрисованного релиза, который не двигался с 19 сентября.

Поэтому проверка сравнивает РЕВИЗИИ в трёх точках и обязана различать причины:
не собрался снимок, не доставлен, доставлен но не перечитан, витрина не
отвечает. «Каталог устарел» — не диагноз, а четыре разные неисправности, и
лечение не той из них было главной потерей времени.

Отдельно сторожится способ чтения ревизии. Производитель пишет поля по
алфавиту, и `items` стоит между `builtAt` и `revision`: в голове файла есть
время сборки, а ревизия — за шестнадцатью мегабайтами записей. Первая версия
читала только голову и на каждой исправной витрине печатала «каталог не
собирается» — отсутствие измерения выдавалось за измеренное отсутствие.
Поэтому снимки здесь строятся большими, а не короткими.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.cell import content, runtime  # noqa: E402


def снимок(путь: Path, *, revision: str, built_at: str, записей: int = 400) -> None:
    """Файл с полями в том же порядке и того же масштаба, что у производителя."""
    данные = {
        "absent_reason": None,
        "builtAt": built_at,
        "count": записей,
        "items": [{"slug": f"z-{i}", "title": "Тайтл " * 12} for i in range(записей)],
        "revision": revision,
        "schema": 1,
        "site": "проверка",
    }
    путь.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")
    assert путь.stat().st_size > 32768, "снимок должен быть больше окна чтения"


def место(tmp_path, **поля):
    значения = {"site_id": "проверка", "domain": "example.test",
                "data_dir": str(tmp_path / "cell"), "unit": "u.service",
                "previous_unit": None, "port": 9999, "account": "acc",
                "reload": "mtime", "managed_by": "cell", "build_id": None}
    значения.update(поля)
    return runtime.Размещение(**{к: значения[к] for к in значения
                                 if к in runtime.Размещение.__dataclass_fields__})


@pytest.fixture()
def стенд(tmp_path, monkeypatch):
    общий = tmp_path / "front"
    ячейка = tmp_path / "cell"
    общий.mkdir()
    ячейка.mkdir()
    monkeypatch.setattr(runtime, "размещение",
                        lambda site_id, **k: место(tmp_path))
    monkeypatch.setattr(content.runtime, "размещение",
                        lambda site_id, **k: место(tmp_path))
    return общий, ячейка


def состояние(общий, *, опрос, предел=30.0):
    return content.состояние_витрины("проверка", общий=общий, предел_часов=предел,
                                     опрос=опрос)


def свежая_метка(часов_назад: float) -> str:
    from datetime import datetime, timedelta, timezone
    когда = datetime.now(timezone.utc) - timedelta(hours=часов_назад)
    return когда.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_всё_сошлось_это_ok(стенд):
    общий, ячейка = стенд
    снимок(общий / "проверка-catalog.json", revision="r-новая", built_at=свежая_метка(2))
    снимок(ячейка / "проверка-catalog.json", revision="r-новая", built_at=свежая_метка(2))
    итог = состояние(общий, опрос=lambda порт: {"revision": "r-новая"})
    assert итог["status"] == "ok", итог
    # Ревизия прочитана из ХВОСТА файла: голова её не содержит.
    assert итог["source"]["revision"] == "r-новая"
    assert итог["source"]["built_at"]


def test_ревизия_читается_за_пределами_головы(стенд):
    """Прямая защита от «читаем только начало файла»."""
    общий, _ = стенд
    п = общий / "проверка-catalog.json"
    снимок(п, revision="r-хвостовая", built_at=свежая_метка(1), записей=3000)
    голова = п.read_bytes()[:8192].decode("utf-8", "replace")
    assert '"revision"' not in голова, "снимок собран не как у производителя"
    assert content._края(п)["revision"] == "r-хвостовая"


def test_старый_источник_называет_производителя(стенд):
    общий, ячейка = стенд
    снимок(общий / "проверка-catalog.json", revision="r-старая", built_at=свежая_метка(91))
    снимок(ячейка / "проверка-catalog.json", revision="r-старая", built_at=свежая_метка(91))
    итог = состояние(общий, опрос=lambda порт: {"revision": "r-старая"})
    assert итог["status"] == "source-stale", итог
    assert "производитель" in итог["reason"]


def test_недоставленный_снимок_отличается_от_непрочитанного(стенд):
    общий, ячейка = стенд
    снимок(общий / "проверка-catalog.json", revision="r-новая", built_at=свежая_метка(2))
    снимок(ячейка / "проверка-catalog.json", revision="r-старая", built_at=свежая_метка(50))
    итог = состояние(общий, опрос=lambda порт: {"revision": "r-старая"})
    assert итог["status"] == "delivery-stale", итог
    assert "не доставлен" in итог["reason"]


def test_доставленный_но_не_перечитанный_снимок(стенд):
    """Та же внешняя картина, другая причина и другое лечение."""
    общий, ячейка = стенд
    снимок(общий / "проверка-catalog.json", revision="r-новая", built_at=свежая_метка(2))
    снимок(ячейка / "проверка-catalog.json", revision="r-новая", built_at=свежая_метка(2))
    итог = состояние(общий, опрос=lambda порт: {"revision": "r-старая"})
    assert итог["status"] == "runtime-stale", итог
    assert "не перечитан" in итог["reason"]


def test_молчащая_витрина_не_выдаётся_за_свежую(стенд):
    общий, ячейка = стенд
    снимок(общий / "проверка-catalog.json", revision="r-новая", built_at=свежая_метка(2))
    снимок(ячейка / "проверка-catalog.json", revision="r-новая", built_at=свежая_метка(2))
    итог = состояние(общий, опрос=lambda порт: {"error": "ConnectionRefusedError"})
    assert итог["status"] == "unreachable", итог


def test_витрина_без_своего_хранилища_но_со_свежей_ревизией_исправна(стенд):
    """Иначе тревога звучала бы на витрине с другим способом доставки.

    Ложная тревога кончается тем, что перестают смотреть и на настоящую.
    """
    общий, _ = стенд
    снимок(общий / "проверка-catalog.json", revision="r-новая", built_at=свежая_метка(2))
    итог = состояние(общий, опрос=lambda порт: {"revision": "r-новая"})
    assert итог["status"] == "ok", итог
    assert итог["note"] == "data-outside-cell"


def test_отсутствие_снимка_источника_называется_отдельно(стенд):
    общий, _ = стенд
    итог = состояние(общий, опрос=lambda порт: {"revision": ""})
    assert итог["status"] == "no-source", итог


def test_свод_перечисляет_устаревшие(стенд, monkeypatch):
    общий, ячейка = стенд
    снимок(общий / "проверка-catalog.json", revision="r-новая", built_at=свежая_метка(2))
    снимок(ячейка / "проверка-catalog.json", revision="r-старая", built_at=свежая_метка(50))
    итог = content.свежесть(общий=общий, сайты=["проверка"],
                            опрос=lambda порт: {"revision": "r-старая"})
    assert итог["ok"] is False
    assert итог["stale"] == ["проверка"]
