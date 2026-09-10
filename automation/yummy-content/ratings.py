"""Адаптеры внешних рейтингов аниме. Только официальные API, только ID-first.

Почему ID-first — не пожелание, а единственный допустимый способ
----------------------------------------------------------------

Сопоставление по названию на этом каталоге даёт ложные совпадения там, где
их заметить труднее всего: у сиквелов, спешлов и пересъёмок названия
различаются одним словом или годом. Поэтому связь берётся только по
идентификатору аниме-домена — `external_ids.mal`, который CVH отдаёт у части
записей. Записи без такого идентификатора остаются `UNMATCHED` и не
публикуются: отсутствие оценки честнее подставленной чужой.

Fuzzy-сопоставление не выполняется вовсе. Если оно когда-нибудь появится,
его результат обязан идти в карантин, а не в выдачу.

Разрешения поставщиков
----------------------

Разрешение владельца проекта получено и не заменяет согласия поставщиков:

* AniList — публичный GraphQL, работает без ключа, включён в shadow;
* Kitsu — публичный JSON:API, работает без ключа, включён как резерв;
* Simkl — требует client_id; ключа нет, адаптер выключен по отсутствию
  credentials, а не по отсутствию кода;
* Shikimori — реализован полностью, но выключен feature-флагом до
  письменного согласия Shikimori.

HTML не скрейпится ни у одного источника. Jikan как замена MAL не
используется.
"""
from __future__ import annotations

import json, os, sqlite3, time, urllib.error, urllib.parse, urllib.request
from typing import Any

ВЕРСИЯ = "yummy-ratings/1.0.0"


class TransportError(RuntimeError):
    """Источник не ответил. Это НЕ «у источника нет оценки».

    Первая версия возвращала `None` и на отказ сети, и на отсутствие оценки,
    и обе причины попадали в отчёт как `PROVIDER_NO_RATING`. Получалось, что
    полностью заблокированный источник выглядел работающим и честно
    сообщившим «оценок нет» — самый дорогой вид тишины.
    """
АГЕНТ = "site-factory-shadow/1.0 (contact: owner)"

#: Рубильник на каждого поставщика. Выключенный адаптер не делает ни одного
#: запроса — это и есть kill-switch, а не фильтрация результата после.
ВКЛЮЧЕНЫ = {
    "anilist": os.environ.get("RATINGS_ANILIST", "1") == "1",
    "kitsu":   os.environ.get("RATINGS_KITSU", "1") == "1",
    "simkl":   os.environ.get("RATINGS_SIMKL", "0") == "1",
    "shikimori": os.environ.get("RATINGS_SHIKIMORI", "0") == "1",
}
ПРИЧИНА_ВЫКЛ = {
    "simkl": "нет client_id: credentials не выданы",
    "shikimori": "ожидается письменное согласие Shikimori",
}

DDL = """
CREATE TABLE IF NOT EXISTS rating_match (
  entity_id TEXT NOT NULL, provider TEXT NOT NULL,
  provider_entity_id TEXT, match_method TEXT NOT NULL,
  match_confidence REAL NOT NULL, outcome TEXT NOT NULL,
  reason TEXT, updated_at TEXT NOT NULL,
  PRIMARY KEY (entity_id, provider));
CREATE TABLE IF NOT EXISTS rating_quarantine (
  entity_id TEXT NOT NULL, provider TEXT NOT NULL, candidate TEXT,
  reason TEXT NOT NULL, created_at TEXT NOT NULL,
  PRIMARY KEY (entity_id, provider));
"""


