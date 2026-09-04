"""Канонические фикстуры ViewModel: одни и те же данные для всех шаблонов.

Зачем. Шаблон — слой представления, и проверять его надо на данных, а не на
живой CMS: иначе падение витрины невозможно отличить от падения источника, а два
шаблона проверяются на разных данных и «оба зелёные» ничего не значат.

Три свойства, ради которых это отдельный модуль, а не набор JSON-файлов рядом с
каждым шаблоном:

* **детерминированность.** Ни `now()`, ни случайности. Время здесь —
  зафиксированные мгновения, иначе снимок вёрстки менялся бы сам по себе и
  визуальные проверки пришлось бы отключить как «мигающие».
* **полнота состояний.** Для каждой ViewModel заданы normal / loading / empty /
  degraded / error. Шаблон, который умеет только normal, ломается в бою именно
  тогда, когда данные не пришли, — то есть в худший момент.
* **край, а не только середина.** Длинный текст, отсутствующая картинка,
  неизвестное необязательное значение. Вёрстка разъезжается на них, а не на
  аккуратной строке из трёх слов.

`degraded` — это не `error`. Degraded означает, что данные есть, но устарели или
неполны, и страница обязана их показать, честно пометив. Error означает, что
показывать нечего. Смешение этих двух состояний и приводит к пустой витрине там,
где можно было отдать вчерашний снимок.
"""

from __future__ import annotations

import copy
from typing import Any

# Зафиксированные мгновения. Любое сравнение с «сейчас» сделало бы фикстуру
# недетерминированной, поэтому свежесть выражается через разницу между этими
# двумя значениями, а не через часы машины.
INSTANT_NOW = "2026-09-03T12:00:00Z"
INSTANT_STALE = "2026-09-01T12:00:00Z"

STATES = ("normal", "loading", "empty", "degraded", "error")

VIEW_MODELS = (
    "site_header",
    "title_card",
    "listing",
    "new_episodes",
    "updates",
    "news",
    "announcements",
    "rating",
    "search",
    "pagination",
    "player",
    "not_found",
)

# Край, на котором вёрстка ломается чаще всего.
LONG_TEXT = (
    "Сказание о пастухе богов: возвращение владыки девяти небес и хроника "
    "падения тысячелетней династии, часть вторая, режиссёрская версия"
)


def _title_card() -> dict[str, Any]:
    return {
        "id": "0192e01a-ecab-7d92-8837-524f28150a35",
        "name": "Сказание о пастухе богов",
        "href": "/anime/skazanie-o-pastuhe-bogov",
        "poster_url": "https://example.invalid/poster.webp",
        "year": 2024,
        "episodes_available": 98,
        # Время события, а не время отрисовки: подменять одно другим запрещено.
        "event_at": INSTANT_NOW,
        "rating": _rating(),
    }


def _rating() -> dict[str, Any]:
    """Оценка всегда с происхождением. Голое число запрещено контрактом."""
    return {
        "value": 7.5,
        "scale_max": 10,
        "source": "kinopoisk",
        "fetched_at": INSTANT_NOW,
        "vote_count": 1423,
        "confidence": "high",
    }


