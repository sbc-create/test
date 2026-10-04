"""Нечитаемая конфигурация nginx: «открыт» подтверждается ИЗМЕРЕНИЕМ.

Случай измерен 2026-10-04 на lordserials22.info и остановил уже сделанное
открытие. Исполнитель применил слой — `/etc/nginx/cells/lords-05.robots` стал
`default ""`, то есть заголовок не добавляется, — а вердикт ответил `unknown`
и операция откатила открытие со словами «исполнитель отработал, но слой nginx
остался 'unknown': … часть конфигураций не читается
(['/etc/nginx/conf.d/lords.conf: PermissionError']), а измерения нет».

Причина не в правах и не в разрешении: `/etc/nginx/conf.d/lords.conf` —
`root:root 0600`, и непривилегированная сторона его не прочитает никогда. Сама
логика вердикта этот случай предусматривает: нечитаемая конфигурация плюс
надбавка nginx к заголовкам приложения, равная нулю, означает «открыт».
Измерения на том вызове просто не было — вердикт звали без публичных сигналов.

Здесь закреплены оба свойства: без измерения «открыт» не объявляется (это
правильная осторожность), а с измерением — объявляется.
"""
from __future__ import annotations

import pathlib

import pytest

from factory.cell import nginx_indexing
from factory.qwen import indexing

САЙТ = "t-layer-01"
ДОМЕН = "t-layer.example"


@pytest.fixture()
def конфигурации(tmp_path, monkeypatch):
    """Корень nginx, где слой ОТКРЫТ, а одна конфигурация не читается."""
    корень = tmp_path / "nginx"
    (корень / "lords").mkdir(parents=True)
    (корень / "cells").mkdir(parents=True)
    перем = nginx_indexing.имя_переменной(САЙТ)
    включаемый = корень / "cells" / f"{САЙТ}.robots"
    включаемый.write_text('default "";\n', encoding="utf-8")
    (корень / "lords" / f"{САЙТ}.conf").write_text(
        f"map $uri ${перем} {{\n    include {включаемый};\n}}\n\n"
        "server {\n"
        f"    server_name {ДОМЕН};\n"
        f"    add_header X-Robots-Tag ${перем} always;\n"
        "    location / { proxy_pass http://127.0.0.1:9999; }\n"
        "}\n", encoding="utf-8")
    # Та самая нечитаемая конфигурация: на живом хосте это root:root 0600.
    чужая = корень / "lords" / "чужая.conf"
    чужая.write_text("# сюда непривилегированной стороне не попасть\n",
                     encoding="utf-8")
    чужая.chmod(0o000)
    monkeypatch.setattr(nginx_indexing, "КОРЕНЬ_NGINX", корень)
    monkeypatch.setattr(nginx_indexing, "КАТАЛОГ_ВКЛЮЧАЕМЫХ", корень / "cells")
    return корень


def _сигналы(*, надбавка: int) -> dict:
    """Публичный ответ: заголовки приложения и общий счёт на https.

    `надбавка` — сколько заголовков добавляет САМ nginx поверх приложения.
    Ноль означает, что запрета от nginx нет.
    """
    свои: list[str] = []
    return {
        "domain": ДОМЕН, "at": "тест", "home_http": "200",
        "x_robots_values_app": свои,
        "x_robots_values": свои + ["noindex, nofollow"] * надбавка,
        "x_robots_count": len(свои) + надбавка,
        "x_robots_count_service": len(свои) + надбавка,
        "x_robots_values_service": [],
        "meta_robots_home": "index, follow",
        "canonical_home": f"https://{ДОМЕН}/",
        "robots_txt": "User-agent: *\nAllow: /\n", "robots_txt_http": "200",
        "sitemap_http": "200", "service_path": "/healthz",
        "service_path_http": "200",
    }


def test_без_измерения_открытым_слой_не_объявляется(конфигурации):
    """Правильная осторожность: не прочитал — не утверждай."""
    слой = indexing.слой_nginx(САЙТ, ДОМЕН)
    assert слой["mode"] == "unknown", слой
    assert слой["denying"] is None
    assert "не читается" in слой["evidence"], слой["evidence"]
    assert not indexing.слой_в_нужном_режиме(слой, indexing.ОТКРЫТ)


def test_с_измерением_слой_объявляется_открытым(конфигурации):
    """Надбавки nginx нет — значит запрета от nginx нет."""
    слой = indexing.слой_nginx(САЙТ, ДОМЕН, _сигналы(надбавка=0))
    assert слой["mode"] == "open", слой
    assert слой["denying"] is False
    assert "измерение согласуется" in слой["evidence"], слой["evidence"]
    assert indexing.слой_в_нужном_режиме(слой, indexing.ОТКРЫТ)


def test_измерение_против_конфигурации_не_объявляет_открытым(конфигурации):
    """Конфигурация говорит «открыт», а заголовок в ответе есть — не верим."""
    слой = indexing.слой_nginx(САЙТ, ДОМЕН, _сигналы(надбавка=1))
    assert слой["mode"] == "unknown", слой
    assert слой["denying"] is None
    assert "надбавка nginx = 1" in слой["evidence"], слой["evidence"]


def test_операция_проверяет_слой_с_измерением():
    """Вердикт слоя после переключения зовётся С сигналами.

    Без них открытие на живом домене откатывалось при единственной нечитаемой
    конфигурации — то есть исправный результат объявлялся неудачей.
    """
    текст = pathlib.Path("factory/qwen/indexing.py").read_text(encoding="utf-8")
    assert "_слой_с_измерением" in текст, (
        "после переключения слой проверяется без публичного измерения: "
        "нечитаемая конфигурация снова отменит исправное открытие")
