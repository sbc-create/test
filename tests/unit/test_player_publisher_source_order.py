"""Издатель витрины берётся из учёта реестра, и запасного пути к нему нет.

Зачем проверка
--------------

Файл направления Secret Hub хранит ОДНО значение `publisher_id` на всё
направление: `lords` отдавал один номер трём витринам (lords-01/02/03),
`yami` — один файл, который читают animedia.icu, animedia.space,
zonafilm.space и арендаторы индексируемого Yummy. Пока PLAYER_CONFIGURE
спрашивала направление, «назначить lordfilm47.space 10373, а
lordserial33.biz 10378» было невыполнимо в принципе: правка направления меняла
и 1lordserials1.online, которое менять запрещено.

Дефект, который проверка не даёт вернуть, тише самой замены. Прежняя редакция
читала объявление витрины и возвращала пустое значение на КАЖДОЙ неудаче —
нечитаемый реестр, отсутствующая запись, пустой `repo.path`, битый
`site.json`, — после чего брала значение направления. То есть повторный запуск
операции (после пересборки, перезапуска или просто при очередном
обслуживании) молча возвращал витрине ПРЕЖНИЙ номер. Снаружи это выглядит как
«изменение не удержалось», и причину искали бы в выкладке, а не здесь.

Правило теперь одно: номер назначает владелец, назначение хранит учёт реестра
(`publisher.publisher_id`, D177), объявление пакета обязано с ним совпадать, а
любая неудача чтения — отказ с названной причиной. Файл направления для выбора
номера не читается вовсе.

Чего проверка НЕ делает
-----------------------

Она не подтверждает, что номер работает у провайдера: это измеряется действием
на живой витрине (`automation/local/publisher-id-check.py`), а не здесь.
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


def _реестр(tmp_path: Path, ячейки: list[dict]) -> Path:
    файл = tmp_path / "config" / "site-cells.json"
    файл.parent.mkdir(exist_ok=True)
    файл.write_text(json.dumps({"cells": ячейки}, ensure_ascii=False), encoding="utf-8")
    return файл


def _пакет(tmp_path: Path, имя: str, объявление: str | None) -> Path:
    каталог = tmp_path / "var" / "site-repos" / имя / "config"
    каталог.mkdir(parents=True, exist_ok=True)
    данные = {"site_id": имя, "domain": f"{имя}.test"}
    if объявление is not None:
        данные["publisher_id_expected"] = объявление
    файл = каталог / "site.json"
    файл.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")
    return файл


@pytest.fixture()
def стенд(tmp_path: Path, monkeypatch):
    """Свой корень пакета: реестр и репозитории витрин — поддельные.

    Состав стенда повторяет найденные в жизни случаи: согласованная витрина,
    витрина без объявления, витрина без `repo.path`, витрина с расхождением,
    витрина без номера в учёте и витрина, которой в реестре нет вовсе.
    """
    м = _модуль()
    _реестр(tmp_path, [
        {"site_id": "alpha", "domain": "alpha.test",
         "repo": {"path": "var/site-repos/alpha"}, "publisher": {"publisher_id": "10373"}},
        {"site_id": "beta", "domain": "beta.test",
         "repo": {"path": "var/site-repos/beta"}, "publisher": {"publisher_id": "10378"}},
        {"site_id": "gamma", "domain": "gamma.test",
         "publisher": {"publisher_id": "10331"}},
        {"site_id": "delta", "domain": "delta.test",
         "repo": {"path": "var/site-repos/delta"}, "publisher": {"publisher_id": "10333"}},
        {"site_id": "epsilon", "domain": "epsilon.test",
         "repo": {"path": "var/site-repos/epsilon"}, "publisher": {}},
    ])
    _пакет(tmp_path, "alpha", "10373")      # согласована
    _пакет(tmp_path, "beta", None)          # объявления нет
    _пакет(tmp_path, "delta", "10252")      # расхождение с учётом
    _пакет(tmp_path, "epsilon", "10252")    # в учёте номера нет
    monkeypatch.setattr(м, "КОРЕНЬ_ПАКЕТА", tmp_path)
    monkeypatch.setattr(м, "РЕЕСТР_ЯЧЕЕК", tmp_path / "config" / "site-cells.json")
    monkeypatch.setattr(м, "КОРЕНЬ_РЕПОЗИТОРИЕВ", tmp_path)
    return м


def _цель(м, site_id: str):
    return м.Цель(site_id, f"{site_id}.test", f"{site_id}.service", "yami")


def test_номер_берётся_из_учёта_реестра(стенд):
    """Учёт и объявление согласны — операция получает назначенный номер."""
    assert стенд.издатель(_цель(стенд, "alpha")) == "10373"


def test_направление_не_читается_для_выбора_номера(стенд):
    """Таблицы файлов направления в модуле нет: запасного источника не существует."""
    assert not hasattr(стенд, "ПРОФИЛИ")


def test_нечитаемый_реестр_отказ_а_не_направление(стенд, tmp_path):
    """Главный найденный путь откату: реестра нет — прежний код брал направление."""
    (tmp_path / "config" / "site-cells.json").unlink()
    with pytest.raises(SystemExit) as ош:
        стенд.издатель(_цель(стенд, "alpha"))
    assert "не читается" in str(ош.value)


def test_витрина_вне_реестра_отказ(стенд):
    """Записи нет — назначенный номер неизвестен, подставлять его нельзя."""
    with pytest.raises(SystemExit) as ош:
        стенд.издатель(_цель(стенд, "unknown"))
    assert "BLOCKED_INPUT" in str(ош.value)


def test_ячейка_без_репозитория_отказ(стенд):
    """Без `repo.path` объявление не сверить, а без сверки выкладка вернёт своё."""
    with pytest.raises(SystemExit) as ош:
        стенд.издатель(_цель(стенд, "gamma"))
    assert "repo.path" in str(ош.value)


def test_битый_пакет_отказ_а_не_направление(стенд, tmp_path):
    """Нечитаемый `site.json` — ровно тот случай тихого возврата номера."""
    (tmp_path / "var" / "site-repos" / "alpha" / "config" / "site.json").write_text(
        "{не json", encoding="utf-8")
    with pytest.raises(SystemExit) as ош:
        стенд.издатель(_цель(стенд, "alpha"))
    assert "не читается" in str(ош.value)


def test_пакет_без_объявления_отказ(стенд):
    """Учёт назначает, пакет молчит: следующая выкладка отдала бы другое значение."""
    with pytest.raises(SystemExit) as ош:
        стенд.издатель(_цель(стенд, "beta"))
    assert "publisher_id_expected" in str(ош.value)


def test_расхождение_учёта_и_пакета_отказ(стенд):
    """Какое из двух значений верно — решает владелец, а не операция."""
    with pytest.raises(SystemExit) as ош:
        стенд.издатель(_цель(стенд, "delta"))
    assert "расходятся" in str(ош.value)


def test_учёт_без_номера_отказ(стенд):
    """Пустое поле — BLOCKED_INPUT, а не разрешение взять значение направления."""
    with pytest.raises(SystemExit) as ош:
        стенд.издатель(_цель(стенд, "epsilon"))
    assert "BLOCKED_INPUT" in str(ош.value)


def test_непригодный_номер_останавливает_операцию(стенд, tmp_path):
    """Плеер вызывает `Number(publisherId)`: нечисловое даёт NaN и 400 у провайдера."""
    _реестр(tmp_path, [
        {"site_id": "alpha", "domain": "alpha.test",
         "repo": {"path": "var/site-repos/alpha"},
         "publisher": {"publisher_id": "не-число"}}])
    with pytest.raises(SystemExit) as ош:
        стенд.издатель(_цель(стенд, "alpha"))
    assert "непригоден" in str(ош.value)


def test_происхождение_называет_учёт_а_не_secret_hub(стенд):
    """Боковой файл не должен ссылаться на Secret Hub: значение не оттуда."""
    источник = стенд.записать.__doc__ or ""
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert "Secret Hub" not in текст, источник
    assert "site-cells.json#publisher.publisher_id" in текст


def test_все_шесть_целей_разрешаются_на_живом_реестре():
    """Настоящий реестр фабрики: ни одна из шести целей не упирается в отказ.

    Проверка смотрит на реальные файлы, потому что новое правило строже
    прежнего: отказ вместо запасного пути обязан быть ДОСТИЖИМЫМ только при
    настоящем расхождении, а не при штатном состоянии репозитория.
    """
    м = _модуль()
    for site_id, цель in м.ЦЕЛИ.items():
        assert м.издатель(цель).isdigit(), site_id


def test_режим_источника_берётся_из_профиля_пакета():
    """У всех шести целей в профиле стоит `provider-id` — так и должно читаться.

    Режим решает, по какому ключу рендерер спрашивает провайдера. Молчаливая
    подмена на `external-ids` уронила бы покрытие просмотра, а искать причину
    стали бы в данных каталога.
    """
    м = _модуль()
    for site_id, цель in м.ЦЕЛИ.items():
        assert м.режим_источника(цель) == "provider-id", site_id


def test_нечитаемый_профиль_останавливает_операцию(tmp_path: Path, monkeypatch):
    """Профиля нет — отказ, а не режим по умолчанию.

    Прежняя редакция читала профиль по жёстко вписанному пути
    `/srv/site-factory/repo/config/site-profiles`, где лежит отдельная, более
    старая копия пакета, и при любой неудаче возвращала `external-ids`.
    """
    м = _модуль()
    monkeypatch.setattr(м, "КОРЕНЬ_ПАКЕТА", tmp_path)
    with pytest.raises(SystemExit) as ош:
        м.режим_источника(м.ЦЕЛИ["zona-01"])
    assert "не читается" in str(ош.value)


def test_профиль_без_режима_останавливает_операцию(tmp_path: Path, monkeypatch):
    """Пустое поле — не разрешение выбрать режим самостоятельно."""
    м = _модуль()
    каталог = tmp_path / "config" / "site-profiles"
    каталог.mkdir(parents=True)
    (каталог / "zona-01.json").write_text(json.dumps(
        {"site_id": "zona-01", "player": {}}), encoding="utf-8")
    monkeypatch.setattr(м, "КОРЕНЬ_ПАКЕТА", tmp_path)
    with pytest.raises(SystemExit) as ош:
        м.режим_источника(м.ЦЕЛИ["zona-01"])
    assert "source_mode" in str(ош.value)
