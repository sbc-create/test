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
    api_status=PRESENT,
    endpoint="ACME (через certbot, прямые вызовы из контура не выполняются)",
    auth="ACME account на хосте, контуру не передаётся",
    operations=("observe", "verify_chain", "verify_expiry"),
    idempotency="продление идемпотентно по сроку действия",
    quotas="лимиты Let's Encrypt на выпуск; в R1 выпуск не выполняется",
    consistency="немедленная после успешного выпуска",
    paid_operations="нет",
    sandbox="staging-контур ACME существует, в R1 не используется",
    egress_hosts=(),
    credential_ref="host:certbot",
    credential_present=True,
    evidence=("живой сертификат yummyani.site: issuer Let's Encrypt YR2, "
              "notBefore Aug 24 2026, notAfter Nov 22 2026",
              "/etc/letsencrypt/renewal/: 5+ конфигураций продления",
              "certbot.timer активен"),
    notes="Контур наблюдает TLS и проверяет цепочку и срок. Выпуск остаётся за "
          "certbot: второй ACME-клиент рядом означал бы гонку за один аккаунт.")

#: Яндекс Метрика. Контракт заморожен по официальной документации, хост в
#: allowlist, endpoint отвечает. Не хватает только credential.
METRIKA = Возможности(
    provider_type="analytics",
    provider="Яндекс Метрика",
    api_status=PRESENT,
    endpoint="https://api-metrika.yandex.net",
    api_version="management/v1, stat/v1",
    doc_source="knowledge/YANDEX_ANALYTICS_CONTRACT.yaml (заморожен 2026-08-23 "
               "по yandex.ru/dev/metrika)",
    auth="заголовок Authorization: OAuth {token}",
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
    credential_ref="file:/etc/site-factory/secrets/yandex_oauth_token",
    credential_present=False,
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
    evidence=("inventory/network-allowlist.yaml: записи нет",
              "config/data-sources.json: источника нет",
              "knowledge/: замороженного контракта нет"),
    notes="Ни одной проверяемой опоры. Любое утверждение о методах, квотах и "
          "стоимости было бы выдумкой, а не неполнотой.")

МАТРИЦА = (DNS, TLS, METRIKA, TOPVISOR)


def матрица() -> list[dict[str, Any]]:
    return [в.в_словарь() for в in МАТРИЦА]


def проверяемые() -> list[str]:
    """Типы провайдеров, по которым возможна живая работа."""
    return [в.provider_type for в in МАТРИЦА
            if в.api_status == PRESENT and в.credential_present]


if __name__ == "__main__":
    print(json.dumps({"matrix": матрица(), "usable_live": проверяемые()},
                     ensure_ascii=False, indent=1))
