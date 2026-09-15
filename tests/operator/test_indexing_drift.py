"""Read-only проверка дрейфа индексации: 1 OPEN + 8 CLOSED."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from seo_operator.indexing_drift import (
    CLOSED,
    MIXED,
    OPEN,
    UNMEASURED,
    Response,
    check_portfolio,
    compare_methods,
    inspect_domain,
)

КОРЕНЬ = Path(__file__).resolve().parents[2]
ПОРТФЕЛЬ = КОРЕНЬ / "config" / "portfolio.json"

ОТКРЫТ = "yummyani.site"
ЗАКРЫТЫЕ = (
    "yummyani.org", "yummyani.biz", "lordfilm47.space", "lordserial33.biz",
    "1lordserials1.online", "zonafilm.space", "animedia.icu", "animedia.space",
)

ЗАГОЛОВКИ_ОТКРЫТО = "HTTP/2 200\r\ncontent-type: text/html\r\n"
ЗАГОЛОВКИ_ЗАКРЫТО = ЗАГОЛОВКИ_ОТКРЫТО + "x-robots-tag: noindex, nofollow\r\n"
ROBOTS_ОТКРЫТ = "User-agent: *\nAllow: /\nDisallow: /dev/\n"
ROBOTS_ЗАКРЫТ = "User-agent: *\nDisallow: /\n"


def тело(domain: str, *, noindex: bool, canonical: str | None = None) -> str:
    мета = "noindex, nofollow" if noindex else "index, follow"
    ссылка = canonical if canonical is not None else f"https://{domain}/"
    return (
        f'<html><head><meta name="robots" content="{мета}"/>'
        f'<link rel="canonical" href="{ссылка}"/></head><body>текст</body></html>'
    )


def загрузчик(состояния: dict[str, str], **особые):
    """Загрузчик, отвечающий по заданной карте «домен -> open|closed»."""

    def получить(url: str) -> Response:
        домен = url.split("//", 1)[1].split("/", 1)[0]
        если_особое = особые.get(домен)
        if если_особое == "timeout":
            return Response(status=None, headers="", body="", error="таймаут")
        if если_особое == "network":
            return Response(status=None, headers="", body="", error="сетевая ошибка")
        if если_особое == "empty":
            return Response(status=200, headers=ЗАГОЛОВКИ_ОТКРЫТО, body="")
        открыт = состояния.get(домен, "closed") == "open"
        if url.endswith("/robots.txt"):
            текст = ROBOTS_ОТКРЫТ if открыт else ROBOTS_ЗАКРЫТ
            return Response(status=200, headers="HTTP/2 200\r\n", body=текст)
        заголовки = ЗАГОЛОВКИ_ОТКРЫТО if открыт else ЗАГОЛОВКИ_ЗАКРЫТО
        return Response(
            status=200, headers=заголовки,
            body=тело(домен, noindex=not открыт),
        )

    return получить


def портфель() -> list[dict]:
    return json.loads(ПОРТФЕЛЬ.read_text(encoding="utf-8"))["sites"]


# --- штатная матрица ----------------------------------------------------------

def test_реестр_объявляет_ровно_один_открытый_домен() -> None:
    сайты = портфель()
    открытые = [s for s in сайты if s.get("indexing_expected") == "open"]
    assert [s["site_id"] for s in открытые] == ["yummyani-site"]
    assert len(сайты) - len(открытые) == 8


def test_штатная_матрица_не_даёт_дрейфа() -> None:
    состояния = {ОТКРЫТ: "open", **{d: "closed" for d in ЗАКРЫТЫЕ}}
    отчёт = check_portfolio(портфель(), fetcher=загрузчик(состояния))
    assert отчёт.ok, [(d.domain, d.reasons) for d in отчёт.drift]
    assert отчёт.summary() == {
        "total": 9, "open": 1, "closed": 8, "mixed": 0, "unmeasured": 0, "drift": [],
    }


def test_повторный_запуск_даёт_тот_же_результат() -> None:
    """Проверка идемпотентна: она ничего не меняет и не накапливает состояние."""
    состояния = {ОТКРЫТ: "open", **{d: "closed" for d in ЗАКРЫТЫЕ}}
    первый = check_portfolio(портфель(), fetcher=загрузчик(состояния)).summary()
    второй = check_portfolio(портфель(), fetcher=загрузчик(состояния)).summary()
    assert первый == второй


# --- дрейф в обе стороны ------------------------------------------------------

def test_повторное_закрытие_yummyani_site_обнаруживается() -> None:
    """Главный риск: штатный deploy возвращает версию, закрывающую витрину."""
    состояния = {ОТКРЫТ: "closed", **{d: "closed" for d in ЗАКРЫТЫЕ}}
    отчёт = check_portfolio(портфель(), fetcher=загрузчик(состояния))
    assert not отчёт.ok
    беда = отчёт.drift[0]
    assert беда.domain == ОТКРЫТ
    assert беда.expected == OPEN and беда.actual == CLOSED
    assert "EXPECTED_OPEN_ACTUAL_CLOSED" in беда.reasons


def test_случайное_открытие_другого_домена_обнаруживается() -> None:
    состояния = {ОТКРЫТ: "open", **{d: "closed" for d in ЗАКРЫТЫЕ}}
    состояния["yummyani.org"] = "open"
    отчёт = check_portfolio(портфель(), fetcher=загрузчик(состояния))
    assert [d.domain for d in отчёт.drift] == ["yummyani.org"]
    assert "EXPECTED_CLOSED_ACTUAL_OPEN" in отчёт.drift[0].reasons


def test_конфликт_слоёв_обнаруживается() -> None:
    """Слои спорят между собой: часть запретов снята, часть держит."""

    def получить(url: str) -> Response:
        домен = url.split("//", 1)[1].split("/", 1)[0]
        if url.endswith("/robots.txt"):
            return Response(200, "HTTP/2 200\r\n", ROBOTS_ЗАКРЫТ)
        # мета открыт, заголовок закрыт — ровно состояние 2026-09-15T17:17Z
        return Response(200, ЗАГОЛОВКИ_ЗАКРЫТО, тело(домен, noindex=False))

    отчёт = inspect_domain("yummyani-site", ОТКРЫТ, OPEN, fetcher=получить)
    assert отчёт.actual == MIXED
    assert any(r.startswith("MIXED_LAYERS") for r in отчёт.reasons)
    assert "meta_robots" in отчёт.layers_open


# --- «не измерено» отличается от «нарушено» -----------------------------------

@pytest.mark.parametrize("вид", ["timeout", "network", "empty"])
def test_неполученный_ответ_не_объявляется_нарушением(вид: str) -> None:
    """Таймаут, сетевая ошибка и пустой ответ — не открытие и не закрытие.

    Считать их нарушением значит поднимать ложную тревогу; считать
    подтверждением — пропускать настоящее.
    """
    состояния = {ОТКРЫТ: "open", **{d: "closed" for d in ЗАКРЫТЫЕ}}
    отчёт = check_portfolio(
        портфель(), fetcher=загрузчик(состояния, **{"yummyani.org": вид})
    )
    беда = next(d for d in отчёт.domains if d.domain == "yummyani.org")
    assert беда.actual == UNMEASURED
    assert any(r.startswith("NOT_MEASURED") for r in беда.reasons)
    assert беда in отчёт.unmeasured


def test_неизмеренный_домен_всё_равно_считается_расхождением() -> None:
    """Молчание не проходит как «всё в порядке»: состояние надо подтвердить."""
    состояния = {ОТКРЫТ: "open", **{d: "closed" for d in ЗАКРЫТЫЕ}}
    отчёт = check_portfolio(
        портфель(), fetcher=загрузчик(состояния, **{"animedia.icu": "timeout"})
    )
    assert not отчёт.ok
    assert "animedia.icu" in отчёт.summary()["drift"]


# --- свойства открытого домена ------------------------------------------------

def test_открытый_домен_с_чужим_canonical_это_находка() -> None:
    def получить(url: str) -> Response:
        if url.endswith("/robots.txt"):
            return Response(200, "HTTP/2 200\r\n", ROBOTS_ОТКРЫТ)
        return Response(200, ЗАГОЛОВКИ_ОТКРЫТО,
                        тело(ОТКРЫТ, noindex=False, canonical="https://example.invalid/"))

    о = inspect_domain("yummyani-site", ОТКРЫТ, OPEN, fetcher=получить)
    assert о.actual == OPEN
    assert any(r.startswith("CROSS_DOMAIN_CANONICAL") for r in о.reasons)


def test_открытый_домен_с_кодом_не_200_это_находка() -> None:
    def получить(url: str) -> Response:
        if url.endswith("/robots.txt"):
            return Response(200, "HTTP/2 200\r\n", ROBOTS_ОТКРЫТ)
        return Response(503, "HTTP/2 503\r\n", тело(ОТКРЫТ, noindex=False))

    о = inspect_domain("yummyani-site", ОТКРЫТ, OPEN, fetcher=получить)
    assert "OPEN_WITH_STATUS_503" in о.reasons


def test_закрытый_домен_не_проверяется_на_canonical() -> None:
    """У закрытой витрины canonical не влияет ни на что: её не индексируют."""
    def получить(url: str) -> Response:
        if url.endswith("/robots.txt"):
            return Response(200, "HTTP/2 200\r\n", ROBOTS_ЗАКРЫТ)
        return Response(200, ЗАГОЛОВКИ_ЗАКРЫТО,
                        тело("yummyani.org", noindex=True, canonical="https://example.invalid/"))

    о = inspect_domain("yummyani-org", "yummyani.org", CLOSED, fetcher=получить)
    assert о.actual == CLOSED
    assert о.reasons == ()


# --- HEAD против GET ----------------------------------------------------------

def test_расхождение_head_и_get_называется_прямо() -> None:
    """Посредник добавляет заголовок только на GET — HEAD однажды уже обманул."""
    def get(url: str) -> Response:
        return Response(200, ЗАГОЛОВКИ_ЗАКРЫТО, тело(ОТКРЫТ, noindex=True))

    def head(url: str) -> Response:
        return Response(200, ЗАГОЛОВКИ_ОТКРЫТО, "")

    сообщение = compare_methods(ОТКРЫТ, get=get, head=head)
    assert сообщение is not None
    assert "GET и HEAD расходятся" in сообщение
    assert "доверять следует GET" in сообщение


def test_совпадение_head_и_get_молчит() -> None:
    def оба(url: str) -> Response:
        return Response(200, ЗАГОЛОВКИ_ЗАКРЫТО, тело(ОТКРЫТ, noindex=True))

    assert compare_methods(ОТКРЫТ, get=оба, head=оба) is None


# --- модуль не умеет менять состояние -----------------------------------------

def test_модуль_не_содержит_операций_записи() -> None:
    """Read-only не на словах: в модуле нет ни записи, ни запуска команд."""
    исходник = (КОРЕНЬ / "seo_operator" / "indexing_drift.py").read_text(encoding="utf-8")
    for опасное in ("subprocess", "open(", "Path(", "requests.post", "urlopen", "os.system"):
        assert опасное not in исходник, (
            f"проверка обязана быть read-only, найдено: {опасное}"
        )


def test_разбор_ответа_не_путает_пустые_строки_в_html_с_концом_заголовков() -> None:
    """Делить ответ надо по ПЕРВОЙ пустой строке, а не по последней.

    В HTML пустые строки встречаются, и разбиение с конца отдавало под видом
    заголовков кусок разметки: закрытые витрины Lords показывались как «слои
    разошлись». Здесь закреплено поведение самого разбора, которым пользуется
    команда.
    """
    ответ = (
        "HTTP/2 200\r\n"
        "x-robots-tag: noindex, nofollow\r\n"
        "\r\n"
        "<html>\n\n<head>\n\n"
        '<meta name="robots" content="noindex, nofollow"/>\n\n'
        '<link rel="canonical" href="https://lordfilm47.space/"/>\n\n'
        "</head></html>"
    )
    заголовки, разделитель, тело = ответ.partition("\r\n\r\n")
    assert разделитель, "разделитель заголовков и тела должен находиться"
    assert "x-robots-tag" in заголовки
    assert "<html>" in тело
    # А разбиение с конца дало бы под видом заголовков разметку:
    неверно = ответ.rsplit("\n\n", 1)
    assert "x-robots-tag" not in неверно[-1]

    def получить(url: str) -> Response:
        if url.endswith("/robots.txt"):
            return Response(200, "HTTP/2 200\r\n", ROBOTS_ЗАКРЫТ)
        return Response(200, заголовки, тело)

    о = inspect_domain("lords-01", "lordfilm47.space", CLOSED, fetcher=получить)
    assert о.actual == CLOSED, о.reasons
