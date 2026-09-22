"""Проверяющий nginx не должен спотыкаться о точку с запятой внутри кавычек.

Найдено при проверке vhost для zonafilm.cc. Конфигурация корректна и nginx её
принимает, а офлайн-проверка отвергла её трижды:

* `add_header Content-Security-Policy "…; …; …" always;` — разбор директивы
  обрывался на ПЕРВОЙ точке с запятой внутри кавычек, слово `always` в хвост не
  попадало, и проверка сообщала об отсутствии `always`, которое на месте;
* `server_tokens`, `allow`, `deny` — обычные директивы nginx, которых просто не
  было в списке известных, потому что vhost'ы Lords их не используют.

Оба класса — ложные срабатывания, и оба опасны одинаково: проверка, которая
ругается на верную конфигурацию, учит править конфигурацию под проверку.
CSP без `always` не попал бы на 404 и 5xx — то есть «исправление» под ложное
срабатывание сняло бы заголовок безопасности с тех самых ответов, ради которых
`always` и требуется.
"""

from __future__ import annotations

import pytest

from factory.lords import nginx_check

CSP = ("default-src 'self'; img-src 'self' https: data:; "
       "style-src 'self' 'unsafe-inline'; object-src 'none'")


def _конфиг(тело: str) -> str:
    return (
        "server {\n"
        "    listen 443 ssl;\n"
        "    server_name example.test;\n"
        "    ssl_certificate /etc/letsencrypt/live/example.test/fullchain.pem;\n"
        "    ssl_certificate_key /etc/letsencrypt/live/example.test/privkey.pem;\n"
        "    ssl_protocols TLSv1.2 TLSv1.3;\n"
        f"{тело}"
        "}\n"
    )


def test_точка_с_запятой_в_кавычках_не_обрывает_директиву():
    текст = _конфиг(f'    add_header Content-Security-Policy "{CSP}" always;\n')
    r = nginx_check.check(текст, expect_tls=True)
    assert r.ok, f"верная конфигурация отвергнута: {r.problems}"


def test_отсутствие_always_по_прежнему_ловится_и_в_кавычках():
    """Починка не имеет права ослабить саму проверку."""
    текст = _конфиг(f'    add_header Content-Security-Policy "{CSP}";\n')
    r = nginx_check.check(текст, expect_tls=True)
    assert not r.ok
    assert any("always" in p for p in r.problems), r.problems


def test_обычные_директивы_nginx_не_считаются_опечаткой():
    текст = _конфиг(
        "    server_tokens off;\n"
        "    location = /healthz {\n"
        "        allow 127.0.0.1;\n"
        "        deny all;\n"
        "        proxy_pass http://127.0.0.1:9123/healthz;\n"
        "    }\n"
    )
    r = nginx_check.check(текст, expect_tls=True)
    assert r.ok, f"обычные директивы приняты за опечатку: {r.problems}"


def test_настоящая_опечатка_всё_ещё_ловится():
    текст = _конфиг("    server_tokenz off;\n")
    r = nginx_check.check(текст, expect_tls=True)
    assert not r.ok
    assert any("server_tokenz" in p for p in r.problems), r.problems


def test_директива_из_новой_версии_по_прежнему_отвергается():
    текст = _конфиг("    http2 on;\n")
    r = nginx_check.check(текст, expect_tls=True)
    assert not r.ok
    assert any("http2" in p for p in r.problems), r.problems


@pytest.mark.parametrize("путь", ["automation/host/nginx/zona-02.conf"])
def test_боевой_vhost_zonafilm_cc_проходит_проверку(путь):
    """Ради этого проверка и запускалась: конфигурация уедет на хост 1.18."""
    from pathlib import Path
    корень = Path(__file__).resolve().parents[2]
    файл = корень / путь
    if not файл.is_file():
        pytest.skip(f"нет {путь}")
    r = nginx_check.check(файл.read_text(encoding="utf-8"), expect_tls=True)
    assert r.ok, f"{путь}: {r.problems}"
    assert r.servers >= 3, "в конфигурации ожидаются блоки http, www и apex"
