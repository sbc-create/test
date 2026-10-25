"""Заготовка nginx новой витрины: закрыта, раздельна и без выдуманного DNS.

Заготовки писались по одной на витрину; на партии из пяти это пять шансов на
опечатку в домене, порте или имени включаемого файла режима индексации.
Генератор убирает эти шансы, но вносит свой: ошибка в шаблоне повторится у всех
пяти сразу. Поэтому здесь закреплены свойства, каждое из которых выросло из
измеренного случая.

Главное из них — про «не измерено». Первая редакция генератора читала ответ
общего модуля DNS своими именами ключей и напечатала в файлы «DNS НЕ ИЗМЕРЕНО»
при исправном ответе зоны. Запись «не измерено» там, где измерение есть, хуже
отсутствия строки: её читают как факт.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation/local/render-cell-nginx.py"
_спец = importlib.util.spec_from_file_location("render_cell_nginx", _путь)
РЕН = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(РЕН)

ДНС = {"at": "2026-10-25T22:03Z", "NS": "april.ns.cloudflare.com", "A": "45.131.182.225"}


@pytest.fixture()
def http_тело() -> str:
    return РЕН.тело_http("lords-18", "lordserials1.cc", 9136, ДНС)


@pytest.fixture()
def tls_тело() -> str:
    return РЕН.тело_tls("lords-18", "lordserials1.cc")


def test_блок_443_не_попадает_в_файл_http(http_тело) -> None:
    """Ссылка на невыпущенный сертификат не даёт nginx перезагрузиться ВОВСЕ."""
    assert "listen 443" not in http_тело
    assert "ssl_certificate" not in http_тело


def test_индексация_закрыта_через_включаемый_файл(http_тело, tls_тело) -> None:
    """Два источника режима на один домен разошлись бы незаметно для всех, кроме обхода."""
    for тело in (http_тело, tls_тело):
        assert "$cell_robots_lords_18" in тело
    assert "include /etc/nginx/cells/lords-18.robots;" in http_тело
    assert "index, follow" not in http_тело


def test_www_отдельным_блоком_с_перенаправлением(http_тело) -> None:
    """У lords-05 www стояло рядом с apex и отдавало каталог 200 с canonical на себя."""
    assert "server_name www.lordserials1.cc;" in http_тело
    assert "return 301 https://lordserials1.cc$request_uri;" in http_тело


def test_маршрут_идёт_через_upstream_а_не_напрямую(http_тело, tls_тело) -> None:
    """Upstream — точка переключения трафика при выкладке."""
    assert "http://cell_lords_18" in tls_тело
    assert "proxy_pass http://127.0.0.1:9136" not in tls_тело
    assert "proxy_pass http://127.0.0.1:9136" not in http_тело


def test_путь_acme_оставлен_на_обоих_блоках(http_тело, tls_тело) -> None:
    """Без него не выпустить и не продлить сертификат."""
    assert http_тело.count("/.well-known/acme-challenge/") >= 2
    assert "/.well-known/acme-challenge/" in tls_тело


def test_dns_попадает_в_заголовок_как_измерение(http_тело) -> None:
    assert "DNS измерен 2026-10-25T22:03Z" in http_тело
    assert "45.131.182.225" in http_тело


def test_неответ_зоны_называется_не_измеренным(monkeypatch) -> None:
    """«Не измерено» ставится ТОЛЬКО когда зона действительно не ответила."""
    класс = type("М", (), {
        "резолверы": staticmethod(lambda: ["8.8.8.8"]),
        "запрос": staticmethod(lambda д, т, с: {"rcode": "SERVFAIL", "answers": []}),
    })
    monkeypatch.setattr(РЕН, "_днс", lambda: класс)
    св = РЕН.измерить_днс("proba.invalid")
    assert св["A"].startswith("НЕ ИЗМЕРЕНО") and "SERVFAIL" in св["A"]


def test_исправный_ответ_не_называется_не_измеренным(monkeypatch) -> None:
    """Та самая ошибка: своё имя ключа дало «не измерено» при живом ответе."""
    класс = type("М", (), {
        "резолверы": staticmethod(lambda: ["8.8.8.8"]),
        "запрос": staticmethod(lambda д, т, с: {
            "rcode": "NOERROR",
            "answers": [{"value": "45.131.182.225", "type": т}]}),
    })
    monkeypatch.setattr(РЕН, "_днс", lambda: класс)
    св = РЕН.измерить_днс("lordserials1.cc")
    assert св["A"] == "45.131.182.225"
    assert "НЕ ИЗМЕРЕНО" not in св["NS"]


def test_все_пять_заготовок_существуют_и_согласованы() -> None:
    """Проверка на фактических файлах: домен и порт совпадают с паспортом."""
    import json

    реестр = {з["site_id"]: з for з in json.loads(
        (КОРЕНЬ / "config/site-cells.json").read_text(encoding="utf-8"))["cells"]}
    for сид in ("lords-18", "lords-19", "lords-20", "lords-21", "lords-22"):
        домен = реестр[сид]["domain"]
        for хвост in ("", "-tls"):
            п = КОРЕНЬ / "automation/host/nginx-site" / f"{сид}{хвост}.conf"
            assert п.is_file(), п
            т = п.read_text(encoding="utf-8")
            assert f"server_name {домен};" in т, (сид, хвост)
            assert f"$cell_robots_{сид.replace('-', '_')}" in т
