"""Издатель витрины берётся из её репозитория, а не из общего направления.

Зачем проверка
--------------

Направление Secret Hub хранит ОДНО значение `publisher_id` на всё направление:
`lords` отдавал один номер трём витринам (lords-01/02/03), `yami` — одному
файлу, который читают animedia.icu, animedia.space, zonafilm.space и три
арендатора индексируемого Yummy. Пока PLAYER_CONFIGURE спрашивал только
направление, «назначить lordfilm47.space 10373, а lordserial33.biz 10378» было
невыполнимо в принципе: правка направления меняла и 1lordserials1.online,
которое менять запрещено.

Дефект, который проверка не даёт вернуть, тише: сама замена проходит, а
ПОВТОРНЫЙ запуск PLAYER_CONFIGURE — после пересборки, перезапуска или просто
при очередном обслуживании — снова берёт значение направления и молча
возвращает витрине прежний номер. Снаружи это выглядит как «изменение не
удержалось», и искать причину пришлось бы в выкладке, а не здесь.

Чего проверка НЕ делает
-----------------------

Она не подтверждает, что номер работает у провайдера: снаружи это не измеряется
(D137). Она проверяет только порядок источников.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "host" / "nova-player-configure.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("nova_player_configure", СЦЕНАРИЙ)
    модуль = importlib.util.module_from_spec(спец)
    # Регистрация ДО исполнения: `@dataclass` внутри модуля ищет своё
    # пространство имён через `sys.modules[cls.__module__]`, и без записи
    # падает с AttributeError ещё на разборе файла.
    sys.modules[спец.name] = модуль
    спец.loader.exec_module(модуль)
    return модуль


@pytest.fixture()
def стенд(tmp_path: Path, monkeypatch):
    """Свой корень пакета: реестр и репозиторий витрины — поддельные."""
    м = _модуль()
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "site-cells.json").write_text(json.dumps({
        "cells": [
            {"site_id": "alpha", "domain": "alpha.test",
             "repo": {"path": "var/site-repos/alpha"}},
            {"site_id": "beta", "domain": "beta.test",
             "repo": {"path": "var/site-repos/beta"}},
            {"site_id": "gamma", "domain": "gamma.test"},
        ]}, ensure_ascii=False), encoding="utf-8")
    for имя, объявление in (("alpha", "10373"), ("beta", None)):
        каталог = tmp_path / "var" / "site-repos" / имя / "config"
        каталог.mkdir(parents=True)
        данные = {"site_id": имя, "domain": f"{имя}.test"}
        if объявление is not None:
            данные["publisher_id_expected"] = объявление
        (каталог / "site.json").write_text(json.dumps(данные, ensure_ascii=False),
                                          encoding="utf-8")
    секрет = tmp_path / "secret-publisher-id"
    секрет.write_text("10238\n", encoding="utf-8")
    monkeypatch.setattr(м, "КОРЕНЬ_ПАКЕТА", tmp_path)
    monkeypatch.setattr(м, "РЕЕСТР_ЯЧЕЕК", tmp_path / "config" / "site-cells.json")
    monkeypatch.setattr(м, "КОРЕНЬ_РЕПОЗИТОРИЕВ", tmp_path)
    monkeypatch.setattr(м, "ПРОФИЛИ", {"lords": str(секрет)})
    return м


def _цель(м, site_id: str):
    return м.Цель(site_id, f"{site_id}.test", f"{site_id}.service", "lords", site_id)


def test_объявление_витрины_важнее_направления(стенд):
    """Витрина объявила свой номер — направление не спрашивается вовсе."""
    assert стенд.издатель(_цель(стенд, "alpha")) == "10373"


def test_без_объявления_работает_прежний_путь(стенд):
    """Витрина без объявления получает значение направления, как раньше."""
    assert стенд.издатель(_цель(стенд, "beta")) == "10238"


def test_витрина_вне_реестра_получает_направление(стенд):
    """Записи нет — не отказ: прежнее поведение сохраняется."""
    assert стенд.издатель(_цель(стенд, "unknown")) == "10238"


def test_ячейка_без_репозитория_получает_направление(стенд):
    assert стенд.издатель(_цель(стенд, "gamma")) == "10238"


def test_непригодное_объявление_останавливает_операцию(стенд, tmp_path):
    """Нечисловое значение — отказ, а не тихий возврат к направлению.

    Плеер вызывает `Number(publisherId)`: нечисловое даёт NaN и 400 от
    провайдера. Молча взять значение направления здесь нельзя — витрина
    получила бы номер, которого ей не назначали.
    """
    файл = tmp_path / "var" / "site-repos" / "alpha" / "config" / "site.json"
    файл.write_text(json.dumps({"publisher_id_expected": "не-число"}),
                    encoding="utf-8")
    with pytest.raises(SystemExit):
        стенд.издатель(_цель(стенд, "alpha"))


def test_происхождение_называет_фактический_источник(стенд):
    """Боковой файл не должен ссылаться на Secret Hub, если значение не оттуда."""
    assert стенд.объявление_витрины("alpha") == "10373"
    assert стенд.объявление_витрины("beta") == ""
