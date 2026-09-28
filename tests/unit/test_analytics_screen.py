"""REQ-ANALYTICS-SCREEN: неподключённый источник виден как состояние, а не ноль.

Экран аналитики — то место, где соблазн показать ноль сильнее всего: пустая
таблица выглядит незаконченной, а ровные нули — рабочей. Разница в том, что по
нулю принимают решение: «посетителей нет» означает, что сайт не работает, а
«счётчик не подключён» — что мы не спрашивали.
"""

from __future__ import annotations

from factory.site_engine.admin import ui


def _запись(поля):
    return {"siteId": "site-1", "fields": поля}


def _поле(значение, состояние, источник="src", причина=""):
    return {"value": значение, "state": состояние, "source": источник,
            "observedAt": "2026-09-06T10:00:00Z", "reason": причина}


def _страница(записи):
    return ui.analytics(записи, flash=None, session_label="кто-то", csrf="t")


def test_неподключённый_счётчик_подписан_словами():
    html = _страница([_запись({
        "visitors": _поле(None, "NOT_CONNECTED", "collector:analytics",
                          "учётные данные не переданы"),
    })])
    assert "не подключено" in html
    assert "учётные данные не переданы" in html
    assert ">0<" not in html.replace("errors", ""), "где-то показан ноль вместо состояния"


def test_измеренное_показано_числом_с_источником():
    html = _страница([_запись({"errors4xx": _поле(214, "CONNECTED", "nginx:access.log")})])
    assert "214" in html
    assert "nginx:access.log" in html, "число без источника нельзя проверить"


def test_несвежее_измерение_помечено():
    html = _страница([_запись({
        "visits": _поле(42, "STALE", "metrika", "измерению 20 ч, порог 12 ч")})])
    assert "42" in html
    assert "устарело" in html
    assert "20 ч" in html


def test_закрытый_доступ_отличается_от_отказа():
    html = _страница([_запись({
        "indexedPages": _поле(None, "ACCESS_BLOCKED", "search-console", "доступ не выдан"),
        "seoVisibility": _поле(None, "ERROR", "search-console", "источник ответил 500"),
    })])
    assert "доступ закрыт" in html
    assert "отказ" in html
    assert "500" in html


def test_обе_таблицы_на_месте():
    html = _страница([_запись({})])
    assert "Аналитика" in html and "SEO" in html
    assert "ИКС" in html, "ИКС вместо устаревшего ТИЦ"
    assert "Core Web Vitals" in html


def test_пустой_флот_не_выглядит_ошибкой():
    html = _страница([])
    assert "Витрин нет" in html
