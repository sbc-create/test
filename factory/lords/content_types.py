"""Типы контента Lords и их фактическое состояние.

Тип объявляется в manifest, но объявление — это ещё не наличие. Между «владелец
включил тип» и «на сайте есть раздел» стоят две проверки: переданы ли учётные
данные и подтверждает ли API наличие данных этого типа. Каждая из них может
закрыть раздел, и закрывает по-разному — поэтому состояний четыре, а не два.

Правило одно и оно жёсткое: поверхности создаёт **только** состояние `enabled`.
Любое другое состояние не создаёт ни маршрута, ни пункта меню, ни URL в sitemap,
ни SEO-страницы, ни внутренней ссылки, ни фасета, ни результата поиска. Пустой
раздел, отдающий 200 с нулём материалов, — нарушение этого правила и
одновременно soft 404.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Типы контента направления. Порядок фиксирован: он задаёт порядок разделов.
CONTENT_TYPES: tuple[str, ...] = (
    "movies",
    "series",
    "animation",
    "anime",
    "dorama",
    "collections",
)

ENABLED = "enabled"
DISABLED_BY_CONFIG = "disabled_by_config"
DISABLED_BY_API = "disabled_by_api"
BLOCKED_CREDENTIALS = "blocked_credentials"

#: Тип, которого источник не отдаёт вовсе — не «в этот раз не подтвердил», а
#: «такого раздела у него нет».
#:
#: Различие не терминологическое. `DISABLED_BY_API` читается как «спросили —
#: не дал» и предлагает ждать: появятся данные, появится и раздел. Ждать при
#: этом нечего, и владелец, включивший тип в manifest, остаётся с выключенным
#: разделом и объяснением, которое валит вину на поставщика.
#:
#: Ровно это и случилось с подборками: `catalog_from_live` принимает их
#: параметром, ни один живой вызов их не передаёт, а состояние объявляло, что
#: их не подтверждает источник.
UNSUPPORTED_BY_SOURCE = "unsupported_by_source"

STATES: tuple[str, ...] = (ENABLED, DISABLED_BY_CONFIG, DISABLED_BY_API,
                           BLOCKED_CREDENTIALS, UNSUPPORTED_BY_SOURCE)

#: Человекочитаемые причины. Отчёт обязан отличать «выключили» от «забыли».
REASONS = {
    ENABLED: "тип включён в manifest и подтверждён источником данных",
    DISABLED_BY_CONFIG: "тип выключен в manifest владельцем",
    DISABLED_BY_API: "тип включён в manifest, но источник данных его не подтверждает",
    BLOCKED_CREDENTIALS: "тип включён в manifest, но учётные данные CDNVideoHub не переданы —"
                         " проверить наличие данных нечем",
    UNSUPPORTED_BY_SOURCE: "тип включён в manifest, но действующий источник такого раздела"
                           " не отдаёт вовсе — ждать данных нечего, нужен другой источник"
                           " или решение владельца",
}


@dataclass(frozen=True)
class TypeState:
    name: str
    state: str
    reason: str

    @property
    def active(self) -> bool:
        """Создаёт ли тип хоть какую-нибудь поверхность."""
        return self.state == ENABLED

    def as_dict(self) -> dict:
        return {"type": self.name, "state": self.state, "reason": self.reason, "active": self.active}


def configured(package: dict) -> dict[str, bool]:
    """Что объявлено в manifest. Неупомянутый тип считается выключенным.

    Умолчание именно такое: молчание manifest не должно включать раздел, который
    владелец не просил.
    """
    declared = package.get("content_types") or {}
    return {name: bool(declared.get(name, False)) for name in CONTENT_TYPES}


def resolve(
    package: dict,
    *,
    credentials_available: bool = False,
    api_capabilities: set | None = None,
    source_supports: set | None = None,
) -> dict[str, TypeState]:
    """Фактическое состояние каждого типа.

    `api_capabilities` — множество типов, наличие которых подтвердил источник
    данных. `None` означает «источник не опрашивался», и это не то же самое, что
    пустое множество: не опрошенный источник не отвечает «данных нет».

    `source_supports` — типы, которые действующий источник способен отдать в
    принципе. `None` означает «неизвестно», и тогда поведение прежнее. Знать это
    отдельно необходимо: «в этот раз не подтвердил» предлагает ждать, а «такого
    не отдаёт вовсе» — искать другой источник, и подменять второе первым значит
    отправить владельца ждать того, чего не будет.
    """
    declared = configured(package)
    out: dict[str, TypeState] = {}
    for name in CONTENT_TYPES:
        if not declared[name]:
            state = DISABLED_BY_CONFIG
        elif source_supports is not None and name not in source_supports:
            # Проверяется раньше учётных данных: доступ к источнику не меняет
            # того, что раздела у него нет.
            state = UNSUPPORTED_BY_SOURCE
        elif not credentials_available:
            state = BLOCKED_CREDENTIALS
        elif api_capabilities is None or name not in api_capabilities:
            state = DISABLED_BY_API
        else:
            state = ENABLED
        out[name] = TypeState(name=name, state=state, reason=REASONS[state])
    return out


def active_types(states: dict[str, TypeState]) -> list[str]:
    return [name for name in CONTENT_TYPES if states[name].active]


def counts(states: dict[str, TypeState]) -> dict[str, int]:
    """Сводка по состояниям — для отчёта сборки."""
    out = dict.fromkeys(STATES, 0)
    for state in states.values():
        out[state.state] += 1
    return out
