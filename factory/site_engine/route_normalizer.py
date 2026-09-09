"""Приведение адреса страницы к ключу маршрута.

Ключ нужен затем, чтобы один и тот же адрес, записанный по-разному, давал одно
и то же. `HTTPS://Example.TEST/title/x/`, `https://example.test/title/x` и
`https://example.test//title/x/?utm_source=mail` — это один адрес, и считать их
тремя значит трижды не найти одну запись.

Чего приведение делать не должно: выбрасывать значимую часть адреса ради того,
чтобы совпало больше. Убрав номер сезона, мы повысим долю совпадений и начнём
приписывать сезону сведения о произведении целиком. Доля вырастет, правда
пропадёт.

Модуль ничего не знает про SEO и ни к кому не ходит: адрес приводится
вычислением, а не запросом.
"""

from __future__ import annotations

import dataclasses
import enum
import re
import unicodedata
from typing import Any
from urllib.parse import unquote, urlsplit

#: Параметры запроса, которые к содержимому страницы отношения не имеют.
#: Перечень закрыт: параметр, которого здесь нет, сохраняется — выбрасывать
#: незнакомое значит терять страницы, различающиеся именно им.
TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "yclid", "fbclid", "_openstat", "from", "ref",
})

#: Схемы, которые считаются одним и тем же адресом.
EQUIVALENT_SCHEMES = frozenset({"http", "https"})


class NormalizeState(str, enum.Enum):
    OK = "OK"
    #: Адрес не разобрался: не адрес вовсе либо неизвестная схема.
    MALFORMED = "MALFORMED"
    #: Адрес не принадлежит ни одному управляемому профилю.
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


@dataclasses.dataclass(frozen=True, slots=True)
class NormalizedRoute:
    """Приведённый адрес вместе с тем, что из него вышло."""

    state: NormalizeState
    site_id: str = ""
    host: str = ""
    #: Ключ маршрута: путь без хвостов, с сохранёнными значимыми частями.
    route_key: str = ""
    canonical_url: str = ""
    route_kind: str = ""
    #: Ключ произведения-родителя для вложенных адресов. Пусто, если адрес и
    #: есть адрес произведения.
    parent_key: str = ""
    dropped_params: tuple[str, ...] = ()
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"state": self.state.value, "siteId": self.site_id,
                "host": self.host, "routeKey": self.route_key,
                "canonicalUrl": self.canonical_url,
                "routeKind": self.route_kind, "parentKey": self.parent_key,
                "droppedParams": list(self.dropped_params),
                "reason": self.reason}


def _host(raw: str) -> str:
    """Имя узла в нижнем регистре и в punycode.

    Регистр имени узла незначим по стандарту, а IDN пишут и так и так:
    `Кино.рф` и `xn--80akjq.xn--p1ai` — одно имя, и различать их значит не
    находить половину адресов.
    """
    имя = (raw or "").strip().lower().rstrip(".")
    if not имя:
        return ""
    try:
        return имя.encode("idna").decode("ascii")
    except (UnicodeError, UnicodeDecodeError):
        return имя


def _path(raw: str) -> str:
    """Путь без повторных косых, с раскрытым процентным кодированием."""
    развёрнут = unquote(raw or "")
    сжат = re.sub(r"/{2,}", "/", развёрнут)
    # Приведение Unicode: одна и та же буква, записанная составным и
    # предсоставленным способом, — одна буква.
    сжат = unicodedata.normalize("NFC", сжат)
    if not сжат.startswith("/"):
        сжат = "/" + сжат
    return сжат.rstrip("/") or "/"


def normalize(url: str, *, profiles: dict[str, str],
              path_rules: dict[str, Any] | None = None) -> NormalizedRoute:
    """Привести адрес к ключу маршрута.

    `profiles` — отображение имени узла на витрину, `path_rules` — объявленная
    профилем структура адресов. Оба приходят настройкой, а не зашиты: сорок
    третья витрина добавляется строкой в объявлении, а не правкой этого
    модуля, и различия витрин живут в профилях, а не здесь.
    """
    try:
        части = urlsplit((url or "").strip())
    except ValueError:
        return NormalizedRoute(NormalizeState.MALFORMED,
                               reason=f"адрес не разбирается: {url!r}")
    if части.scheme and части.scheme not in EQUIVALENT_SCHEMES:
        return NormalizedRoute(
            NormalizeState.MALFORMED,
            reason=f"схема {части.scheme!r} не считается адресом страницы")

    узел = _host(части.hostname or "")
    if not узел:
        return NormalizedRoute(NormalizeState.MALFORMED,
                               reason="адрес без имени узла")
    # Ключи объявления приводятся тем же правилом, что и имя узла адреса:
    # иначе международный домен, записанный в объявлении кириллицей, никогда
    # не совпадёт с адресом, приведённым к punycode.
    приведённые = {_host(имя): витр for имя, витр in profiles.items()}
    витрина = приведённые.get(узел, "")
    if not витрина:
        return NormalizedRoute(
            NormalizeState.OUT_OF_SCOPE, host=узел,
            reason=f"узел {узел!r} не принадлежит ни одному управляемому профилю")

    путь = _path(части.path)
    # Отброшенные параметры перечисляются: «мы их выбросили» и «их не было» —
    # разные положения, и второе не должно выглядеть как первое.
    выброшено: list[str] = []
    if части.query:
        for пара in части.query.split("&"):
            имя = пара.split("=", 1)[0]
            if имя in TRACKING_PARAMS:
                выброшено.append(имя)

    правила = path_rules or {}
    вид, родитель = _kind_of(путь, правила)
    канонический = f"https://{узел}{путь}/" if путь != "/" else f"https://{узел}/"
    return NormalizedRoute(
        NormalizeState.OK, site_id=витрина, host=узел, route_key=путь,
        canonical_url=канонический, route_kind=вид, parent_key=родитель,
        dropped_params=tuple(sorted(выброшено)))


def _kind_of(путь: str, правила: dict[str, Any]) -> tuple[str, str]:
    """Вид адреса и адрес произведения-родителя.

    Вложенный адрес принадлежит тому же произведению, что и родитель, — это
    структура адресов витрины, объявленная профилем, а не догадка о ней.
    """
    части = [c for c in путь.split("/") if c]
    if not части:
        return "root", ""
    # Префиксы адресов объявляет профиль витрины. Умолчания здесь нет и быть
    # не может: догадка о том, каким префиксом витрина называет произведения,
    # — это знание о конкретной витрине, а ядро таким знанием не располагает.
    # Без объявления вид адреса неизвестен, и это честнее выдуманного.
    префиксы = tuple(правила.get("titlePrefixes") or ())
    if not префиксы:
        return "unknown-without-profile", ""
    if части[0] not in префиксы:
        return "other", ""
    if len(части) == 1:
        return "listing", ""
    родитель = f"/{части[0]}/{части[1]}"
    if len(части) == 2:
        return "title", ""
    if части[2:3] == ["season"] and len(части) == 4:
        return "season", родитель
    if части[2:3] == ["season"] and части[4:5] == ["episode"] and len(части) == 6:
        return "episode", родитель
    return "other", родитель
