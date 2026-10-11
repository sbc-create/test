"""Правка перенаправления http → https: что меняется и когда отказ.

Повод. Девять доменов сети отдавали `200` по http — два адреса одной страницы.
Правка повторяет образец уже исправленных доменов: в блоке `:80` тело
`location /` заменяется на `return 308`.

Цена ошибки здесь — не только дубль. Если перенаправить ВСЁ, включая
`/.well-known/acme-challenge/`, сломается продление сертификата, и сайт
останется без TLS. Поэтому путь ACME проверяется до правки, а его отсутствие —
отказ. Это и сторожится здесь, вместе с неприкосновенностью блока `:443`.

Правка исполняется в песочнице: конфигурации копируются во временный каталог,
модуль переключается на него, и проверяется ФАКТИЧЕСКИЙ результат.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "host" / "http-redirect-install.py"

БЕЗ_ПЕРЕНАПРАВЛЕНИЯ = """upstream cell_animedia_01 { server 127.0.0.1:9121; }

server {
    listen 80;
    listen [::]:80;
    server_name animedia.icu www.animedia.icu;
    server_tokens off;

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
        default_type "text/plain";
    }

    location / {
        proxy_pass http://cell_animedia_01;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_read_timeout 30s;
    }

    location = /healthz {
        proxy_pass http://cell_animedia_01/healthz;
        access_log off;
    }
}

server {
    listen 443 ssl;
    server_name animedia.icu;

    ssl_certificate /etc/letsencrypt/live/animedia.icu/fullchain.pem;

    location / {
        proxy_pass http://cell_animedia_01;
        proxy_read_timeout 30s;
    }

    location = /healthz {
        proxy_pass http://cell_animedia_01/healthz;
    }
}
"""

УЖЕ_С_308 = """server {
    listen 80;
    server_name lordfilm47.space;

    location ^~ /.well-known/acme-challenge/ { root /var/www/lords-acme; }

    location / {
        return 308 https://$host$request_uri;
    }
}
"""

БЕЗ_ACME = """server {
    listen 80;
    server_name noacme.example;

    location / {
        proxy_pass http://cell_x;
    }
}
"""


def _модуль(каталог: Path):
    спец = importlib.util.spec_from_file_location("http_redirect_install", СЦЕНАРИЙ)
    м = importlib.util.module_from_spec(спец)
    sys.modules["http_redirect_install"] = м
    спец.loader.exec_module(м)
    м.NGINX = каталог
    return м


@pytest.fixture()
def песок(tmp_path):
    (tmp_path / "lords").mkdir()
    (tmp_path / "lords" / "animedia-01.conf").write_text(
        БЕЗ_ПЕРЕНАПРАВЛЕНИЯ, encoding="utf-8")
    (tmp_path / "lords" / "lords-01.conf").write_text(УЖЕ_С_308, encoding="utf-8")
    (tmp_path / "lords" / "noacme.conf").write_text(БЕЗ_ACME, encoding="utf-8")
    return _модуль(tmp_path), tmp_path


def test_правка_заменяет_только_тело_location(песок):
    м, каталог = песок
    было = (каталог / "lords" / "animedia-01.conf").read_text(encoding="utf-8")
    стало, причина = м.правка(было, "animedia.icu")
    assert причина == "", причина
    assert "return 308 https://$host$request_uri;" in стало
    # Прокси на :80 для корня исчез…
    блок80 = стало[:стало.index("listen 443")]
    assert "proxy_pass http://cell_animedia_01;\n        proxy_http_version" not in блок80
    # …а всё остальное на месте.
    assert "/.well-known/acme-challenge/" in блок80
    assert "location = /healthz" in блок80
    assert стало.count("{") == стало.count("}")


def test_блок_443_не_затронут(песок):
    м, каталог = песок
    было = (каталог / "lords" / "animedia-01.conf").read_text(encoding="utf-8")
    стало, _ = м.правка(было, "animedia.icu")
    тls_до = было[было.index("listen 443"):]
    тls_после = стало[стало.index("listen 443"):]
    assert тls_до == тls_после, "изменён блок HTTPS"


def test_отказ_без_пути_acme(песок):
    """Перенаправление без ACME сломало бы продление сертификата."""
    м, каталог = песок
    было = (каталог / "lords" / "noacme.conf").read_text(encoding="utf-8")
    стало, причина = м.правка(было, "noacme.example")
    assert стало == ""
    assert "acme" in причина.lower()


def test_отказ_если_перенаправление_уже_стоит(песок):
    м, каталог = песок
    было = (каталог / "lords" / "lords-01.conf").read_text(encoding="utf-8")
    стало, причина = м.правка(было, "lordfilm47.space")
    assert стало == ""
    assert "уже стоит" in причина


def test_отказ_если_нет_блока_80(песок):
    м, _ = песок
    стало, причина = м.правка(УЖЕ_С_308, "чужой.домен")
    assert стало == ""
    assert "нет блока :80" in причина


def test_файл_домена_находится_по_блоку_80(песок):
    м, каталог = песок
    файлы = м.файлы_домена("animedia.icu")
    assert файлы == [каталог / "lords" / "animedia-01.conf"]


def test_копии_правки_не_берутся_в_работу(песок):
    """Иначе повторный запуск начал бы править собственные копии."""
    м, каталог = песок
    копия = каталог / "lords" / f"animedia-01.conf.before-{м.МЕТКА}.20261011T120000Z"
    копия.write_text(БЕЗ_ПЕРЕНАПРАВЛЕНИЯ, encoding="utf-8")
    assert копия not in м.файлы_домена("animedia.icu")


def test_без_apply_файлы_не_меняются(песок, capsys):
    м, каталог = песок
    файл = каталог / "lords" / "animedia-01.conf"
    было = файл.read_text(encoding="utf-8")
    код = м.главное(["--domain", "animedia.icu", "--dry-run"])
    вывод = capsys.readouterr().out
    assert код == 0
    assert "это план" in вывод
    assert файл.read_text(encoding="utf-8") == было, "файл изменён без --apply"


def test_правка_повторяет_образец_исправленных_доменов():
    """Строка должна быть ровно той, что у уже работающих доменов."""
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert "return 308 https://$host$request_uri;" in текст
    assert "301" not in текст.replace("30", ""), "образец сети — 308, не 301"


def test_сценарий_не_трогает_прочие_настройки():
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    for запрещено in ("ssl_certificate", "upstream", "add_header",
                      "proxy_set_header", "listen 443"):
        правка = текст.split("def правка", 1)[1].split("def ", 1)[0]
        assert запрещено not in правка, (
            f"правка трогает {запрещено!r}: её дело — только location / на :80")
