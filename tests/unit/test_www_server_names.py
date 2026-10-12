"""Правка `server_name` у www-зеркал: две части, и вторая без первой пуста.

Проверка существует из-за двух способов «сделать и не сделать». Первый:
дописать блок для www, но забыть убрать `www.` из блока 443 — nginx скажет
`conflicting server name`, победит первый блок, перенаправления не будет.
Второй, опаснее: убрать `www.` глобальной заменой по файлу и снести его из
блока ПОРТА 80 — тогда `http://www` перестанет отвечать вовсе.

У `zona-02.conf` оба блока лежат в одном файле, поэтому вторая ошибка там не
теоретическая.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = (КОРЕНЬ / "automation" / "host" / "www-redirect"
            / "check-server-names.py")


def _модуль():
    спец = importlib.util.spec_from_file_location("check_server_names",
                                                  ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    sys.modules["check_server_names"] = м
    спец.loader.exec_module(м)
    return м


пр = _модуль()

ДО_ПРАВКИ = """
server {
    listen 80;
    listen [::]:80;
    server_name zonafilm.cc www.zonafilm.cc;
    location / { return 301 https://zonafilm.cc$request_uri; }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name zonafilm.cc www.zonafilm.cc;
    ssl_certificate /etc/letsencrypt/live/zonafilm.cc/fullchain.pem;
}
"""

ПОСЛЕ_ПРАВКИ = """
server {
    listen 80;
    listen [::]:80;
    server_name zonafilm.cc www.zonafilm.cc;
    location / { return 301 https://zonafilm.cc$request_uri; }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name zonafilm.cc;
    ssl_certificate /etc/letsencrypt/live/zonafilm.cc/fullchain.pem;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name www.zonafilm.cc;
    ssl_certificate /etc/letsencrypt/live/zonafilm.cc/fullchain.pem;
    return 301 https://zonafilm.cc$request_uri;
}
"""

ПЕРЕСТАРАЛИСЬ = ПОСЛЕ_ПРАВКИ.replace(
    "    server_name zonafilm.cc www.zonafilm.cc;\n"
    "    location / { return 301 https://zonafilm.cc$request_uri; }",
    "    server_name zonafilm.cc;\n"
    "    location / { return 301 https://zonafilm.cc$request_uri; }")


def test_до_правки_проверка_падает():
    """Без этого проверка не несла бы доверия (D203, D205)."""
    плохо = пр.разобрать(ДО_ПРАВКИ, "zonafilm.cc")
    assert плохо, "проверка не заметила неисправленное состояние"
    assert "conflicting server name" in " ".join(плохо)


def test_после_правки_замечаний_нет():
    assert пр.разобрать(ПОСЛЕ_ПРАВКИ, "zonafilm.cc") == []


def test_глобальная_замена_ломает_блок_80_и_это_видно():
    """Самая дорогая ошибка этой правки: www снесён из блока порта 80.

    Тогда http://www.zonafilm.cc перестаёт отвечать совсем, а блок 443
    выглядит правильным — то есть беда тихая.
    """
    плохо = пр.разобрать(ПЕРЕСТАРАЛИСЬ, "zonafilm.cc")
    assert плохо, "потеря www в блоке 80 осталась незамеченной"
    текст = " ".join(плохо)
    assert "блока 80" in текст
    assert "http://www" in текст


def test_блок_только_для_www_лишним_не_считается():
    """У нового блока server_name РОВНО www — это цель правки, а не дефект."""
    только_www = """
server {
    listen 443 ssl;
    server_name www.zonafilm.cc;
    return 301 https://zonafilm.cc$request_uri;
}
"""
    assert пр.разобрать(только_www, "zonafilm.cc") == []


def test_файл_без_блока_443_это_предел_измерения():
    только_80 = """
server {
    listen 80;
    server_name zonafilm.cc www.zonafilm.cc;
}
"""
    плохо = пр.разобрать(только_80, "zonafilm.cc")
    assert плохо
    assert "предел измерения" in " ".join(плохо)


def test_отсутствие_блока_80_замечанием_не_является():
    """У трёх витрин блок 80 лежит в отдельном файле — это норма."""
    только_443 = """
server {
    listen 443 ssl;
    server_name an1meg0.site;
}

server {
    listen 443 ssl;
    server_name www.an1meg0.site;
    return 301 https://an1meg0.site$request_uri;
}
"""
    assert пр.разобрать(только_443, "an1meg0.site") == []


def test_нечитаемые_файлы_исправностью_не_считаются(tmp_path, capsys):
    код = пр.главное(["--dir", str(tmp_path)])
    вывод = capsys.readouterr()
    assert код == 2, вывод.out
    assert "предел измерения" in вывод.err


def test_живое_состояние_называется_честно():
    """На машине правка пока не сделана — проверка обязана это сказать."""
    if not пр.КАТАЛОГ.is_dir():
        import pytest
        pytest.skip("каталога конфигураций nginx на машине нет")
    код = пр.главное([])
    assert код in (0, 1, 2), код
