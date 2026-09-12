"""Матрица возможностей провайдеров.

Заполняется ТОЛЬКО проверенным. Там, где официальная документация не
заморожена, credential не выдан или обращение к хосту не разрешено
allowlist'ом, стоит UNVERIFIED — и это не пробел в работе, а измеренное
состояние. Догадка о том, что «у провайдера наверняка есть такой метод»,
здесь хуже пустоты: по ней потом строят план и удивляются отказу.

Проба разрешена только read-only и только к хостам из
`inventory/network-allowlist.yaml`. Хост, которого там нет, не проверяется
вовсе: расширять список по инициативе исполнителя запрещено.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

PRESENT = "PRESENT"
ABSENT = "ABSENT"
UNVERIFIED = "UNVERIFIED"

#: Режим адаптера. В R1 ни один адаптер не писал в живого провайдера, и
#: называть его SHADOW_READY было преувеличением: «готов» звучит как
#: «остался один шаг», а шагов не сделано ни одного.
FAKE_SHADOW_ONLY = "FAKE_SHADOW_ONLY"
LIVE = "LIVE"

#: Состояние endpoint отдельно от состояния ВОЗМОЖНОСТЕЙ. Ответ 401
#: доказывает, что адрес существует и требует авторизации, и ничего не
#: говорит о том, какие операции доступны предъявителю токена.
OBSERVED_UNAUTHENTICATED = "OBSERVED_UNAUTHENTICATED"


@dataclass(frozen=True)
class Возможности:
    provider_type: str
    provider: str
    api_status: str
    endpoint: str | None = None
    api_version: str | None = None
    doc_source: str | None = None
    auth: str | None = None
    operations: tuple[str, ...] = ()
    scopes: str = UNVERIFIED
    idempotency: str = UNVERIFIED
    quotas: str = UNVERIFIED
    consistency: str = UNVERIFIED
    paid_operations: str = UNVERIFIED
    sandbox: str = UNVERIFIED
    egress_hosts: tuple[str, ...] = ()
    credential_ref: str | None = None
    credential_present: bool = False
    #: Режим адаптера контура, а не состояние провайдера. Смешивать их —
    #: значит выдавать наличие кода за наличие интеграции.
    adapter_mode: str = FAKE_SHADOW_ONLY
    #: Наблюдаемое состояние endpoint, если оно отличается от api_status.
    endpoint_state: str | None = None
    #: Подтверждены ли операции ПОД АВТОРИЗАЦИЕЙ.
    authenticated_capability: str = UNVERIFIED
    evidence: tuple[str, ...] = ()
    notes: str = ""

    def в_словарь(self) -> dict[str, Any]:
        return asdict(self)


#: DNS. Делегирование зон наблюдается живьём и указывает на Cloudflare, но это
#: факт о ДЕЛЕГИРОВАНИИ, а не о доступе к API: в inventory/dns-zones.yaml нет
#: ни одной зоны, credential не выдан, а api.cloudflare.com отсутствует в
#: network-allowlist — значит проверить возможности нечем и пробовать нельзя.
DNS = Возможности(
    provider_type="dns",
    provider="cloudflare (по наблюдаемому делегированию)",
    api_status=UNVERIFIED,
    endpoint=None,
    doc_source=None,
    auth=UNVERIFIED,
    operations=(),
    egress_hosts=(),
    credential_ref=None,
    credential_present=False,
    adapter_mode=FAKE_SHADOW_ONLY,
    authenticated_capability=UNVERIFIED,
    evidence=("config/directions/lords.json: nameservers april/pablo.ns.cloudflare.com",
              "inventory/dns-zones.yaml: zones: [] — ни одной разрешённой зоны",
              "inventory/network-allowlist.yaml: хоста API провайдера нет"),
    notes="Делегирование наблюдаемо, доступ к API — нет. Записи DNS в R1 "
          "выполняются только на fake-провайдере.")

#: TLS. Выпуск идёт локальным certbot к Let's Encrypt; это проверено и
#: сертификатом, и наличием конфигураций продления, и активным таймером.
TLS = Возможности(
    provider_type="tls",
    provider="Let's Encrypt через локальный certbot",
    # Сертификат и таймер доказывают, что на хосте РАБОТАЕТ ACME-клиент. Про
    # API провайдера они не говорят ничего: контур к ACME не обращается, и
    # назвать это «TLS Provider API подтверждён» было подменой предмета.
    api_status=UNVERIFIED,
    endpoint=None,
    auth="ACME account принадлежит certbot на хосте и контуру не передаётся",
    operations=(),
    idempotency=UNVERIFIED,
    quotas="лимиты Let's Encrypt на выпуск; выпуск из контура не выполняется",
    consistency=UNVERIFIED,
    paid_operations="нет",
    sandbox="staging-контур ACME существует; не использовался",
    egress_hosts=(),
    credential_ref="host:certbot",
    credential_present=False,
    adapter_mode=FAKE_SHADOW_ONLY,
    authenticated_capability=UNVERIFIED,
    evidence=("живой сертификат yummyani.site: issuer Let's Encrypt YR2, "
              "notBefore Aug 24 2026, notAfter Nov 22 2026",
              "/etc/letsencrypt/renewal/: 5+ конфигураций продления",
              "certbot.timer активен",
              "обращений контура к ACME не выполнялось"),
    notes="Подтверждено НАЛИЧИЕ локального ACME-клиента, а не доступ к API "
          "провайдера. Адаптер работает только на fake-провайдере.")

#: Что именно подтверждает наблюдение за TLS: автоматизация на хосте есть,
#: доступа к API провайдера из контура нет.
TLS_АВТОМАТИЗАЦИЯ = "LOCAL_ACME_CLIENT_PRESENT"

#: Яндекс Метрика. Контракт заморожен по официальной документации, хост в
#: allowlist, endpoint отвечает. Не хватает только credential.
METRIKA = Возможности(
    provider_type="analytics",
    provider="Яндекс Метрика",
    # Endpoint наблюдался, возможности — нет. Ответ 401 доказывает адрес и
    # требование авторизации; какие операции доступны предъявителю токена,
    # без токена проверить нечем.
    api_status=UNVERIFIED,
    endpoint_state=OBSERVED_UNAUTHENTICATED,
    endpoint="https://api-metrika.yandex.net",
    api_version="management/v1, stat/v1",
    doc_source="knowledge/YANDEX_ANALYTICS_CONTRACT.yaml (заморожен 2026-08-23 "
               "по yandex.ru/dev/metrika)",
    auth="заголовок Authorization: OAuth {token}",
    # Перечень взят из замороженной документации. Это ОПИСАННЫЕ операции, а
    # не проверенные: ни одна не выполнялась под авторизацией.
    operations=("list_counters", "get_counter", "create_counter", "list_goals",
                "create_goal"),
    scopes="определяются выданным OAuth-токеном; без токена не проверены",
    idempotency="нативной idempotency-key нет; защита строится на observe/adopt "
                "по natural key до создания",
    quotas="описаны в документации; фактические лимиты аккаунта не измерены",
    consistency="счётчик доступен сразу; ДАННЫЕ появляются асинхронно",
    paid_operations="нет",
    sandbox=ABSENT,
    egress_hosts=("api-metrika.yandex.net",),
    credential_ref="file-ref:yandex_oauth_token",
    credential_present=False,
    adapter_mode=FAKE_SHADOW_ONLY,
    authenticated_capability=UNVERIFIED,
    evidence=("GET https://api-metrika.yandex.net/management/v1/counters -> 401 "
              "unauthorized (read-only проба: endpoint существует и требует "
              "авторизации)",
              "config/data-sources.json: yandex_metrika status=missing_credentials",
              "inventory/network-allowlist.yaml: ref yandex-metrika-api"),
    notes="Создание счётчика в R1 не выполняется: credential не выдан, а "
          "реальные записи запрещены заданием.")

#: Topvisor. В репозитории нет ни контракта, ни endpoint, ни credential, ни
#: записи в allowlist. Обращаться нельзя, придумывать — тем более.
TOPVISOR = Возможности(
    provider_type="seo_rank",
    provider="Topvisor",
    api_status=UNVERIFIED,
    endpoint=None,
    doc_source=None,
    auth=UNVERIFIED,
    operations=(),
    egress_hosts=(),
    credential_ref=None,
    credential_present=False,
    adapter_mode=FAKE_SHADOW_ONLY,
    authenticated_capability=UNVERIFIED,
    evidence=("inventory/network-allowlist.yaml: записи нет",
              "config/data-sources.json: источника нет",
              "knowledge/: замороженного контракта нет"),
    notes="Ни одной проверяемой опоры. Любое утверждение о методах, квотах и "
          "стоимости было бы выдумкой, а не неполнотой.")

МАТРИЦА = (DNS, TLS, METRIKA, TOPVISOR)


def матрица() -> list[dict[str, Any]]:
    return [в.в_словарь() for в in МАТРИЦА]


def живые() -> list[str]:
    """Типы провайдеров, по которым ВОЗМОЖНА живая работа.

    Требуются три вещи разом: подтверждённый API, выданный credential и
    адаптер в живом режиме. Любые две без третьей живой работы не дают.
    """
    return [в.provider_type for в in МАТРИЦА
            if в.api_status == PRESENT and в.credential_present
            and в.adapter_mode == LIVE]


def production_onboarding_готов() -> bool:
    """Готовность production onboarding. Ни один провайдер не живой."""
    return bool(живые())


if __name__ == "__main__":
    print(json.dumps({"matrix": матрица(), "usable_live": живые(),
                      "tls_automation": TLS_АВТОМАТИЗАЦИЯ,
                      "production_onboarding_ready":
                          production_onboarding_готов()},
                     ensure_ascii=False, indent=1))
