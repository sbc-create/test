"""Единственный источник правды о событиях аналитики.

Здесь описаны девять событий, их цели в Метрике и — главное — какие параметры
каждому событию разрешено нести. Из этого описания генерируются и клиент для
браузера, и запросы на создание целей, поэтому «цель есть, а событие шлёт не
то» становится невозможным состоянием.

Запрет, ради которого модуль вообще существует: в Метрику не передаются тексты
комментариев, имена, e-mail, токены, Publisher ID и поисковые запросы. Разрешены
только технические идентификаторы и категориальные значения из перечислений
ниже. Параметр, которого нет в описании, клиент выбрасывает, а не отправляет.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

#: Типы параметров, которые вообще бывают. Свободного текста среди них нет —
#: это и есть механическая гарантия, что персональные данные не уедут.
ParamKind = Literal["id", "int", "enum", "bool"]


@dataclass(frozen=True)
class EventParam:
    """Разрешённый параметр события."""

    name: str
    kind: ParamKind
    description: str
    #: Для ``enum`` — полный список допустимых значений. Иначе пусто.
    values: tuple[str, ...] = ()
    #: Для ``id`` — максимальная длина. Идентификатор длиннее — это уже не ID.
    max_length: int = 64

    def as_dict(self) -> dict:
        out = {"name": self.name, "kind": self.kind, "description": self.description}
        if self.values:
            out["values"] = list(self.values)
        if self.kind == "id":
            out["max_length"] = self.max_length
        return out


@dataclass(frozen=True)
class AnalyticsEvent:
    """Событие сайта и соответствующая ему цель Метрики."""

    #: Идентификатор события. Он же — `url` в условии цели типа `action`.
    id: str
    #: Человеческое имя цели в интерфейсе Метрики.
    goal_name: str
    purpose: str
    params: tuple[EventParam, ...] = field(default_factory=tuple)

    def as_goal(self) -> dict:
        """Тело цели по контракту Management API: JavaScript-событие."""
        return {
            "name": self.goal_name,
            "type": "action",
            "conditions": [{"type": "exact", "url": self.id}],
        }

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "goal_name": self.goal_name,
            "purpose": self.purpose,
            "params": [p.as_dict() for p in self.params],
        }


# --------------------------------------------------------------------------
# Категориальные словари. Значение вне словаря не отправляется.
# --------------------------------------------------------------------------
RESULT_BUCKETS = ("none", "1-10", "11-50", "51+")
LENGTH_BUCKETS = ("short", "medium", "long")
SEARCH_SOURCES = ("header", "page", "suggest")
FILTER_NAMES = ("genre", "year", "status", "season", "voice", "sort")
PLAYER_KINDS = ("vk_white", "cdnvideohub", "unavailable")
PLAYER_ERRORS = ("no_data", "rights_missing", "network", "decode", "timeout", "unknown")

_TITLE_ID = EventParam("title_id", "id", "Технический идентификатор тайтла из каталога пакета")
_EPISODE_ID = EventParam("episode_id", "id", "Технический идентификатор эпизода")


#: Девять событий задания. Порядок фиксирован: он же порядок создания целей.
EVENTS: tuple[AnalyticsEvent, ...] = (
    AnalyticsEvent(
        "search",
        "Поиск по каталогу",
        "Пользователь выполнил поиск. Сам запрос НЕ передаётся: он может содержать личные данные.",
        (
            EventParam("results_bucket", "enum", "Сколько нашлось, интервалом", RESULT_BUCKETS),
            EventParam("source", "enum", "Откуда запущен поиск", SEARCH_SOURCES),
        ),
    ),
    AnalyticsEvent(
        "filter_apply",
        "Применён фильтр каталога",
        "Пользователь применил фильтр. Передаётся имя фильтра, но не введённое значение.",
        (
            EventParam("filter_name", "enum", "Какой фильтр применён", FILTER_NAMES),
            EventParam("value_count", "int", "Сколько значений выбрано"),
        ),
    ),
    AnalyticsEvent(
        "title_view",
        "Просмотр страницы тайтла",
        "Открыта карточка тайтла.",
        (_TITLE_ID, EventParam("category", "id", "Слаг раздела каталога")),
    ),
    AnalyticsEvent(
        "season_select",
        "Выбран сезон",
        "Пользователь переключил сезон.",
        (_TITLE_ID, EventParam("season_number", "int", "Номер сезона")),
    ),
    AnalyticsEvent(
        "episode_select",
        "Выбран эпизод",
        "Пользователь выбрал серию.",
        (
            _TITLE_ID,
            EventParam("season_number", "int", "Номер сезона"),
            EventParam("episode_number", "int", "Номер серии"),
        ),
    ),
    AnalyticsEvent(
        "player_start",
        "Запуск плеера",
        "Плеер начал загрузку по действию пользователя.",
        (_TITLE_ID, _EPISODE_ID, EventParam("player", "enum", "Какой плеер встроен", PLAYER_KINDS)),
    ),
    AnalyticsEvent(
        "player_ready",
        "Плеер готов к воспроизведению",
        "Плеер сообщил о готовности.",
        (_TITLE_ID, _EPISODE_ID, EventParam("player", "enum", "Какой плеер встроен", PLAYER_KINDS)),
    ),
    AnalyticsEvent(
        "player_error",
        "Ошибка плеера",
        "Плеер сообщил об ошибке. Передаётся категория ошибки, не текст сообщения.",
        (
            _TITLE_ID,
            _EPISODE_ID,
            EventParam("error_code", "enum", "Категория ошибки", PLAYER_ERRORS),
        ),
    ),
    AnalyticsEvent(
        "comment_submit",
        "Отправлен комментарий",
        "Комментарий отправлен на модерацию. Текст, имя и e-mail НЕ передаются никогда.",
        (
            _TITLE_ID,
            EventParam("length_bucket", "enum", "Длина комментария интервалом", LENGTH_BUCKETS),
        ),
    ),
)

EVENT_IDS: tuple[str, ...] = tuple(event.id for event in EVENTS)
BY_ID: dict[str, AnalyticsEvent] = {event.id: event for event in EVENTS}

#: Имена, которые нельзя отправлять ни при каких обстоятельствах. Клиент
#: отбрасывает их отдельной проверкой — до сверки со списком разрешённых. Это
#: избыточно и намеренно: список разрешённых когда-нибудь расширят по ошибке.
FORBIDDEN_PARAM_NAMES: tuple[str, ...] = (
    "text", "comment", "comment_text", "body", "message",
    "name", "username", "user_name", "login", "nickname",
    "email", "mail", "e_mail", "phone", "tel",
    "query", "q", "search_query", "keyword",
    "token", "access_token", "oauth", "secret", "password", "api_key",
    "publisher_id", "publisherid", "session", "cookie", "ip", "user_id", "uid",
)


def goals_payload() -> list[dict]:
    """Тела всех девяти целей в порядке создания."""
    return [event.as_goal() for event in EVENTS]


def as_dict() -> dict:
    """Машиночитаемое описание контракта событий — для отчёта и тестов."""
    return {
        "version": 1,
        "events": [event.as_dict() for event in EVENTS],
        "forbidden_param_names": list(FORBIDDEN_PARAM_NAMES),
    }
