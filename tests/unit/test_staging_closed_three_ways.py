"""Закрытость staging измеряется тремя путями, а не наличием одного заголовка.

Повод измерен 2026-10-17: публичный `X-Robots-Tag` отдают ячейки и НЕ отдаёт
цепочка Yummy. Проверка, требовавшая заголовок безусловно, измеряла наличие
заголовка, а не закрытость индексации, и на такой цепочке не могла пройти
никогда.

Проверки опровергаемы: на закрытом состоянии находки нет, на открытом — есть,
и каждый из трёх способов закрытия проверяется отдельно.
"""
from __future__ import annotations

import factory.verify as verify


def _подменить(monkeypatch, *, заголовки: dict, тело: str, robots: str,
               код: int = 401):
    """Подменяет один сетевой вызов проверки. Возвращает журнал обращений."""
    журнал: list[str] = []

    def _get(base_url, path, auth=""):  # noqa: ANN001 — подпись как у исходной
        журнал.append(path)
        if path == "/robots.txt":
            return 200, {}, robots
        if path == "/" and auth == "":
            # Анонимный запрос: закрытость паролем проверяется отдельно и
            # должна остаться удовлетворённой, иначе появится вторая находка.
            return код, {}, ""
        if path == "/":
            return 200, заголовки, тело
        return 404, {}, ""

    monkeypatch.setattr(verify, "_get", _get)
    return журнал


ОБЯЗАТЕЛЬНЫЕ = {
    "Strict-Transport-Security": "max-age=31536000",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'self'",
}


def _находки_staging(отчёт) -> list[str]:
    return [н.message for н in отчёт.findings if н.check == "staging"]


def test_заголовок_закрывает(monkeypatch, tmp_path):
    заголовки = {**ОБЯЗАТЕЛЬНЫЕ, "X-Robots-Tag": "noindex, nofollow"}
    _подменить(monkeypatch, заголовки=заголовки, тело="<html></html>",
               robots="User-agent: *\nAllow: /\n")
    отчёт = verify.security_smoke("https://stage.example", tmp_path,
                                  auth="u:p", environment="staging")
    assert _находки_staging(отчёт) == []


def test_мета_закрывает_без_заголовка(monkeypatch, tmp_path):
    """Цепочка Yummy: заголовка нет, мета есть — это закрытое состояние."""
    тело = '<html><head><meta name="robots" content="noindex, follow">' \
           "</head></html>"
    _подменить(monkeypatch, заголовки=dict(ОБЯЗАТЕЛЬНЫЕ), тело=тело,
               robots="User-agent: *\nAllow: /\n")
    отчёт = verify.security_smoke("https://stage.example", tmp_path,
                                  auth="u:p", environment="staging")
    assert _находки_staging(отчёт) == []


def test_robots_закрывает_без_заголовка_и_меты(monkeypatch, tmp_path):
    _подменить(monkeypatch, заголовки=dict(ОБЯЗАТЕЛЬНЫЕ), тело="<html></html>",
               robots="User-agent: *\nDisallow: /\n")
    отчёт = verify.security_smoke("https://stage.example", tmp_path,
                                  auth="u:p", environment="staging")
    assert _находки_staging(отчёт) == []


def test_открытое_состояние_даёт_находку(monkeypatch, tmp_path):
    """Ни заголовка, ни меты, ни запрета обхода — находка обязана быть."""
    _подменить(monkeypatch, заголовки=dict(ОБЯЗАТЕЛЬНЫЕ), тело="<html></html>",
               robots="User-agent: *\nDisallow: /poster/\n")
    отчёт = verify.security_smoke("https://stage.example", tmp_path,
                                  auth="u:p", environment="staging")
    находки = _находки_staging(отчёт)
    assert len(находки) == 1
    assert "ни одним из трёх способов" in находки[0]


def test_disallow_подкаталога_не_считается_закрытием(monkeypatch, tmp_path):
    """`Disallow: /poster/` не закрывает сайт — это тот же класс ошибки,
    что подстрочный поиск «Disallow: /», который я правила в четырёх местах."""
    _подменить(monkeypatch, заголовки=dict(ОБЯЗАТЕЛЬНЫЕ), тело="<html></html>",
               robots="User-agent: *\nDisallow: /poster/\nDisallow: /api/\n")
    отчёт = verify.security_smoke("https://stage.example", tmp_path,
                                  auth="u:p", environment="staging")
    assert len(_находки_staging(отчёт)) == 1
