"""Данные ячеек обязаны попадать в бэкап, и план сбора обязан быть выводимым.

Повод. Измерено 2026-10-13: суточный архив хоста собирал `/srv/sites/`,
`/etc/site-factory/`, `/etc/nginx/sites-available/`, `var/` фабрики и хранилище
Secret Hub. Каталоги данных ячеек живут в `/srv/<учётная запись>/data` — другой
путь, — и в архив не попадала ни одна из 28 ячеек. Снаружи это неотличимо от
«всё собрано»: бэкап завершался успехом.

Что здесь закрепляется:

1. план строится по КОНТРАКТУ ДАННЫХ витрины, а не по списку имён в коде, —
   иначе следующая ячейка снова окажется без копии;
2. невосстановимое берётся, поставляемое — нет: снимок каталога весит в сотню
   раз больше и возвращается производителем;
3. витрина без объявленного контракта не пропускается молча;
4. элемент контракта, уводящий за пределы каталога данных, ОСТАНАВЛИВАЕТ план:
   содержимое `config/site.json` витрины — это вход, а не доверенное значение;
5. сам сценарий бэкапа действительно вызывает план и валит прогон при отказе.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.cell import registry

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "host" / "site-factory-backup.sh"


def _модуль():
    import importlib.util

    путь = КОРЕНЬ / "automation" / "host" / "backup_cell_data.py"
    spec = importlib.util.spec_from_file_location("backup_cell_data", путь)
    м = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(м)
    return м


def _ячейка(tmp_path, site_id="lords-10", *, контракт=None, data_dir=None,
            domain=None):
    """Реестр из одной ячейки плюс её репозиторий с контрактом данных."""
    репо = tmp_path / "repo" / site_id
    (репо / "config").mkdir(parents=True)
    конфиг = {"site_id": site_id, "domain": domain or f"{site_id}.example"}
    if контракт is not None:
        конфиг["data_contract"] = {"user_writable": контракт,
                                   "delivered": [f"{site_id}-catalog.json"]}
    (репо / "config" / "site.json").write_text(
        json.dumps(конфиг, ensure_ascii=False), encoding="utf-8")
    запись = {
        "site_id": site_id, "domain": конфиг["domain"], "aliases": [],
        "status": "live", "repo": {"kind": "local", "path": str(репо)},
        "template": {"template_id": "lords-films"}, "pins": {},
        "deploy_target": {}, "publisher": {}, "data": {}, "deployed": {},
        "content_revision": None, "last_update": None, "backup": {},
        "resources": {}, "release": {},
        "runtime": {"port": 9125, "unit": f"nova-{site_id}.service",
                    **({"data_dir": data_dir} if data_dir is not None else {})},
    }
    реестр = tmp_path / "site-cells.json"
    реестр.write_text(json.dumps({"schema_version": registry.SCHEMA_VERSION,
                                  "cells": [запись]}, ensure_ascii=False),
                      encoding="utf-8")
    return реестр


def _запись(site_id, domain, *, контракт=None, data_dir=None, status="live"):
    """Одна запись реестра без записи на диск — для проверок полноты."""
    з = {
        "site_id": site_id, "domain": domain, "aliases": [], "status": status,
        "repo": {"kind": "local", "path": f"var/site-repos/{site_id}"},
        "template": {"template_id": "lords-films"}, "pins": {},
        "deploy_target": {}, "publisher": {}, "data": {}, "deployed": {},
        "content_revision": None, "last_update": None, "backup": {},
        "resources": {}, "release": {},
        "runtime": {"port": 9125, "unit": f"nova-{site_id}.service",
                    **({"data_dir": data_dir} if data_dir else {})},
    }
    return з


def _реестр_из(tmp_path, *записи):
    """Реестр из готовых записей — для проверок полноты."""
    путь = tmp_path / "site-cells.json"
    путь.write_text(json.dumps({"schema_version": registry.SCHEMA_VERSION,
                                "cells": list(записи)}, ensure_ascii=False),
                    encoding="utf-8")
    return путь


def test_план_берёт_объявленное_контрактом(tmp_path):
    реестр = _ячейка(tmp_path, контракт=["site-data", "{site}-community.json",
                                         "editorial-overrides.json"],
                     data_dir="/srv/lordfilm-group/data")
    строки = _модуль().план(реестр, шум=open("/dev/null", "w"))
    элементы = [э for _, _, э in строки]
    assert элементы == ["site-data", "lords-10-community.json",
                        "editorial-overrides.json"]
    assert all(к == "/srv/lordfilm-group/data" for _, к, _ in строки)


def test_поставляемое_в_план_не_попадает(tmp_path):
    """Снимок каталога восстановит производитель; в архиве он лишний.

    Измерено: данные ячеек 1,81 ГиБ, невосстановимая часть 25,74 МиБ (1,39 %).
    """
    реестр = _ячейка(tmp_path, контракт=["site-data", "editorial-overrides.json"],
                     data_dir="/srv/lordfilm-group/data")
    элементы = [э for _, _, э in _модуль().план(реестр, шум=open("/dev/null", "w"))]
    assert not [э for э in элементы if "catalog" in э or "details" in э]


def test_витрина_без_контракта_не_пропускается_молча(tmp_path, capsys):
    реестр = _ячейка(tmp_path, контракт=None, data_dir="/srv/lordfilm-group/data")
    м = _модуль()
    строки = м.план(реестр)
    assert строки == [("lords-10", "/srv/lordfilm-group/data", "*")]
    assert "УНКОНТРАКТ" in capsys.readouterr().err


def test_нет_каталога_данных_это_названная_причина(tmp_path, capsys):
    реестр = _ячейка(tmp_path, контракт=["site-data"], data_dir=None)
    assert _модуль().план(реестр) == []
    assert "ПРОПУСК" in capsys.readouterr().err


@pytest.mark.parametrize("элемент", [
    "../../etc/shadow", "/etc/shadow", "site-data/../../..", "~/secret",
])
def test_элемент_за_пределами_каталога_останавливает_план(tmp_path, элемент):
    """`config/site.json` витрины — вход, а не доверенное значение.

    Без этой проверки правка в репозитории витрины забирала бы в архив любой
    файл, доступный root, — и архив потом распаковывают.
    """
    м = _модуль()
    реестр = _ячейка(tmp_path, контракт=["site-data", элемент],
                     data_dir="/srv/lordfilm-group/data")
    with pytest.raises(м.ПланОтвергнут, match="уводит за пределы"):
        м.план(реестр, шум=open("/dev/null", "w"))


def test_сценарий_бэкапа_действительно_зовёт_план_и_валится_при_отказе():
    """Иначе проверка выше охраняла бы код, который никто не вызывает."""
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    # Ищется именно ВЫЗОВ, а не первое упоминание: первая версия проверки
    # резала текст по первому вхождению имени файла, и когда рядом появился
    # пояснительный комментарий, окно съехало в него — проверка стала судить о
    # комментарии вместо кода.
    строки = [с for с in текст.splitlines()
              if "backup_cell_data.py" in с and not с.lstrip().startswith("#")]
    assert строки, "сценарий не ВЫЗЫВАЕТ построение плана сбора данных ячеек"
    начало = текст.index(строки[0])
    # Отказ плана обязан останавливать прогон, а не печатать предупреждение.
    assert "fail" in текст[начало:начало + 600], "отказ плана не останавливает бэкап"
    assert "srv-cells/" in текст, "данные ячеек некуда складывать в архиве"


def test_запись_о_проверке_называет_покрытие_ячеек():
    """Иначе «данные ячеек в копии» пришлось бы принимать на слово.

    Архив и запись о проверке лежат под root (`0600` и `0640 root:root`), и
    заглянуть внутрь снаружи нечем. Число витрин и элементов в записи — это
    единственный проверяемый ответ, и ноль в нём отличим от «поле не пишется».
    """
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert '"cell_data"' in текст, "запись о проверке не называет покрытие ячеек"
    for имя in ("CELL_SITES", "CELL_ITEMS", "CELL_KB"):
        assert имя in текст, f"{имя} не считается и в запись не попадёт"
    # Значения обязаны доехать до python-блока записи, а не остаться в echo.
    блок = текст.split('python3 - "$RECORD"', 1)[1][:400]
    assert "$CELL_SITES" in блок and "$CELL_ITEMS" in блок, (
        "сводка по ячейкам не передана в запись о проверке")


def test_действующий_реестр_даёт_непустой_план():
    """На реальном реестре план обязан покрывать ячейки, а не оказаться пустым.

    Путь передаётся явно: по умолчанию план читает КОРНЕВУЮ копию реестра
    (`/usr/local/lib/site-factory-cell/config/site-cells.json`, 0600 root) —
    ту, из которой привилегированный исполнитель берёт размещение витрин.
    Под обычной учётной записью она не читается, и это правильно.
    """
    реестр = КОРЕНЬ / "config" / "site-cells.json"
    строки = _модуль().план(реестр, шум=open("/dev/null", "w"))
    витрины = {с for с, _, _ in строки}
    assert len(витрины) >= 20, f"в плане всего {len(витрины)} витрин"
    партия = {f"lords-{n}" for n in range(10, 18)}
    assert партия <= витрины, f"партия не покрыта: {sorted(партия - витрины)}"


def test_нечитаемый_реестр_это_отказ_а_не_пустой_план():
    """Пустой план опаснее исключения: бэкап прошёл бы успешно и без данных.

    Ровно это и было до 2026-10-13 — архив собирался без единой ячейки и
    считался подтверждённым. Поэтому нечитаемый или пустой реестр обязан
    останавливать прогон, а не вырождаться в «собирать нечего».
    """
    м = _модуль()
    with pytest.raises(м.ПланОтвергнут, match="не прочитан"):
        м.план(Path("/nonexistent/site-cells.json"), шум=open("/dev/null", "w"))


def test_пустой_реестр_это_отказ(tmp_path):
    м = _модуль()
    пустой = tmp_path / "site-cells.json"
    пустой.write_text('{"schema_version": "1.0", "cells": []}', encoding="utf-8")
    with pytest.raises(м.ПланОтвергнут, match="ни одной ячейки"):
        м.план(пустой, шум=open("/dev/null", "w"))


def test_по_умолчанию_берётся_корневая_копия_реестра():
    """Иначе бэкап читал бы рабочую копию, а исполнитель — корневую.

    Измерено 2026-10-13: в `/srv/site-factory/repo`, откуда юнит запускает
    сценарий, нет ни `config/site-cells.json`, ни `factory/cell` — это более
    старый checkout. Реестр хоста лежит у привилегированного исполнителя.
    """
    м = _модуль()
    assert str(м.РЕЕСТР_ХОСТА) == "/usr/local/lib/site-factory-cell/config/site-cells.json"
    if м.РЕЕСТР_ХОСТА.is_file():
        assert м.выбрать_реестр() == м.РЕЕСТР_ХОСТА
    явный = Path("/tmp/какой-то-реестр.json")
    assert м.выбрать_реестр(явный) == явный, "явный путь обязан быть сильнее"


# --- обязательный состав, а не порог количества ----------------------------

def test_полнота_ловит_публичную_ячейку_без_каталога_данных(tmp_path):
    """Порог «витрин не меньше N» этого не видит, а копии у витрины не будет.

    Ровно это и случилось 13.10: в плане не было animedia-01 — действующей
    витрины animedia.icu, — потому что в её паспорте отсутствовал
    `runtime.data_dir`. Счётчик витрин оставался зелёным.
    """
    м = _модуль()
    путь = _реестр_из(tmp_path, _запись("animedia-01", "animedia.icu"))
    покрытые, незапущенные, пробелы = м.полнота(путь)
    assert покрытые == [] and незапущенные == []
    assert any("нет runtime.data_dir" in п for п in пробелы), пробелы


def test_полнота_не_требует_каталога_у_непубличных(tmp_path):
    """Пилот и локальные стенды наружу не смотрят: копии им не нужны."""
    м = _модуль()
    путь = _реестр_из(tmp_path, _запись("pilot-local", "pilot.localhost.test"))
    assert м.полнота(путь) == ([], [], [])


def test_полнота_на_действующем_реестре_без_пробелов():
    """Без порога количества: сверяется СОСТАВ, витрина за витриной.

    Прежняя редакция требовала «покрыто не меньше 25» — и это ровно тот
    порог, против которого написана сама проверка: он был зелёным, когда в
    «покрытые» попадали десять ячеек с ОБЪЯВЛЕННЫМ, но ещё не созданным
    каталогом (lords-08…17). Теперь каждая публичная ячейка обязана попасть
    РОВНО в одно состояние, и состояние обязано совпадать с диском.
    """
    import json as _json

    м = _модуль()
    реестр = КОРЕНЬ / "config" / "site-cells.json"
    покрытые, незапущенные, пробелы = м.полнота(реестр)
    assert пробелы == [], "\n".join(пробелы)

    записи = _json.loads(реестр.read_text(encoding="utf-8"))["cells"]
    публичные = {з["site_id"]: з for з in записи
                 if not str(з.get("domain") or "").endswith(м.НЕПУБЛИЧНЫЕ)}
    не_названные = set(публичные) - set(покрытые) - {
        с.split(" ")[0] for с in незапущенные}
    assert not не_названные, f"публичные ячейки без состояния: {не_названные}"

    for site_id in покрытые:
        каталог = (публичные[site_id].get("runtime") or {}).get("data_dir")
        assert каталог and Path(каталог).is_dir(), \
            f"{site_id} назван покрытым, а каталога {каталог} на диске нет"
    for строка in незапущенные:
        site_id = строка.split(" ")[0]
        каталог = (публичные[site_id].get("runtime") or {}).get("data_dir")
        assert not Path(каталог).is_dir(), \
            f"{site_id} назван незапущенным, а каталог {каталог} существует"


def test_действующая_витрина_без_каталога_на_диске_это_пробел(tmp_path):
    """Самый опасный случай: паспорт в порядке, а данных нет.

    Со статусом `live` это значит, что витрина работает, а копировать нечего —
    либо каталог переехал, либо потерян. В одной куче с незапущенными такой
    случай был бы не виден.
    """
    м = _модуль()
    путь = _реестр_из(tmp_path, _запись("lords-01", "lordfilm47.space",
                                        data_dir=str(tmp_path / "нет-такого")))
    покрытые, незапущенные, пробелы = м.полнота(путь)
    assert покрытые == [] and незапущенные == []
    assert any("на диске его НЕТ" in п and "live" in п for п in пробелы), пробелы


def test_незапущенная_витрина_без_каталога_не_пробел_и_не_покрытие(tmp_path):
    """У `planned` данных ещё не существует: терять нечего, но и покрытия нет."""
    м = _модуль()
    путь = _реестр_из(tmp_path, _запись("lords-10", "lordfilm.group",
                                        status="planned",
                                        data_dir=str(tmp_path / "ещё-нет")))
    покрытые, незапущенные, пробелы = м.полнота(путь)
    assert покрытые == [], покрытые
    assert пробелы == [], пробелы
    assert len(незапущенные) == 1 and "planned" in незапущенные[0], незапущенные


def test_созданный_каталог_переводит_витрину_в_покрытые(tmp_path):
    """Состояние берётся с диска, а не из статуса: запуск — это появление данных."""
    м = _модуль()
    каталог = tmp_path / "данные"
    каталог.mkdir()
    (каталог / "lords-10-catalog.json").write_text("{}", encoding="utf-8")
    путь = _реестр_из(tmp_path, _запись("lords-10", "lordfilm.group",
                                        status="planned", data_dir=str(каталог)))
    покрытые, незапущенные, пробелы = м.полнота(путь)
    assert покрытые == ["lords-10"], (покрытые, незапущенные, пробелы)
    assert незапущенные == [] and пробелы == []