def _base(view_model: str) -> dict[str, Any]:
    if view_model == "site_header":
        return {
            "brand": "YummyAnime",
            "nav": [
                {"label": "Каталог", "href": "/catalog"},
                {"label": "Новости", "href": "/posts"},
            ],
            "search_href": "/search",
        }
    if view_model == "title_card":
        return _title_card()
    if view_model == "listing":
        return {"heading": "Аниме летнего сезона", "items": [_title_card()], "total": 1}
    if view_model == "new_episodes":
        return {
            "heading": "Новые серии",
            "items": [{**_title_card(), "season": 1, "episode": 98, "published_at": INSTANT_NOW}],
        }
    if view_model == "updates":
        return {"heading": "Обновления", "items": [{**_title_card(), "changed_at": INSTANT_NOW}]}
    if view_model == "news":
        return {
            "heading": "Новости",
            "items": [
                {
                    "id": "news-1",
                    "title": "Второй сезон подтверждён",
                    "href": "/posts/vtoroy-sezon",
                    "published_at": INSTANT_NOW,
                    "lead": "Студия объявила дату выхода.",
                }
            ],
        }
    if view_model == "announcements":
        return {
            "heading": "Анонсы",
            "items": [{"id": "ann-1", "name": "Премьера осени", "premiere_at": INSTANT_NOW, "href": "/anime/premiera"}],
        }
    if view_model == "rating":
        return _rating()
    if view_model == "search":
        return {"query": "пастух", "items": [_title_card()], "total": 1}
    if view_model == "pagination":
        return {"page": 2, "per_page": 24, "total": 105, "has_next": True, "has_prev": True}
    if view_model == "player":
        return {
            "status": "ready",
            "title_id": "0192e01a-ecab-7d92-8837-524f28150a35",
            "season": 1,
            "episode": 98,
            "poster_url": "https://example.invalid/poster.webp",
            "message": None,
        }
    if view_model == "not_found":
        return {"code": 404, "heading": "Страница не найдена", "suggest_href": "/catalog"}
    raise KeyError(f"неизвестная ViewModel: {view_model}")


def _emptied(value: Any) -> Any:
    """Пустое состояние: списки пустеют, скаляры обнуляются в None."""
    if isinstance(value, dict):
        return {k: _emptied(v) for k, v in value.items()}
    if isinstance(value, list):
        return []
    return value


def fixture(view_model: str, state: str = "normal") -> dict[str, Any]:
    """Каноническая фикстура. Возвращается копия: правка у потребителя не должна
    протекать в следующий вызов — иначе тесты начнут зависеть от порядка."""
    if state not in STATES:
        raise KeyError(f"неизвестное состояние: {state}")
    data = copy.deepcopy(_base(view_model))

    if state == "normal":
        pass
    elif state == "loading":
        # Данных ещё нет, но и ошибки нет: шаблон обязан показать скелет,
        # а не пустоту и не спиннер без конца.
        data = {"state": "loading", "view_model": view_model}
    elif state == "empty":
        data = _emptied(data)
        data["state"] = "empty"
    elif state == "degraded":
        # Данные есть, но устаревшие. Показать обязаны — с честной пометкой.
        data["state"] = "degraded"
        data["stale_since"] = INSTANT_STALE
        data["notice"] = "данные могли устареть"
    elif state == "error":
        data = {"state": "error", "view_model": view_model, "message": "источник недоступен"}

    if isinstance(data, dict):
        data.setdefault("state", state)
    return data


def edge_fixture(view_model: str, edge: str) -> dict[str, Any]:
    """Крайние случаи, на которых вёрстка расходится."""
    data = fixture(view_model, "normal")
    if edge == "long_text":
        for key in ("name", "heading", "title", "query"):
            if key in data:
                data[key] = LONG_TEXT
        for item in data.get("items", []) or []:
            if isinstance(item, dict) and "name" in item:
                item["name"] = LONG_TEXT
    elif edge == "missing_media":
        data.pop("poster_url", None)
        data["poster_url"] = None
        for item in data.get("items", []) or []:
            if isinstance(item, dict):
                item["poster_url"] = None
    elif edge == "unknown_optional":
        # Необязательное поле неизвестно. Отсутствие оценки показывается как
        # отсутствие, а не как ноль — иначе шаблон соврёт пользователю.
        if "rating" in data:
            data["rating"] = None
        for item in data.get("items", []) or []:
            if isinstance(item, dict):
                item["rating"] = None
    else:
        raise KeyError(f"неизвестный крайний случай: {edge}")
    data["edge"] = edge
    return data


EDGES = ("long_text", "missing_media", "unknown_optional")


def all_fixtures() -> dict[str, dict[str, Any]]:
    """Полный набор — то, что отдаёт mock-сервер и на чём идёт conformance."""
    out: dict[str, dict[str, Any]] = {}
    for view_model in VIEW_MODELS:
        for state in STATES:
            out[f"{view_model}/{state}"] = fixture(view_model, state)
        for edge in EDGES:
            out[f"{view_model}/edge:{edge}"] = edge_fixture(view_model, edge)
    return out
