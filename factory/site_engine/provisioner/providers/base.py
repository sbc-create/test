"""Контракт провайдер-адаптера и правила безопасности вызовов.

Каждый адаптер отвечает за ОДИН тип внешнего ресурса и обязан уметь пять
вещей: посмотреть, спланировать, применить, сверить и вывести из обращения.
Порядок не случаен: `observe` идёт до `plan`, а `plan` — до `apply`, потому
что единственная надёжная защита от второго объекта — искать по естественному
ключу ДО создания.

Здесь же живут запреты, которые не должен переизобретать каждый адаптер:
какие типы DNS-записей допустимы автоматически, какие адреса вообще нельзя
вызывать и какое доказательство владения требуется, чтобы принять чужой
объект под управление.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

# --- безопасность вызовов ----------------------------------------------------

#: Записи, которые контур вправе менять сам. Всё остальное — отдельное ручное
#: разрешение: ошибка в NS или MX уводит домен или почту целиком, и откат по
#: журналу здесь не помогает, потому что ломается доставка, а не страница.
РАЗРЕШЁННЫЕ_ЗАПИСИ = frozenset({"A", "AAAA", "CNAME", "TXT"})
ЗАЩИЩЁННЫЕ_ЗАПИСИ = frozenset({"NS", "MX", "SOA", "DS", "DNSKEY", "CAA"})
#: TXT разрешён не любой: SPF, DKIM и DMARC живут в TXT, и правка «просто
#: текстовой записи» ломает почту так же надёжно, как правка MX.
ЗАЩИЩЁННЫЕ_TXT = re.compile(r"^(_dmarc|_domainkey|.*\._domainkey|@?)$", re.I)
ACME_ИМЯ = "_acme-challenge"
#: Символы, через которые в значение пытаются протащить команду оболочки.
ОПАСНЫЕ_СИМВОЛЫ = ";|&`$\n\r"


class ProviderError(RuntimeError):
    def __init__(self, code: str, detail: str, *, retryable: bool = False):
        super().__init__(detail)
        self.error_code, self.detail, self.retryable = code, detail, retryable


def проверить_запись(тип: str, имя: str, значение: str) -> None:
    """Допустима ли автоматическая правка этой DNS-записи."""
    т = (тип or "").upper()
    if т in ЗАЩИЩЁННЫЕ_ЗАПИСИ:
        raise ProviderError(
            "RECORD_TYPE_PROTECTED",
            f"запись {т} не изменяется автоматически: перенос делегирования "
            f"или почты требует отдельного разрешения")
    if т not in РАЗРЕШЁННЫЕ_ЗАПИСИ:
        raise ProviderError("RECORD_TYPE_UNSUPPORTED",
                            f"тип записи {т} не объявлен разрешённым")
    if т == "TXT":
        короткое = (имя or "").split(".")[0]
        if короткое != ACME_ИМЯ and ЗАЩИЩЁННЫЕ_TXT.match(имя or ""):
            raise ProviderError(
                "TXT_PROTECTED",
                f"TXT {имя!r} относится к почтовой политике (SPF/DKIM/DMARC) "
                f"и автоматически не меняется")
    if any(с in (значение or "") for с in ОПАСНЫЕ_СИМВОЛЫ):
        raise ProviderError("VALUE_REJECTED",
                            "значение записи содержит управляющие символы")


def проверить_адрес(url: str, разрешённые_хосты: frozenset[str]) -> str:
    """Можно ли вообще обращаться по этому адресу.

    Три отказа сразу: чужая схема, хост вне allowlist и адрес, который
    резолвится во внутреннюю сеть. Последнее — защита от подмены DNS уже
    после проверки имени: адрес проверяется по фактическому разрешению, а не
    по тому, как он выглядит.
    """
    м = re.match(r"^(https?)://([^/:]+)(?::(\d+))?(/.*)?$", url or "")
    if not м:
        raise ProviderError("URL_REJECTED", "адрес не разобран или схема не http(s)")
    схема, хост = м.group(1), м.group(2).lower()
    if схема != "https":
        raise ProviderError("URL_INSECURE", "допускается только https")
    if хост not in разрешённые_хосты:
        raise ProviderError(
            "EGRESS_DENIED",
            f"хост {хост} отсутствует в allowlist; расширять список по "
            f"инициативе исполнителя запрещено")
    try:
        сведения = socket.getaddrinfo(хост, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as ош:
        raise ProviderError("DNS_RESOLVE_FAILED", f"{хост}: {ош}", retryable=True)
    for запись in сведения:
        адрес = ipaddress.ip_address(запись[4][0])
        if (адрес.is_private or адрес.is_loopback or адрес.is_link_local
                or адрес.is_reserved or адрес.is_multicast):
            raise ProviderError(
                "SSRF_BLOCKED",
                f"{хост} разрешается во внутренний адрес {адрес}: запрос не "
                f"выполняется")
    return хост


# --- контракт адаптера -------------------------------------------------------

@dataclass(frozen=True)
class Наблюдение:
    существует: bool
    external_id: str | None = None
    fingerprint: str | None = None
    подробности: dict[str, Any] | None = None
    владение_подтверждено: bool = False


@runtime_checkable
class ProviderAdapter(Protocol):
    provider_type: str
    resource_kind: str
    #: Может ли адаптер писать в живого провайдера. В R1 — нигде.
    live_writes: bool

    def observe(self, *, site_id: str, intent: Any) -> Наблюдение: ...

    def plan(self, *, site_id: str, intent: Any,
             observed: Наблюдение) -> dict[str, Any]: ...

    def apply(self, *, site_id: str, plan: dict[str, Any],
              idempotency_key: str) -> dict[str, Any]: ...

    def reconcile(self, *, site_id: str, external_id: str) -> Наблюдение: ...

    def retire(self, *, site_id: str, external_id: str) -> dict[str, Any]: ...