def _get(url: str, *, данные: bytes | None = None,
         заголовки: dict | None = None) -> tuple[int, Any]:
    зпр = urllib.request.Request(url, data=данные, headers={
        "User-Agent": АГЕНТ, "Accept": "application/json", **(заголовки or {})})
    try:
        with urllib.request.urlopen(зпр, timeout=25) as о:
            return о.status, json.loads(о.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


# --- адаптеры ---------------------------------------------------------------

def anilist(mal_id: str) -> dict | None:
    """AniList по `idMal`. Оценка `averageScore` по стобалльной шкале."""
    q = ("query($m:Int){Media(idMal:$m,type:ANIME){id averageScore "
         "popularity siteUrl}}")
    код, тело = _get("https://graphql.anilist.co",
                     данные=json.dumps({"query": q, "variables": {"m": int(mal_id)}}
                                       ).encode(),
                     заголовки={"Content-Type": "application/json"})
    if код != 200:
        raise TransportError(f"anilist HTTP {код}")
    м = ((тело or {}).get("data") or {}).get("Media")
    if not м or м.get("averageScore") is None:
        return None
    return {"provider_entity_id": str(м["id"]), "value": float(м["averageScore"]),
            "scale": 100.0, "votes": м.get("popularity"),
            "source_url": м.get("siteUrl") or f"https://anilist.co/anime/{м['id']}"}


def kitsu(mal_id: str) -> dict | None:
    """Kitsu через официальный mapping MAL → Kitsu. Шкала стобалльная."""
    # Скобки в именах фильтров обязаны быть закодированы, а Kitsu отвечает
    # только на свой тип содержимого. Без того и другого запрос уходил впустую, а
    # адаптер объявлял это «у источника нет оценки».
    url = "https://kitsu.io/api/edge/mappings?" + urllib.parse.urlencode({
        "filter[externalSite]": "myanimelist/anime",
        "filter[externalId]": str(mal_id), "include": "item"})
    код, тело = _get(url, заголовки={"Accept": "application/vnd.api+json"})
    if код != 200:
        raise TransportError(f"kitsu HTTP {код}")
    if not (тело or {}).get("included"):
        return None
    поз = тело["included"][0]
    атр = поз.get("attributes") or {}
    if атр.get("averageRating") in (None, ""):
        return None
    return {"provider_entity_id": str(поз.get("id")),
            "value": float(атр["averageRating"]), "scale": 100.0,
            "votes": (атр.get("userCount") or None),
            "source_url": f"https://kitsu.io/anime/{поз.get('id')}"}


def shikimori(mal_id: str) -> dict | None:
    """Shikimori: идентификатор совпадает с MAL. Выключен до согласия."""
    код, тело = _get(f"https://shikimori.one/api/animes/{mal_id}")
    if код != 200 or not тело or not тело.get("score"):
        return None
    оценка = float(тело["score"])
    if оценка <= 0:
        return None
    return {"provider_entity_id": str(тело.get("id")), "value": оценка,
            "scale": 10.0, "votes": None,
            "source_url": f"https://shikimori.one/animes/{тело.get('id')}"}


def simkl(mal_id: str) -> dict | None:
    """Simkl. Без client_id не вызывается вовсе."""
    ключ = os.environ.get("SIMKL_CLIENT_ID")
    if not ключ:
        return None
    код, тело = _get(f"https://api.simkl.com/search/id?mal={mal_id}&client_id={ключ}")
    if код != 200 or not тело:
        return None
    п = тело[0] if isinstance(тело, list) and тело else None
    оц = ((п or {}).get("ratings") or {}).get("simkl") or {}
    if not п or оц.get("rating") is None:
        return None
    return {"provider_entity_id": str((п.get("ids") or {}).get("simkl")),
            "value": float(оц["rating"]), "scale": 10.0,
            "votes": оц.get("votes"), "source_url": п.get("url")}


АДАПТЕРЫ = {"anilist": anilist, "kitsu": kitsu,
            "shikimori": shikimori, "simkl": simkl}
ПАУЗА = {"anilist": 0.75, "kitsu": 0.3, "shikimori": 1.1, "simkl": 0.3}


def mal_идентификаторы(соед: sqlite3.Connection) -> dict[str, str]:
    """entity_id → mal id из detail-кэша. Единственный ключ сопоставления."""
    import detail as detail_mod
    итог = {}
    for р in соед.execute("SELECT entity_id FROM entity"):
        д = detail_mod.прочитать(р["entity_id"])
        m = ((д or {}).get("external_ids") or {}).get("mal")
        if m:
            итог[р["entity_id"]] = str(m)
    return итог


def собрать(соед: sqlite3.Connection, поставщик: str,
            предел: int | None = None) -> dict:
    соед.executescript(DDL)
    if not ВКЛЮЧЕНЫ.get(поставщик):
        return {"provider": поставщик, "enabled": False,
                "reason": ПРИЧИНА_ВЫКЛ.get(поставщик, "выключен"),
                "matched": 0, "unmatched": 0}
    карта = mal_идентификаторы(соед)
    цели = [(e, m) for e, m in карта.items()]
    if предел:
        цели = цели[:предел]
    т = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ок = нет = ошибок = 0
    for ид, mal in цели:
        уже = соед.execute(
            "SELECT outcome FROM rating_match WHERE entity_id=? AND provider=?",
            (ид, поставщик)).fetchone()
        if уже and уже["outcome"] in ("MATCHED", "PROVIDER_NO_RATING"):
            continue                      # идемпотентность: повтор не ходит в сеть
        отказ = None
        try:
            р = АДАПТЕРЫ[поставщик](mal)
        except TransportError as e:
            р, отказ, ошибок = None, str(e), ошибок + 1
        except Exception as e:            # noqa: BLE001
            р, отказ, ошибок = None, type(e).__name__, ошибок + 1
        исход = ("MATCHED" if р else
                 "PROVIDER_ERROR" if отказ else "PROVIDER_NO_RATING")
        if отказ and ошибок > 20:
            соед.commit()
            return {"provider": поставщик, "enabled": True, "matched": ок,
                    "providerNoRating": нет, "errors": ошибок,
                    "abortedReason": отказ, "withMalId": len(карта),
                    "matchMethod": "id:mal", "ambiguous": 0,
                    "note": "остановлено: источник недоступен, не «нет оценок»"}
        соед.execute(
            "INSERT INTO rating_match(entity_id, provider, provider_entity_id, "
            "match_method, match_confidence, outcome, reason, updated_at) "
            "VALUES(?,?,?,'id:mal',1.0,?,?,?) "
            "ON CONFLICT(entity_id, provider) DO UPDATE SET "
            "provider_entity_id=excluded.provider_entity_id, "
            "outcome=excluded.outcome, updated_at=excluded.updated_at",
            (ид, поставщик, (р or {}).get("provider_entity_id"), исход,
             отказ or (None if р else "источник не отдал оценку"), т))
        if р:
            соед.execute(
                "INSERT INTO external_rating(entity_id, provider, external_id, "
                "value, scale, votes, fetched_at, source, status) "
                "VALUES(?,?,?,?,?,?,?,?,'OK') "
                "ON CONFLICT(entity_id, provider) DO UPDATE SET "
                "value=excluded.value, scale=excluded.scale, "
                "votes=excluded.votes, fetched_at=excluded.fetched_at, "
                "source=excluded.source, status='OK'",
                (ид, поставщик, р["provider_entity_id"], р["value"], р["scale"],
                 р.get("votes"), т, f"api:{поставщик}:{р.get('source_url','')}"))
            ок += 1
        else:
            нет += 1
        соед.commit()
        time.sleep(ПАУЗА.get(поставщик, 0.5))
    без_ключа = соед.execute("SELECT count(*) c FROM entity").fetchone()["c"] - len(карта)
    return {"provider": поставщик, "enabled": True, "matched": ок,
            "providerNoRating": нет, "errors": ошибок,
            "withMalId": len(карта), "unmatchedNoAnimeId": без_ключа,
            "matchMethod": "id:mal", "ambiguous": 0,
            "note": "fuzzy-сопоставление не выполняется; без mal id — UNMATCHED"}
