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


def _acceptance_slot() -> dict:
    """Слот адресов. Читается, а не повторяется: два перечня разошлись бы."""
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "config" / "live-acceptance.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("products", {})
    except json.JSONDecodeError:
        return {}


def live_urls() -> dict | None:
    """Адреса действующих витрин. Пункт исчезает, когда все адреса переданы.

    Запрос, продолжающий просить уже полученное, обесценивает весь список:
    его перестают читать. Поэтому здесь называются только те продукты, у
    которых адреса действительно нет.
    """
    slot = _acceptance_slot()
    ждут = [имя for имя, куда in PRODUCTS
            if not (slot.get(имя) or {}).get("base_url")]
    if not ждут:
        return None
    места = "; ".join(f"{имя} — {куда}" for имя, куда in PRODUCTS if имя in ждут)
    перечень = ", ".join(ждут)
    return _item(
        "owner.live_urls",
        ("Визуальная и функциональная приёмка выполняется на действующих сайтах. "
         "Локальные сборки и витрины на выдуманных данных приёмкой продукта не "
         f"являются, поэтому без адресов приёмка не начинается. Ждут адреса: "
         f"{перечень}. Для yummy нужен не адрес витрины, а привязка витрин к "
         "доменам yummyani.me, yummyani.site, yummyani.org, yummyani.biz."),
        ("перечень адресов: продукт → адрес, по одному на каждую витрину; "
         "для yummy — какая витрина (site, org, biz) живёт на каком домене"),
        "basis-video → https://<домен>/",
        места,
        "PRODUCT_LIVE_ACCEPTANCE → BLOCKED_OWNER_URLS",
    )


def address_states() -> list[dict]:
    """Адреса, которые переданы, но приёмку по ним провести нельзя.

    Это не запрос недостающего входа, а названное состояние: имя не
    разрешается, TLS не обслуживается, адрес отдаёт не эту витрину. Владельцу
    оно нужно ровно так же — но как факт о его инфраструктуре, а не как
    претензия к витрине.
    """
    import json
    from pathlib import Path

    evidence = (Path(__file__).resolve().parents[2] / "artifacts" / "evidence" /
                "products" / "live-identity.json")
    if not evidence.is_file():
        return []
    try:
        измерено = json.loads(evidence.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    out = []
    for имя, _ in PRODUCTS:
        primary = (измерено.get(имя) or {}).get("primary") or {}
        verdict = primary.get("verdict")
        if verdict in (None, "SERVES_OUR_STOREFRONT"):
            continue
        out.append(_item(
            f"owner.address_state.{имя}",
            f"{primary.get('url')}: {primary.get('note', verdict)}. "
            "Это состояние адреса, а не отказ витрины: готовность продукта им "
            "не измеряется и от него не меняется.",
            "исправление на стороне владельца: запись DNS, выкладка TLS или "
            "публикация витрины по этому адресу",
            "запись A/AAAA либо сертификат и обслуживание 443",
            "инфраструктура владельца; измерено scripts/live_identity_probe.py",
            f"PRODUCT_LIVE_ACCEPTANCE → {verdict}"))
    return out


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
    ждут = live_urls()
    return [*([ждут] if ждут else []), *address_states(), *yummy_items()]


__all__ = ["PRODUCTS", "address_states", "collect", "live_urls", "yummy_items"]
