"""Чего полоса шаблонов ждёт от владельца — в форме единого запроса.

Зачем отдельно
--------------

`factory/input_request.py` собирает недостающее обходом пакетов сайтов. Для
трёх витрин это работает, а для Yummy — нет: пакета направления в фабрике не
существует, приложение живёт в отдельном репозитории, и обходом оно не
находится ничем. Его требования описаны в `factory/yummy/adapter_contract.py`,
и без сведения в один список владелец читал бы два документа вместо одного.

Второе, чего обход не находит по устройству: боевые адреса витрин. Живая
приёмка всех четырёх продуктов стоит сейчас именно на них, и это единственное,
чего ждут от владельца. Пункт отсутствовал в документе, который существует
ради полноты.

Чего здесь нет
--------------

Ни одного адреса, домена или ключа. Пустое поле — не разрешение подставить
значение по умолчанию: адреса приходят от владельца и до тех пор живая приёмка
помечается `BLOCKED_OWNER_URLS` — ожиданием входа, а не провалом продукта.
"""

from __future__ import annotations

#: Продукты полосы и место, куда ложится боевой адрес каждого.
PRODUCTS = (
    ("zona-cinema", "sites/zona-cinema-preview/package.yaml → domain, canonical_url"),
    ("animedia-portal", "sites/animedia-preview/package.yaml → domain, canonical_url"),
    ("basis-video", "sites/pilot-local/package.yaml → domain, canonical_url"),
    ("yummy", "inventory/portfolios.yaml → привязка SITE_PROFILE к домену"),
)


def _item(field: str, why: str, fmt: str, example: str, where: str, blocks: str) -> dict:
    return {"field": field, "why": why, "format": fmt, "example_without_secret": example,
            "where_to_put": where, "blocks_stage": blocks}


def live_urls() -> dict:
    """Адреса действующих витрин для приёмки. Один пункт на четыре продукта."""
    места = "; ".join(f"{имя} — {куда}" for имя, куда in PRODUCTS)
    return _item(
        "owner.live_urls",
        ("Визуальная и функциональная приёмка выполняется на действующих сайтах. "
         "Локальные сборки и витрины на выдуманных данных приёмкой продукта не "
         "являются, поэтому без адресов приёмка не начинается. Продукты: "
         "zona-cinema, animedia-portal, basis-video, yummy."),
        ("перечень адресов: продукт → адрес, по одному на каждую витрину; "
         "для yummy — какая витрина (site, org, biz) живёт на каком из доменов "
         "yummyani.me, yummyani.site, yummyani.org, yummyani.biz"),
        "zona-cinema → https://<домен>/, basis-video → https://<домен>/",
        места,
        "PRODUCT_LIVE_ACCEPTANCE → BLOCKED_OWNER_URLS",
    )


def yummy_items() -> list[dict]:
    """Требования подключения Yummy в форме общего запроса.

    Содержание читается из контракта, а не повторяется здесь: два перечня
    одного и того же расходятся молча, и разошёлся бы именно тот, что реже
    открывают.
    """
    from factory.yummy import adapter_contract

    items = []
    for запись in adapter_contract.missing_inputs():
        items.append(_item(
            запись["field"], запись["why"], запись["format"],
            запись["example_without_secret"], запись["where_to_put"],
            # В контракте это поле называется `blocks` и говорит о том же.
            f"{запись['blocks']} → BLOCKED_INPUT"))
    return items


def collect() -> list[dict]:
    return [live_urls(), *yummy_items()]


__all__ = ["PRODUCTS", "collect", "live_urls", "yummy_items"]
