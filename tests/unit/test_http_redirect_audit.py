"""HTTP→HTTPS: отсутствие редиректа и его настоящая серьёзность.

Повод. Девять живых доменов отвечают по http кодом 200 вместо перехода на
https. Назвать это «дублем в индексе» было бы преувеличением, а «пустяком» —
преуменьшением, и решает различие ровно один измеримый признак: что говорит
canonical копии по http. Измерено 12.10: у всех девяти он уже указывает на
https, то есть копия сама называет правильный адрес.

Поэтому проверка обязана читать canonical, а не только код, и обязана
отличать «редиректа нет, но canonical на https» от «редиректа нет и canonical
чужой». Второй случай — настоящий дубль, первый — незашифрованный лишний ход.

Отдельно закреплён путь ACME: перенаправлять его нельзя, иначе продление
сертификата сломается, и это хуже отсутствия редиректа.

Сеть не используется: `ответ` подменяется.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "local" / "http-redirect-audit.py"

СТРАНИЦА = ('<html><head><link rel="canonical" href="https://x.example/">'
            '<meta name="robots" content="index, follow"></head></html>')
ЧУЖОЙ_CANONICAL = ('<html><head><link rel="canonical" href="http://x.example/">'
                   '<meta name="robots" content="index, follow"></head></html>')


def _модуль():
    спец = importlib.util.spec_from_file_location("http_redirect_audit", СЦЕНАРИЙ)
    м = importlib.util.module_from_spec(спец)
    sys.modules["http_redirect_audit"] = м
    спец.loader.exec_module(м)
    return м


@pytest.fixture()
def модуль():
    return _модуль()


def _подменить(м, monkeypatch, ответы):
    """ответы: (домен, путь) → (код, location, тело)."""
    def поддельный(домен, путь, *, тело=False):
        ключ = (домен, путь)
        assert ключ in ответы, f"тест не описал запрос {ключ}"
        код, куда, страница = ответы[ключ]
        return код, куда, (страница if тело else "")
    monkeypatch.setattr(м, "ответ", поддельный)


def test_редирект_на_https_признаётся(модуль, monkeypatch):
    _подменить(модуль, monkeypatch, {
        ("x.example", "/"): ("301", "https://x.example/", ""),
        ("x.example", модуль.ПУТЬ_ACME): ("404", "", ""),
    })
    итог = модуль.проверить("x.example")
    assert итог["перенаправляет"] is True
    assert итог["acme_жив"] is True


def test_редирект_на_чужой_домен_редиректом_не_считается(модуль, monkeypatch):
    """Переход на другой домен — не «включили https», а подмена адреса."""
    _подменить(модуль, monkeypatch, {
        ("x.example", "/"): ("301", "https://чужой.example/", ""),
        ("x.example", модуль.ПУТЬ_ACME): ("404", "", ""),
    })
    assert модуль.проверить("x.example")["перенаправляет"] is False


def test_код_200_с_canonical_на_https_смягчение_названо(модуль, monkeypatch):
    _подменить(модуль, monkeypatch, {
        ("x.example", "/"): ("200", "", СТРАНИЦА),
        ("x.example", модуль.ПУТЬ_ACME): ("404", "", ""),
    })
    итог = модуль.проверить("x.example")
    assert итог["перенаправляет"] is False
    assert итог["canonical_на_https"] is True
    assert итог["canonical_по_http"] == "https://x.example/"
    assert итог["robots_по_http"] == "index, follow"


def test_код_200_с_canonical_на_http_это_дубль(модуль, monkeypatch):
    """Вот это уже второй сайт в индексе, а не лишний ход."""
    _подменить(модуль, monkeypatch, {
        ("x.example", "/"): ("200", "", ЧУЖОЙ_CANONICAL),
        ("x.example", модуль.ПУТЬ_ACME): ("404", "", ""),
    })
    итог = модуль.проверить("x.example")
    assert итог["canonical_на_https"] is False


def test_вывод_различает_два_случая(модуль, monkeypatch):
    """В выдаче названо число домена БЕЗ canonical на https, а не только общее."""
    # canonical обязан называть СВОЙ домен: страница с чужим адресом в
    # canonical — другой случай, и смешивать его с этим нельзя.
    _подменить(модуль, monkeypatch, {
        ("тихий.example", "/"): (
            "200", "",
            '<link rel="canonical" href="https://тихий.example/">'),
        ("тихий.example", модуль.ПУТЬ_ACME): ("404", "", ""),
        ("дубль.example", "/"): (
            "200", "",
            '<link rel="canonical" href="http://дубль.example/">'),
        ("дубль.example", модуль.ПУТЬ_ACME): ("404", "", ""),
    })
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = модуль.главное(["тихий.example", "дубль.example"])
    вывод = буфер.getvalue()
    assert код == 1, "отсутствие редиректа обязано давать ненулевой код"
    assert "без перенаправления: 2" in вывод
    assert "БЕЗ canonical на https: 1" in вывод
    assert "дубль.example" in вывод.split("БЕЗ canonical на https")[1]


def test_перенаправление_пути_acme_это_отдельная_тревога(модуль, monkeypatch):
    """Сломанное продление хуже отсутствия редиректа, и говорится отдельно."""
    _подменить(модуль, monkeypatch, {
        ("x.example", "/"): ("301", "https://x.example/", ""),
        ("x.example", модуль.ПУТЬ_ACME): ("301", "https://x.example/", ""),
    })
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = модуль.главное(["x.example"])
    assert код == 1
    assert "продление" in буфер.getvalue()


def test_403_и_200_по_пути_acme_тоже_живой_путь(модуль, monkeypatch):
    """Токена нет — ответ любой, кроме перенаправления: путь не перехвачен."""
    for код_acme in ("403", "200", "404"):
        _подменить(модуль, monkeypatch, {
            ("x.example", "/"): ("301", "https://x.example/", ""),
            ("x.example", модуль.ПУТЬ_ACME): (код_acme, "", ""),
        })
        assert модуль.проверить("x.example")["acme_жив"] is True, код_acme


def test_отсутствие_ответа_не_выдаётся_за_редирект(модуль, monkeypatch):
    _подменить(модуль, monkeypatch, {
        ("x.example", "/"): ("нет ответа: TimeoutError", "", ""),
        ("x.example", модуль.ПУТЬ_ACME): ("нет ответа: TimeoutError", "", ""),
    })
    итог = модуль.проверить("x.example")
    assert итог["перенаправляет"] is False
    assert итог["acme_жив"] is False


def test_страница_без_canonical_не_считается_смягчённой(модуль, monkeypatch):
    _подменить(модуль, monkeypatch, {
        ("x.example", "/"): ("200", "", "<html><head></head></html>"),
        ("x.example", модуль.ПУТЬ_ACME): ("404", "", ""),
    })
    итог = модуль.проверить("x.example")
    assert итог["canonical_по_http"] == ""
    assert итог["canonical_на_https"] is False
