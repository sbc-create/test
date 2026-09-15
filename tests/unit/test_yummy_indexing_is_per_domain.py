"""Индексацию открывает домен, а не семейство.

Владелец 2026-09-15 разрешил индексацию **только** `yummyani.site`. Решение было
выложено поднятием `SEO_INDEXING_ENABLED` в приложении — и не вступило в силу:
перед приложением стоит этот посредник, и он независимо от приложения слал
`X-Robots-Tag: noindex, nofollow` и отдавал собственный `robots.txt` с
`Disallow: /`. Снаружи витрина оставалась закрытой, а приёмка, проверявшая порт
приложения, видела успех.

Здесь закрепляется поведение посредника: открыт ровно перечисленный домен, всё
остальное закрыто, и незаданная переменная означает «закрыто».
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ФРОНТ = КОРЕНЬ / "automation" / "host" / "yummy-frontend.py"


def _загрузить(домен: str | None):
    прежнее = os.environ.get("YUMMY_VARIANT_DOMAIN")
    if домен is None:
        os.environ.pop("YUMMY_VARIANT_DOMAIN", None)
    else:
        os.environ["YUMMY_VARIANT_DOMAIN"] = домен
    try:
        имя = f"yf_{(домен or 'unset').replace('.', '_')}"
        загрузчик = importlib.machinery.SourceFileLoader(имя, str(ФРОНТ))
        модуль = importlib.util.module_from_spec(
            importlib.util.spec_from_loader(имя, загрузчик)
        )
        загрузчик.exec_module(модуль)
        return модуль
    finally:
        if прежнее is None:
            os.environ.pop("YUMMY_VARIANT_DOMAIN", None)
        else:
            os.environ["YUMMY_VARIANT_DOMAIN"] = прежнее


def test_open_domain_is_named_explicitly() -> None:
    модуль = _загрузить("yummyani.site")
    assert модуль.ДОМЕНЫ_С_ОТКРЫТОЙ_ИНДЕКСАЦИЕЙ == frozenset({"yummyani.site"})


def test_owner_approved_domain_is_open() -> None:
    assert _загрузить("yummyani.site").ИНДЕКСАЦИЯ_ОТКРЫТА is True


@pytest.mark.parametrize("домен", ["yummyani.org", "yummyani.biz"])
def test_sibling_domains_stay_closed(домен: str) -> None:
    """Решение владельца названо поимённо и на соседние площадки не переносится."""
    assert _загрузить(домен).ИНДЕКСАЦИЯ_ОТКРЫТА is False


def test_unset_variable_means_closed_not_probably_the_main_domain() -> None:
    """У ВАРИАНТ_ДОМЕНА умолчание `yummyani.site`.

    Если бы решение об индексации читало его, экземпляр с незаданной переменной
    молча считался бы открытым. Ошибаться в эту сторону нельзя.
    """
    модуль = _загрузить(None)
    assert модуль.ВАРИАНТ_ДОМЕНА == "yummyani.site"
    assert модуль.ИНДЕКСАЦИЯ_ОТКРЫТА is False


def test_noindex_header_is_conditional_in_source() -> None:
    исходник = ФРОНТ.read_text(encoding="utf-8")
    assert 'if not ИНДЕКСАЦИЯ_ОТКРЫТА:\n            self.send_header("X-Robots-Tag"' in исходник, (
        "заголовок noindex обязан зависеть от домена, а не ставиться всегда"
    )


def test_robots_txt_is_not_intercepted_on_an_open_domain() -> None:
    """На открытом домене правила отдаёт приложение, а не посредник.

    Свой ответ здесь означал бы вторую версию правил, расходящуюся с первой при
    каждой правке.
    """
    исходник = ФРОНТ.read_text(encoding="utf-8")
    assert 'if путь == "/robots.txt" and not ИНДЕКСАЦИЯ_ОТКРЫТА:' in исходник
    assert исходник.count(b"Disallow: /\\n".decode()) == 1, (
        "запрещающий robots.txt должен остаться ровно в одном месте — закрытой ветке"
    )


def test_only_one_domain_is_open_at_a_time() -> None:
    открытые = _загрузить("yummyani.site").ДОМЕНЫ_С_ОТКРЫТОЙ_ИНДЕКСАЦИЕЙ
    assert len(открытые) == 1, (
        f"открыт должен быть один домен, в списке {sorted(открытые)}"
    )
    for чужой in ("lordfilm47.space", "lordserial33.biz", "1lordserials1.online",
                  "zonafilm.space", "animedia.icu", "animedia.space"):
        assert чужой not in открытые
