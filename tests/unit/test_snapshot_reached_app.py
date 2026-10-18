"""REQ-CELL-SNAPSHOT-REACHED: «файл доставлен» и «витрина его загрузила» — разное.

Между этими двумя утверждениями помещается дефект, который не виден ничем
другим. Опись ячеек объявляет режим перезагрузки: при `restart` установка
каталога перезапускает юнит, при `mtime` — не перезапускает, рассчитывая, что
рантайм перечитает сам. Измерено 2026-10-18: `mtime` объявлен у тринадцати
ячеек из двадцати одной, а ядро по mtime НЕ перечитывает — перечитывание
существует только наложением отдельного сайта.

Инструмент сравнивает загруженную ревизию с ревизией файла и ОБЪЯСНЯЕТ
совпадение: если процесс старше файла — перечитывание работает; если младше —
совпадение объясняется перезапуском и ничего не доказывает. Это различение и
проверяется здесь: без него инструмент успокаивал бы там, где измерения нет.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

ПУТЬ = (Path(__file__).resolve().parents[2] / "automation" / "local"
        / "snapshot-reached-app.py")


def _модуль():
    спец = importlib.util.spec_from_file_location("snapshot_reached_app", ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


МОД = _модуль()


def _файл(tmp_path: Path, тело: str, имя: str = "catalog.json") -> Path:
    ф = tmp_path / имя
    ф.write_text(тело, encoding="utf-8")
    return ф


def test_ревизия_в_начале_файла(tmp_path):
    ф = _файл(tmp_path, '{"revision":"abc123","items":[]}')
    рев, когда = МОД.ревизия_файла(str(ф))
    assert рев == "abc123"
    assert когда.endswith("Z")


def test_ревизия_в_конце_файла(tmp_path):
    """Порядок ключей у разных издателей разный — это измеренный случай."""
    ф = _файл(tmp_path, '{"items":[' + ",".join(['{"slug":"x"}'] * 500)
              + '],"revision":"zzz999"}')
    рев, _ = МОД.ревизия_файла(str(ф))
    assert рев == "zzz999"


def test_ревизия_в_середине_большого_файла(tmp_path):
    """Края не помогли — читается целиком; иначе инструмент соврал бы
    «в файле нет revision» на исправном снимке."""
    хвост = ",".join(['{"slug":"y"}'] * 2000)
    ф = _файл(tmp_path, '{"items":[' + хвост + '],"mid":{"revision":"midrev"},'
              '"tail":[' + хвост + "]}")
    рев, _ = МОД.ревизия_файла(str(ф))
    assert рев == "midrev"


def test_нет_файла_это_не_пустая_ревизия(tmp_path):
    рев, причина = МОД.ревизия_файла(str(tmp_path / "нет-такого.json"))
    assert рев == ""
    assert причина == "файла нет"


def test_путь_не_назван(tmp_path):
    рев, причина = МОД.ревизия_файла("")
    assert рев == "" and причина == "путь не назван"


def test_файл_без_ревизии_называется_честно(tmp_path):
    ф = _файл(tmp_path, '{"items":[]}')
    рев, причина = МОД.ревизия_файла(str(ф))
    assert рев == "" and причина == "в файле нет revision"


def test_время_разбирается_в_обеих_формах():
    assert МОД.разобрать_время("2026-10-18T04:05:40Z") is not None
    assert МОД.разобрать_время("2026-10-18T04:05:40+00:00") is not None
    assert МОД.разобрать_время("не время") is None
    assert МОД.разобрать_время("") is None


def test_ячейка_без_обоих_путей_не_считается_исправной(tmp_path, monkeypatch):
    """Главное различение инструмента: спросить нечем — значит НЕ ИЗМЕРЕНО.

    Отсутствие способа спросить — пробел наблюдаемости (MOD-80), и записывать
    такую ячейку исправной нельзя: именно это и скрывало бы недоехавший снимок.
    """
    monkeypatch.setattr(МОД, "порт_ячейки", lambda имя: "9999")
    monkeypatch.setattr(МОД, "ответ_healthz", lambda порт, таймаут: {"ok": True})
    monkeypatch.setattr(МОД, "заголовки_ответа", lambda порт, таймаут: {})
    итог = МОД.проверить("ячейка-без-полей", 1)
    assert "НЕ ИЗМЕРЕНО" in итог["вывод"]
    assert "ok" in итог["вывод"], "в выводе должно быть сказано, какие поля есть"


def test_ревизия_берётся_из_заголовка_когда_healthz_молчит(tmp_path, monkeypatch):
    """Второй путь измерения, и он не из симметрии.

    Рантайм Zona отдаёт `X-Catalog-Revision` на каждый ответ — измерено линией
    Zona 2026-10-18 и проверено отсюда независимо: у zona-01/02/03 заголовок
    совпал с файлом. С ОДНИМ путём инструмент называл неизмеримыми пять ячеек,
    а неизмеримых две. Такой вывод хуже пробела: он указывает на риск,
    которого нет.
    """
    ф = _файл(tmp_path, '{"revision":"из-файла","items":[]}')
    monkeypatch.setattr(МОД, "порт_ячейки", lambda имя: "9999")
    monkeypatch.setattr(МОД, "ответ_healthz", lambda порт, таймаут: {"ok": True})
    monkeypatch.setattr(МОД, "заголовки_ответа", lambda порт, таймаут: {
        "x-catalog-revision": "из-файла", "x-catalog-built-at": "2026-10-18"})
    monkeypatch.setattr(МОД, "путь_по_данным", lambda имя: str(ф))
    итог = МОД.проверить("zona-01", 1)
    assert итог["вывод"] == "снимок у приложения"
    assert "заголовок ответа" in итог["объяснение"], (
        "откуда взята загруженная ревизия, обязано быть видно в выводе")


def test_заголовок_тоже_ловит_расхождение(tmp_path, monkeypatch):
    """Отрицательный контроль: второй путь измеряет, а не успокаивает."""
    ф = _файл(tmp_path, '{"revision":"на-диске-новее","items":[]}')
    monkeypatch.setattr(МОД, "порт_ячейки", lambda имя: "9999")
    monkeypatch.setattr(МОД, "ответ_healthz", lambda порт, таймаут: {})
    monkeypatch.setattr(МОД, "заголовки_ответа", lambda порт, таймаут: {
        "x-catalog-revision": "загружено-старое"})
    monkeypatch.setattr(МОД, "путь_по_данным", lambda имя: str(ф))
    итог = МОД.проверить("zona-01", 1)
    assert итог["вывод"].startswith("РАСХОЖДЕНИЕ")


def test_healthz_имеет_приоритет_над_заголовком(tmp_path, monkeypatch):
    """`/healthz` называет и путь, и время запуска — заголовок только ревизию.

    Поэтому подробный ответ предпочитается: иначе ячейка, у которой есть оба
    пути, потеряла бы графу «почему так» и совпадение перестало бы
    различаться от перезапуска.
    """
    ф = _файл(tmp_path, '{"revision":"rev-h","items":[]}')
    monkeypatch.setattr(МОД, "порт_ячейки", lambda имя: "9999")
    monkeypatch.setattr(МОД, "ответ_healthz", lambda порт, таймаут: {
        "catalog_revision": "rev-h", "catalog_path": str(ф),
        "process_start_time": "2000-01-01T00:00:00Z"})
    monkeypatch.setattr(МОД, "заголовки_ответа", lambda порт, таймаут: {
        "x-catalog-revision": "не-должно-пригодиться"})
    итог = МОД.проверить("ячейка", 1)
    assert итог["загружено"] == "rev-h"
    assert итог["объяснение"] == "процесс старше файла"


def test_путь_по_данным_берётся_из_описи_а_не_угадывается(monkeypatch, tmp_path):
    """Выдуманный путь дал бы ложное «РАСХОЖДЕНИЕ», поэтому путь — из описи.

    Нет записи, нет `data_dir`, нет файла — возвращается пусто, и ячейка
    честно остаётся неизмеренной.
    """
    каталог = tmp_path / "data"
    каталог.mkdir()
    (каталог / "zona-09-catalog.json").write_text("{}", encoding="utf-8")
    реестр = tmp_path / "config" / "site-cells.json"
    реестр.parent.mkdir()
    реестр.write_text(json.dumps({"cells": [
        {"site_id": "zona-09", "runtime": {"data_dir": str(каталог)}},
        {"site_id": "zona-10", "runtime": {"data_dir": str(каталог)}},
        {"site_id": "zona-11", "runtime": {}},
    ]}), encoding="utf-8")
    monkeypatch.setattr(МОД, "__file__", str(tmp_path / "a" / "b" / "c.py"))
    assert МОД.путь_по_данным("zona-09") == str(каталог / "zona-09-catalog.json")
    assert МОД.путь_по_данным("zona-10") == "", "файла нет — пути нет"
    assert МОД.путь_по_данным("zona-11") == "", "data_dir не назван"
    assert МОД.путь_по_данным("нет-такой") == ""


def _реестр(tmp_path: Path, ячейки: list) -> None:
    """Подменяет корень модуля, чтобы запись читалась из своего реестра."""
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config" / "site-cells.json").write_text(
        json.dumps({"cells": ячейки}), encoding="utf-8")


def _юнит(tmp_path: Path, имя: str, тело: str, *, включён: bool) -> None:
    (tmp_path / "units").mkdir(exist_ok=True)
    (tmp_path / "units" / имя).write_text(тело, encoding="utf-8")
    (tmp_path / "wants").mkdir(exist_ok=True)
    if включён:
        (tmp_path / "wants" / имя).write_text("", encoding="utf-8")


def test_объявленный_путь_расходится_с_юнитом(tmp_path, monkeypatch):
    """Доставка берёт путь ИЗ РЕЕСТРА, поэтому расхождение молчаливо фатально.

    Так уже было: zona-02, измерено 2026-10-08 — издатель клал снимок в
    `/srv/lords/.frontend/...`, витрина читала `/srv/zonafilm-cc/data`,
    разница 6791 произведение, отчёт доставки при этом был успешным.
    """
    _реестр(tmp_path, [{"site_id": "zona-02", "runtime": {
        "unit": "nova-zonafilm-cc.service",
        "data_dir": "/srv/lords/.frontend/sites/zona-02/data"}}])
    _юнит(tmp_path, "nova-zonafilm-cc.service",
          "ExecStart=/usr/bin/python3 run.py --port 9123 "
          "--data-dir /srv/zonafilm-cc/data\n", включён=True)
    monkeypatch.setattr(МОД, "__file__", str(tmp_path / "a" / "b" / "c.py"))
    monkeypatch.setattr(МОД, "КАТАЛОГИ_ЮНИТОВ", (tmp_path / "units",))
    monkeypatch.setattr(МОД, "ВКЛЮЧЁННЫЕ", tmp_path / "wants")
    итог = МОД.сверка_объявления("zona-02")
    assert итог.startswith("РАСХОЖДЕНИЕ ОБЪЯВЛЕНИЯ")
    assert "/srv/lords/.frontend/sites/zona-02/data" in итог
    assert "/srv/zonafilm-cc/data" in итог


def test_совпавшее_объявление_не_поднимает_тревогу(tmp_path, monkeypatch):
    """Отрицательный контроль: исправная ячейка не попадает в находки."""
    _реестр(tmp_path, [{"site_id": "zona-02", "runtime": {
        "unit": "nova-zonafilm-cc.service",
        "data_dir": "/srv/zonafilm-cc/data/"}}])
    _юнит(tmp_path, "nova-zonafilm-cc.service",
          "ExecStart=run.py --data-dir /srv/zonafilm-cc/data\n", включён=True)
    monkeypatch.setattr(МОД, "__file__", str(tmp_path / "a" / "b" / "c.py"))
    monkeypatch.setattr(МОД, "КАТАЛОГИ_ЮНИТОВ", (tmp_path / "units",))
    monkeypatch.setattr(МОД, "ВКЛЮЧЁННЫЕ", tmp_path / "wants")
    assert МОД.сверка_объявления("zona-02") == "совпадает"


def test_выключенный_юнит_называется_отдельно(tmp_path, monkeypatch):
    """«Включён» — это ссылка в multi-user.target.wants, и только она.

    Прежний юнит ячейки может остаться на диске с правильным путём; если он
    не включён, его ExecStart ничего не говорит о живой витрине.
    """
    _реестр(tmp_path, [{"site_id": "zona-02", "runtime": {
        "unit": "nova-zona-02.service", "data_dir": "/srv/zonafilm-cc/data"}}])
    _юнит(tmp_path, "nova-zona-02.service",
          "ExecStart=run.py --data-dir /srv/zonafilm-cc/data\n", включён=False)
    monkeypatch.setattr(МОД, "__file__", str(tmp_path / "a" / "b" / "c.py"))
    monkeypatch.setattr(МОД, "КАТАЛОГИ_ЮНИТОВ", (tmp_path / "units",))
    monkeypatch.setattr(МОД, "ВКЛЮЧЁННЫЕ", tmp_path / "wants")
    assert "НЕ включён" in МОД.сверка_объявления("zona-02")


def test_нечитаемый_юнит_не_выдаётся_за_совпадение(tmp_path, monkeypatch):
    _реестр(tmp_path, [
        {"site_id": "нет-юнита", "runtime": {"data_dir": "/srv/x/data"}},
        {"site_id": "нет-файла", "runtime": {
            "unit": "нет-такого.service", "data_dir": "/srv/x/data"}},
        {"site_id": "без-ключа", "runtime": {
            "unit": "пустой.service", "data_dir": "/srv/x/data"}}])
    _юнит(tmp_path, "пустой.service", "ExecStart=run.py --port 9999\n",
          включён=True)
    monkeypatch.setattr(МОД, "__file__", str(tmp_path / "a" / "b" / "c.py"))
    monkeypatch.setattr(МОД, "КАТАЛОГИ_ЮНИТОВ", (tmp_path / "units",))
    monkeypatch.setattr(МОД, "ВКЛЮЧЁННЫЕ", tmp_path / "wants")
    assert МОД.сверка_объявления("нет-юнита") == "юнит не назван в реестре"
    assert "не прочитан" in МОД.сверка_объявления("нет-файла")
    assert МОД.сверка_объявления("без-ключа") == "юнит не передаёт --data-dir"


def test_витрина_с_верховым_приложением_называется(tmp_path, monkeypatch):
    """Возраст снимка у такой ячейки НЕ говорит о свежести содержимого.

    Измерено 2026-10-18: у yummy-site снимок каталога от 2026-09-10 — 38
    суток, а публичная главная отдаёт материалы с датой 2026-10-18. Содержимое
    приходит от верхового приложения (`LORDS_LEGACY_UPSTREAM`), а снимок
    остаётся проверкой «есть чем стартовать». Без этой графы инструмент
    подсказал бы вывод «содержимое устарело на 38 суток», и он был бы ложным.
    """
    корень = tmp_path / "srv" / "yummyani-site"
    (корень / "current" / "config").mkdir(parents=True)
    (корень / "current" / "config" / "site.json").write_text(json.dumps({
        "environment": {"LORDS_LEGACY_UPSTREAM": "127.0.0.1:3101"}}),
        encoding="utf-8")
    _реестр(tmp_path, [{"site_id": "yummy-site", "runtime": {
        "app_dir": str(корень / "app")}}])
    monkeypatch.setattr(МОД, "__file__", str(tmp_path / "a" / "b" / "c.py"))
    assert МОД.содержимое_с_верха("yummy-site") == "127.0.0.1:3101"


def test_витрина_без_верхового_приложения_не_оговаривается(tmp_path, monkeypatch):
    корень = tmp_path / "srv" / "zonafilm-space"
    (корень / "current" / "config").mkdir(parents=True)
    (корень / "current" / "config" / "site.json").write_text(json.dumps({
        "environment": {"LORDS_CATALOG": "<data>/zona-01-catalog.json"}}),
        encoding="utf-8")
    _реестр(tmp_path, [{"site_id": "zona-01", "runtime": {
        "app_dir": str(корень / "app")}}])
    monkeypatch.setattr(МОД, "__file__", str(tmp_path / "a" / "b" / "c.py"))
    assert МОД.содержимое_с_верха("zona-01") == ""
    assert МОД.содержимое_с_верха("нет-записи") == ""


def test_неизмеримая_ячейка_с_верхом_говорит_об_этом(tmp_path, monkeypatch):
    """Пробел наблюдаемости остаётся пробелом, но риск за ним — другой."""
    monkeypatch.setattr(МОД, "порт_ячейки", lambda имя: "9999")
    monkeypatch.setattr(МОД, "ответ_healthz", lambda порт, таймаут: {"ok": True})
    monkeypatch.setattr(МОД, "заголовки_ответа", lambda порт, таймаут: {})
    monkeypatch.setattr(МОД, "сверка_объявления", lambda имя: "совпадает")
    monkeypatch.setattr(МОД, "содержимое_с_верха", lambda имя: "127.0.0.1:3101")
    итог = МОД.проверить("yummy-site", 1)
    assert "НЕ ИЗМЕРЕНО" in итог["вывод"]
    assert "источником содержимого не является" in итог["вывод"]
    assert итог["верх"] == "127.0.0.1:3101"


def test_процесс_старше_файла_не_объявляется_доказательством():
    """Поправка измерением, а не осторожностью.

    Доставка перезаписывает файл каждые сутки даже при неизменном содержимом:
    конвейер пишет `skipped: «вход не изменился»` при совпавшем digest
    (измерено 2026-10-18 на animedia-01/02, вход не менялся с 2026-09-07).
    Значит mtime новый, а ревизия — та же, что процесс загрузил при старте, и
    «процесс старше файла» перечитывания не доказывает.
    """
    тело = ПУТЬ.read_text(encoding="utf-8")
    assert "вход не изменился" in тело, (
        "основание поправки обязано быть названо рядом с ней")
    for ложь in ("перечитывание РАБОТАЕТ", "перечитывание работает, "):
        assert ложь not in тело, f"инструмент не вправе утверждать «{ложь}»"
    assert "Для доказательства нужна ревизия, менявшаяся" in тело


def test_заголовки_разбираются_без_учёта_регистра(monkeypatch):
    """`curl -D -` печатает их как отдал сервер; имена нечувствительны."""
    class Готово:
        stdout = ("HTTP/1.1 200 OK\r\nX-Catalog-Revision: abc\r\n"
                  "Content-Type: text/html\r\nСтрока без двоеточия\r\n")
    monkeypatch.setattr(МОД.subprocess, "run", lambda *а, **к: Готово())
    з = МОД.заголовки_ответа("9999", 1)
    assert з["x-catalog-revision"] == "abc"
    assert з["content-type"] == "text/html"


def test_совпадение_при_перезапуске_объясняется(tmp_path, monkeypatch):
    """Процесс младше файла — совпадение ревизий ничего не доказывает."""
    ф = _файл(tmp_path, '{"revision":"rev-1","items":[]}')
    старое = 1_700_000_000
    os.utime(ф, (старое, старое))
    monkeypatch.setattr(МОД, "порт_ячейки", lambda имя: "9999")
    monkeypatch.setattr(МОД, "ответ_healthz", lambda порт, таймаут: {
        "catalog_revision": "rev-1", "catalog_path": str(ф),
        "process_start_time": "2026-10-18T04:05:40Z"})
    итог = МОД.проверить("ячейка", 1)
    assert итог["вывод"] == "снимок у приложения"
    assert итог["объяснение"] == "перезапуск"


def test_процесс_старше_файла_это_перечитывание(tmp_path, monkeypatch):
    """Единственный случай, который доказывает перечитывание."""
    ф = _файл(tmp_path, '{"revision":"rev-2","items":[]}')
    monkeypatch.setattr(МОД, "порт_ячейки", lambda имя: "9999")
    monkeypatch.setattr(МОД, "ответ_healthz", lambda порт, таймаут: {
        "catalog_revision": "rev-2", "catalog_path": str(ф),
        "process_start_time": "2000-01-01T00:00:00Z"})
    итог = МОД.проверить("ячейка", 1)
    assert итог["объяснение"] == "процесс старше файла"


def test_расхождение_называется_прямо(tmp_path, monkeypatch):
    ф = _файл(tmp_path, '{"revision":"на-диске","items":[]}')
    monkeypatch.setattr(МОД, "порт_ячейки", lambda имя: "9999")
    monkeypatch.setattr(МОД, "ответ_healthz", lambda порт, таймаут: {
        "catalog_revision": "загружено-другое", "catalog_path": str(ф),
        "process_start_time": "2000-01-01T00:00:00Z"})
    итог = МОД.проверить("ячейка", 1)
    assert итог["вывод"].startswith("РАСХОЖДЕНИЕ")
