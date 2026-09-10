"""Переходник: контур чтения → модель представления Yummy.

Здесь и только здесь шаблон знает про таблицы. Компоненты
(`yummy_entity.py`) работают со словарями и о базе не знают вовсе — иначе
каждое расширение контура превращалось бы в правку разметки.

Готовность к расширению контракта
---------------------------------

Контур `yummy-read-model/1.0.0` сегодня отдаёт немного: название, год, тип,
постер, внешние оценки, события серий, статус показа, материалы редакции.
Остальные поля полной карточки — страна, студия, жанры, режиссёры, актёры,
возраст, длительность, сезоны, озвучки, альтернативные названия,
рекомендации — Архитектор добавляет отдельно.

Поэтому переходник читает **то, что есть**, а не то, что обязано быть:

* дополнительная колонка `entity` подхватывается, как только появится;
* таблица-связка (`entity_genre`, `entity_person`, …) подхватывается, как
  только появится, — по объявленной здесь карте имён;
* отсутствие источника означает отсутствие поля, а не пустую строку и не ноль.

Ничего не достраивается. Жанр, которого нет в контуре, не выводится из
названия; рекомендации не подбираются по совпадению слов; статус показа не
выводится из «доступных серий меньше заявленного» — это догадки, а они
неотличимы от фактов на странице и потому запрещены.
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3

КОНТРАКТ = "yummy-contract-adapter/1.0.0"

#: Колонки `entity`, которые представление умеет показать, если они появятся.
#: Ключ — поле представления, значение — допустимые имена колонок в контуре.
#: Несколько имён на поле: Архитектор волен назвать колонку по-своему, а
#: переименование не должно требовать выката шаблона.
КОЛОНКИ = {
    "description": ("description", "synopsis", "plot"),
    "backdrop": ("backdrop_path", "background_path", "banner_path"),
    "age_rating": ("age_rating", "age_limit", "rating_mpaa"),
    "duration_minutes": ("duration_minutes", "runtime_minutes", "duration"),
    "seasons": ("seasons", "seasons_total", "season_count"),
    "episodes_total": ("episodes_total", "episodes", "episode_count"),
    "aired_from": ("aired_from", "released_at", "premiere_at", "aired_on"),
    "aired_to": ("aired_to", "finished_at", "released_to"),
}

#: Таблицы-связки: поле представления → (имена таблиц, имена колонок значения).
#: Для ролей дополнительно проверяется колонка роли.
СВЯЗКИ = {
    "alt_titles": (("entity_title", "entity_alt_title"), ("title", "value", "name")),
    "genres": (("entity_genre", "entity_genres"), ("genre", "value", "name", "title")),
    "studios": (("entity_studio", "entity_studios"), ("studio", "value", "name", "title")),
    "countries": (("entity_country", "entity_countries"), ("country", "value", "name", "title")),
    "dubs": (("entity_dub", "entity_voice", "entity_dubs"), ("dub", "voice", "value", "name", "title")),
    "directors": (("entity_person", "entity_staff"), ("person", "name", "value", "title")),
    "cast": (("entity_person", "entity_cast", "entity_character"), ("person", "name", "value", "title")),
}

#: Какая роль в `entity_person` считается режиссёром и какая — актёром.
РОЛИ = {"directors": ("director", "режиссёр", "DIRECTOR"),
        "cast": ("actor", "voice_actor", "character", "актёр", "ACTOR")}


def _таблицы(соед) -> set[str]:
    return {р[0] for р in соед.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}


def _колонки(соед, таблица: str) -> set[str]:
    try:
        return {р[1] for р in соед.execute(f"PRAGMA table_info({таблица})")}
    except sqlite3.Error:
        return set()


class Контур:
    """Снимок возможностей контура. Считается один раз на запрос."""

    def __init__(self, соед):
        self.соед = соед
        self.таблицы = _таблицы(соед)
        self.колонки = {т: _колонки(соед, т) for т in self.таблицы}

    def есть_таблицу(self, имя: str) -> bool:
        return имя in self.таблицы

    def колонка(self, таблица: str, кандидаты) -> str | None:
        имеющиеся = self.колонки.get(таблица, set())
        for к in кандидаты:
            if к in имеющиеся:
                return к
        return None

    # --- поля -----------------------------------------------------------
    def доп_колонки(self) -> dict[str, str]:
        """Какие необязательные колонки `entity` контур уже отдаёт."""
        найдено = {}
        for поле, имена in КОЛОНКИ.items():
            к = self.колонка("entity", имена)
            if к:
                найдено[поле] = к
        return найдено

    def связка(self, поле: str, entity_id: str) -> list[str]:
        таблицы, значения = СВЯЗКИ[поле]
        for т in таблицы:
            if not self.есть_таблицу(т):
                continue
            зк = self.колонка(т, значения)
            ик = self.колонка(т, ("entity_id",))
            if not (зк and ик):
                continue
            условие, параметры = "", [entity_id]
            рк = self.колонка(т, ("role", "kind", "job"))
            if рк and поле in РОЛИ:
                метки = РОЛИ[поле]
                условие = " AND lower(" + рк + ") IN (" + ",".join("?" * len(метки)) + ")"
                параметры += [м.lower() for м in метки]
            пк = self.колонка(т, ("position", "ord", "sort", "idx"))
            порядок = f" ORDER BY {пк}" if пк else ""
            строки = self.соед.execute(
                f"SELECT {зк} FROM {т} WHERE {ик} = ?{условие}{порядок}",
                параметры).fetchall()
            значения_ = [str(с[0]).strip() for с in строки if с[0] is not None
                         and str(с[0]).strip()]
            if значения_:
                # Порядок сохраняется, повторы снимаются: одно имя дважды —
                # это дефект источника, а не два разных человека.
                видели, итог = set(), []
                for з in значения_:
                    if з not in видели:
                        видели.add(з)
                        итог.append(з)
                return итог
        return []


def версия_контракта(соед) -> str:
    """Версия контура, если он её объявляет. Иначе — базовая 1.0.0.

    Версия читается, а не угадывается: представление обязано уметь отказать
    несовместимому контракту, а для этого его надо знать.
    """
    к = Контур(соед)
    for таблица, поле in (("read_model_meta", "contract"), ("meta", "contract")):
        if к.есть_таблицу(таблица) and поле in к.колонки.get(таблица, set()):
            строка = соед.execute(f"SELECT {поле} FROM {таблица} LIMIT 1").fetchone()
            if строка and строка[0]:
                return str(строка[0])
    return "yummy-read-model/1.0.0"


def _строка_дат(с: dict) -> str | None:
    """«с … по …» из того, что известно. Половина даты — тоже ответ."""
    от, до = (с.get("aired_from") or "")[:10], (с.get("aired_to") or "")[:10]
    if от and до and от != до:
        return f"{от} — {до}"
    return от or до or None


def _строка_серий(выпущено, всего) -> str | None:
    """«12 из 24», «12» или ничего. Ноль сериями не считается."""
    if выпущено and всего:
        return f"{int(выпущено)} из {int(всего)}"
    if всего:
        return f"{int(всего)}"
    if выпущено:
        return f"{int(выпущено)}"
    return None


def сущность(соед, entity_id: str | None = None,
             canonical_path: str | None = None) -> dict | None:
    """Модель представления одного тайтла. None — сущности нет в контуре."""
    if not (entity_id or canonical_path):
        return None
    соед.row_factory = sqlite3.Row
    к = Контур(соед)
    доп = к.доп_колонки()
    поля = ["entity_id", "canonical_path", "title_ru", "title_original", "kind",
            "year", "poster_path", "airing_status", "episodes_released",
            "next_episode_at", "last_episode_at"]
    поля += sorted(set(доп.values()) - set(поля))
    where, параметр = ("entity_id = ?", entity_id) if entity_id else (
        "canonical_path = ?", canonical_path)
    строка = соед.execute(
        f"SELECT {', '.join(поля)} FROM entity WHERE {where} LIMIT 1",
        (параметр,)).fetchone()
    if строка is None:
        return None
    с = dict(строка)
    ид = с["entity_id"]

    оценки = [dict(р) for р in соед.execute(
        "SELECT provider, value, scale, votes, status, fetched_at, source "
        "FROM external_rating WHERE entity_id = ?", (ид,)).fetchall()]
    # Порядок вывода — по числу голосов, затем по имени провайдера: он должен
    # быть устойчивым, иначе одна и та же карточка перетасовывается между
    # запросами и её нельзя сравнить со снимком.
    оценки.sort(key=lambda о: (-(о.get("votes") or 0), о.get("provider") or ""))

    вид = {
        "entity_id": ид,
        "canonical_path": с.get("canonical_path"),
        "title": с.get("title_ru") or с.get("title_original"),
        "title_original": (с.get("title_original")
                           if с.get("title_original") != с.get("title_ru") else None),
        "poster": с.get("poster_path"),
        "kind": с.get("kind") if с.get("kind") != "UNKNOWN" else None,
        # Статус показа берётся только подтверждённый. UNCONFIRMED — это «мы не
        # знаем», и печатать его как статус нельзя.
        "status": (с.get("airing_status")
                   if str(с.get("airing_status") or "").startswith("CONFIRMED") else None),
        "year": с.get("year"),
        "ratings": оценки,
        "contract": версия_контракта(соед),
    }
    for поле, колонка in доп.items():
        вид[поле] = с.get(колонка)
    вид["backdrop"] = вид.get("backdrop")
    вид["aired"] = _строка_дат(вид)
    вид["episodes"] = _строка_серий(с.get("episodes_released"),
                                    вид.get("episodes_total"))
    if вид.get("duration_minutes"):
        вид["duration"] = f"{int(вид['duration_minutes'])} мин"
    for поле in СВЯЗКИ:
        значения = к.связка(поле, ид)
        if значения:
            вид[поле] = значения
    вид["recommendations"] = рекомендации(соед, ид)
    вид["personal"] = личная(соед, ид)
    return вид


#: Таблица рекомендаций контура. Пока её нет — секция не выводится: подбирать
#: «похожее» внутри шаблона запрещено.
ТАБЛИЦЫ_РЕКОМЕНДАЦИЙ = ("recommendation", "entity_recommendation", "recommendations")


def рекомендации(соед, entity_id: str, предел: int = 12) -> list[dict]:
    """Только объявленные контуром связи. Ничего не подбирается на месте."""
    соед.row_factory = sqlite3.Row
    к = Контур(соед)
    for т in ТАБЛИЦЫ_РЕКОМЕНДАЦИЙ:
        if not к.есть_таблицу(т):
            continue
        ик = к.колонка(т, ("entity_id", "source_entity_id", "from_entity_id"))
        цк = к.колонка(т, ("target_entity_id", "recommended_entity_id", "to_entity_id"))
        if not (ик and цк):
            continue
        рк = к.колонка(т, ("reason", "note", "why"))
        ск = к.колонка(т, ("source", "provider"))
        вк = к.колонка(т, ("weight", "score", "rank", "position"))
        поля = [f"r.{цк} AS target"]
        поля.append(f"r.{рк} AS reason" if рк else "NULL AS reason")
        поля.append(f"r.{ск} AS source" if ск else "NULL AS source")
        порядок = f" ORDER BY r.{вк} DESC" if вк else ""
        строки = соед.execute(
            f"SELECT {', '.join(поля)}, e.canonical_path, e.title_ru, "
            f"e.title_original, e.poster_path, e.year, e.kind "
            f"FROM {т} r JOIN entity e ON e.entity_id = r.{цк} "
            f"WHERE r.{ик} = ? AND e.canonical_path IS NOT NULL "
            f"AND e.canonical_path != ''{порядок} LIMIT ?",
            (entity_id, предел)).fetchall()
        итог = []
        for с in строки:
            оценки = [dict(о) for о in соед.execute(
                "SELECT provider, value, scale, votes, status FROM external_rating "
                "WHERE entity_id = ? AND status = 'OK'", (с["target"],)).fetchall()]
            итог.append({
                "entity_id": с["target"],
                "canonical_path": с["canonical_path"],
                "title": с["title_ru"] or с["title_original"],
                "poster": с["poster_path"],
                "year": с["year"],
                "kind": с["kind"] if с["kind"] != "UNKNOWN" else None,
                "ratings": оценки,
                "reason": с["reason"],
                "source": с["source"],
            })
        if итог:
            return итог
    return []


def личная(соед, entity_id: str, user_id: str | None = None) -> dict:
    """Состояние внутренней оценки. Без рабочего API — «недоступен».

    Сводка (среднее и число голосов) считается по реальным строкам и не
    показывается, когда их нет: «0 голосов» и «0.0» — не факты, а пустота с
    видом факта.
    """
    соед.row_factory = sqlite3.Row
    к = Контур(соед)
    if not к.есть_таблицу("user_rating"):
        return {"state": "недоступен"}
    свод = соед.execute(
        "SELECT COUNT(*) AS n, AVG(value) AS avg, MAX(scale) AS scale "
        "FROM user_rating WHERE entity_id = ?", (entity_id,)).fetchone()
    состояние = {"scale": int(свод["scale"] or 10)}
    if свод["n"]:
        состояние["votes"] = свод["n"]
        состояние["average"] = свод["avg"]
    своя = None
    if user_id:
        строка = соед.execute(
            "SELECT value FROM user_rating WHERE entity_id = ? AND user_id = ?",
            (entity_id, user_id)).fetchone()
        своя = строка["value"] if строка else None
    состояние["value"] = своя
    состояние["state"] = "оценено" if своя else "нет"
    return состояние


# --- ленты -------------------------------------------------------------------
#
# Шесть поверхностей, шесть запросов, шесть источников. Ни одна не является
# срезом другой: пересечение проверяется тестом.

def _карточки(строки) -> list[dict]:
    return [{"entity_id": с["entity_id"], "canonical_path": с["canonical_path"],
             "title": с["title_ru"] or с["title_original"],
             "poster": с["poster_path"], "year": с["year"], "kind": с["kind"],
             "caption": с["caption"] if "caption" in с.keys() else None}
            for с in строки if с["canonical_path"]]


def новые_серии(соед, предел: int = 24) -> list[dict]:
    """События появления серий. Не «недавно добавленные тайтлы»."""
    соед.row_factory = sqlite3.Row
    строки = соед.execute(
        """
        SELECT e.entity_id, e.canonical_path, e.title_ru, e.title_original,
               e.poster_path, e.year, e.kind,
               'Сезон ' || v.season || ', серия ' || v.episode
               || CASE WHEN v.voice != '' THEN ' · ' || v.voice ELSE '' END AS caption,
               MAX(COALESCE(v.source_event_at, v.published_at)) AS когда
          FROM episode_event v JOIN entity e ON e.entity_id = v.entity_id
         WHERE e.canonical_path IS NOT NULL AND e.canonical_path != ''
         GROUP BY v.entity_id, v.season, v.episode, v.voice
         ORDER BY когда DESC LIMIT ?""", (предел,)).fetchall()
    return _карточки(строки)


def сейчас_выходит(соед, предел: int = 24) -> list[dict]:
    """Только подтверждённый статус. Догадка по числу серий запрещена."""
    соед.row_factory = sqlite3.Row
    строки = соед.execute(
        """
        SELECT entity_id, canonical_path, title_ru, title_original, poster_path,
               year, kind,
               CASE WHEN episodes_released > 0
                    THEN 'Вышло серий: ' || episodes_released END AS caption
          FROM entity
         WHERE airing_status = 'CONFIRMED_ONGOING'
               AND canonical_path IS NOT NULL AND canonical_path != ''
         ORDER BY COALESCE(last_episode_at, updated_at) DESC LIMIT ?""",
        (предел,)).fetchall()
    return _карточки(строки)


def расписание(соед, предел: int = 40, сейчас: str | None = None) -> list[dict]:
    """Подтверждённые ближайшие серии. Прошлое расписанием не является."""
    соед.row_factory = sqlite3.Row
    порог = сейчас or dt.datetime.now(dt.timezone.utc).isoformat()
    строки = соед.execute(
        """
        SELECT entity_id, canonical_path, title_ru, title_original, poster_path,
               year, kind, substr(next_episode_at, 1, 10) AS caption
          FROM entity
         WHERE next_episode_at IS NOT NULL AND next_episode_at >= ?
               AND canonical_path IS NOT NULL AND canonical_path != ''
         ORDER BY next_episode_at ASC LIMIT ?""", (порог, предел)).fetchall()
    return _карточки(строки)


def посты(соед, тип: str, предел: int = 12, сейчас: str | None = None) -> list[dict]:
    """Новости или анонсы. Протухшее не показывается, но и не удаляется."""
    соед.row_factory = sqlite3.Row
    if not Контур(соед).есть_таблицу("editorial_post"):
        return []
    строки = соед.execute(
        """
        SELECT post_id, type, source, title, summary, image_path, canonical_path,
               provenance, published_at, updated_at, status
          FROM editorial_post
         WHERE type = ? AND status = 'published'
               AND canonical_path IS NOT NULL AND canonical_path != ''
         ORDER BY published_at DESC LIMIT ?""", (тип, предел)).fetchall()
    порог = dt.datetime.fromisoformat(
        (сейчас or dt.datetime.now(dt.timezone.utc).isoformat()).replace("Z", "+00:00")
    ) - dt.timedelta(hours=48)
    итог = []
    for с in строки:
        обновлено = None
        try:
            обновлено = dt.datetime.fromisoformat(
                str(с["updated_at"]).replace("Z", "+00:00"))
        except ValueError:
            pass
        # SLA свежести: 48 часов без обновления — материал не показывается.
        if обновлено is not None and обновлено.tzinfo and обновлено < порог:
            continue
        итог.append({"post_id": с["post_id"], "title": с["title"],
                     "summary": с["summary"], "image": с["image_path"],
                     "canonical_path": с["canonical_path"], "source": с["source"],
                     "published_at": с["published_at"], "provenance": с["provenance"]})
    return итог


#: Контур отдаёт «Актуальное» в camelCase (`entityId`, `canonicalPath`) —
#: это его публичный вид. Компоненты работают со snake_case. Перевод один и
#: здесь: два разных написания одного поля в разметке однажды разойдутся.
ПЕРЕВОД = {"entityId": "entity_id", "canonicalPath": "canonical_path",
           "poster": "poster", "title": "title", "year": "year", "kind": "kind"}


def из_контура(элементы) -> list[dict]:
    итог = []
    for э in элементы or []:
        к = {новое: э.get(старое) for старое, новое in ПЕРЕВОД.items()}
        if к.get("canonical_path"):
            итог.append(к)
    return итог


#: Как считается каждая поверхность. Ленивые вызовы: «Актуальное» проходит по
#: всему каталогу с рейтингами, и считать его ради страницы, где его нет, —
#: секунды ожидания посетителя ни за что.
ИСТОЧНИКИ = ("new_episodes", "ongoing", "trending", "news", "announcements",
             "schedule")


def ленты(соед, актуальное=None, предел: int = 24, сейчас: str | None = None,
          нужные=None) -> dict[str, list[dict]]:
    """Поверхности контракта. Каждая — своим запросом к своему источнику."""
    нужные = set(нужные) if нужные else set(ИСТОЧНИКИ)
    как = {
        "new_episodes": lambda: новые_серии(соед, предел),
        "ongoing": lambda: сейчас_выходит(соед, предел),
        "trending": lambda: (из_контура(актуальное(соед, предел))
                             if актуальное else []),
        "news": lambda: посты(соед, "news", 12, сейчас),
        "announcements": lambda: посты(соед, "announcement", 12, сейчас),
        "schedule": lambda: расписание(соед, 40, сейчас),
    }
    return {и: (как[и]() if и in нужные else []) for и in ИСТОЧНИКИ}
