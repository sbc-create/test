"""Кто держит память узла: перечень для решения владельца, без остановки чего-либо.

Повод измерен 25.10. Шлюз фонового редактора требует 2 048 МиБ свободной
памяти и отказывал каждые пять минут при 1 691–1 905 МиБ; редактор с 03:51Z не
опубликовал ничего. Отказ не тратит квоту — и всё же это ОСТАНОВКА, а не
экономия, и владельцу нужен перечень держателей, а не слово «мало».

Главное требование к этому инструменту — не выдавать отсутствие измерения за
отсутствие проблемы: витрина, чей домен или его разрешение не установлены,
попадает в «НЕ ИЗМЕРЕНО», а не в «освободимо». Обратная ошибка уже стоила
отчёта: доля освободимой памяти была напечатана, когда реестр ячеек не
читался вовсе, и перечень честно показывал «не проверено» по всем 15 витринам.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import socket

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation/local/node-memory-holders.py"
_спец = importlib.util.spec_from_file_location("node_memory_holders", _путь)
ПАМ = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(ПАМ)


def поддельный_proc(tmp_path: pathlib.Path, процессы: dict[int, tuple[int, str]]):
    for pid, (кб, команда) in процессы.items():
        д = tmp_path / str(pid)
        д.mkdir()
        (д / "status").write_text(f"Name:\tx\nVmRSS:\t{кб} kB\n", encoding="utf-8")
        (д / "cmdline").write_bytes(команда.replace(" ", "\0").encode())
    (tmp_path / "нечисло").mkdir()
    return tmp_path


def test_процессы_ниже_порога_не_попадают(tmp_path) -> None:
    корень = поддельный_proc(tmp_path, {
        11: (2_000_000, "/usr/bin/python3 /srv/zonafilm-cc/releases/a1/src/serve.py"),
        12: (10_000, "/usr/bin/python3 мелочь.py")})
    итог = ПАМ.процессы(60, корень)
    assert [з["pid"] for з in итог] == [11]
    assert итог[0]["миб"] == 1953


def test_процесс_без_vmrss_пропускается(tmp_path) -> None:
    (tmp_path / "13").mkdir()
    (tmp_path / "13" / "status").write_text("Name:\tядро\n", encoding="utf-8")
    (tmp_path / "13" / "cmdline").write_bytes(b"")
    assert ПАМ.процессы(1, tmp_path) == []


@pytest.mark.parametrize("команда,ожидание", [
    ("/usr/bin/python3 /srv/zonafilm-cc/releases/36fd/src/serve.py --port 9123", "zonafilm-cc"),
    ("/usr/bin/python3 /srv/site-1lordserials1-online/releases/d16/overlay/main.py", "site-1lordserials1-online"),
    ("claude --resume", ""),
])
def test_каталог_витрины_из_пути_выпуска(команда, ожидание) -> None:
    assert ПАМ.ячейка_процесса(команда) == ожидание


def test_карта_каталогов_знает_приставку_site(tmp_path) -> None:
    реестр = tmp_path / "site-cells.json"
    реестр.write_text(json.dumps({"cells": [
        {"site_id": "lords-04", "domain": "1lordserials1.online",
         "repo": {"path": "var/site-repos/site-1lordserials1-online"}}]}), encoding="utf-8")
    карта = ПАМ.домены(реестр)
    assert карта["1lordserials1-online"] == "1lordserials1.online"
    assert карта["site-1lordserials1-online"] == "1lordserials1.online"
    assert карта["lords-04"] == "1lordserials1.online"


def test_нечитаемый_реестр_не_придумывает_доменов(tmp_path) -> None:
    assert ПАМ.домены(tmp_path / "нет.json") == {}


def test_nxdomain_это_нет_домена_а_сбой_это_не_измерено() -> None:
    нет = socket.gaierror(socket.EAI_NONAME, "Name or service not known")
    нет.errno = socket.EAI_NONAME
    сбой = socket.gaierror(socket.EAI_AGAIN, "Temporary failure")
    сбой.errno = socket.EAI_AGAIN

    def кидает(ош):
        def _(имя):
            raise ош
        return _

    assert ПАМ.разрешается("x", резолвер=кидает(нет)) is False
    assert ПАМ.разрешается("x", резолвер=кидает(сбой)) is None
    assert ПАМ.разрешается("x", резолвер=lambda имя: "127.0.0.1") is True


def test_освободимо_считается_только_по_подтверждённому_отсутствию_dns() -> None:
    записи = [
        {"миб": 1240, "pid": 1, "команда": "/usr/bin/python3 /srv/lordfilm47-space/releases/a/x.py"},
        {"миб": 900, "pid": 2, "команда": "/usr/bin/python3 /srv/animedia-space/releases/b/x.py"},
        {"миб": 500, "pid": 3, "команда": "/usr/bin/python3 /srv/some-new-site/releases/c/x.py"},
        {"миб": 1000, "pid": 4, "команда": "claude --resume"},
    ]
    карта = {"lordfilm47-space": "lordfilm47.space", "animedia-space": "animedia.space"}
    нет = socket.gaierror(socket.EAI_NONAME, "нет такого имени")
    нет.errno = socket.EAI_NONAME

    def резолвер(имя):
        if имя == "lordfilm47.space":
            raise нет
        return "127.0.0.1"

    с = ПАМ.свод(записи, карта, резолвер=резолвер)
    assert с["освободимо_миб"] == 1240
    assert [в["домен"] for в in с["не_разрешаются"]] == ["lordfilm47.space"]
    # Витрина без домена в реестре — «не проверено», и в освободимое не идёт.
    неизвестная = [в for в in с["витрины"] if в["каталог"] == "some-new-site"][0]
    assert неизвестная["разрешается"] is None
    assert с["по_виду"]["сеанс claude"] == 1000
    assert с["по_виду"]["витрина"] == 2640
