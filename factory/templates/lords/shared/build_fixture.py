#!/usr/bin/env python3
"""Фикстура каталога Lords для отрисовки шаблонных пакетов.

## Почему версия 2

Версия 1 читала только `lords-01-catalog.json` и на этом основании объявляла,
что в источнике нет ни жанров, ни стран, ни описаний, ни оценок, ни эпизодов.
Это был неверный вывод о данных, а не о шаблонах: каталог — плоский индекс
витрины, а весь состав записи лежит рядом, в `lords-01-details.json`. Там есть
`genres`, `countries`, `description`, `imdb_rating` с провенансом источника,
`seasons` с числом серий и доступностью, `premiere_date`, `duration`,
`recommendation_ids`.

Последствие ошибки было не косметическим. Пятьдесят шаблонов строились на семи
полях, и различать их было нечем, кроме цвета и порядка одинаковых полок.

## Что остаётся запрещённым

Обогащение — это присоединение того, что в источнике ЕСТЬ, по ключу записи.
Ничего не досочиняется:

* оценка показывается только вместе с источником и только если источник её
  подтверждает (`ratings_by_source`); «оценка без провенанса» в фикстуру не
  попадает;
* эпизод существует ровно настолько, насколько его подтверждает `seasons`:
  номер сезона, число серий и сколько из них доступно. Названий серий в
  источнике нет — и выдумывать их нельзя, страница обязана обойтись номером;
* подборка берётся из реального недельного снимка витрины, а не составляется
  по вкусу;
* отсутствие поля отмечается явно, чтобы проверка отличала «данных нет» от
  «шаблон забыл отрисовать».

## Постеры

Внешний хост постеров вне разрешённого периметра. Но витрина проксирует их
своим первым адресом `/poster/...`, и это локальная первичная служба. Поэтому
постеры берутся оттуда — настоящие изображения настоящих записей, без единого
внешнего запроса. Если служба недоступна, фикстура честно помечает
`poster_mode=absent`, и ядро отрисовки покажет запись без изображения, а не
подставит чужую картинку.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import urllib.error
import urllib.request

КАТАЛОГ = pathlib.Path("/srv/lords/.frontend/lords-01-catalog.json")
СОСТАВ = pathlib.Path("/srv/lords/.frontend/lords-01-details.json")
ПОДБОРКИ = pathlib.Path("/srv/lords/.frontend/lords-02-popular-weekly.json")
ВНЕШНИЙ_ПОСТЕР = "https://poster.cdnvideohub.com/"
ВИТРИНА = "http://127.0.0.1:9110"
ДОМЕН_ВИТРИНЫ = "lordserial33.biz"

_ТРАНСЛИТ = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def слаг(значение: str) -> str:
    буквы = "".join(_ТРАНСЛИТ.get(с, с) for с in (значение or "").lower())
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", буквы)).strip("-")


def _оценки(запись: dict) -> dict:
    """Оценка попадает в фикстуру только с доказанным источником.

    `imdb_rating` в составе записи может стоять и без подтверждения в
    `ratings_by_source`. Число без провенанса — это утверждение, за которое
    никто не отвечает, поэтому оно отбрасывается.
    """
    результат = {}
    for источник, тело in (запись.get("ratings_by_source") or {}).items():
        значение = _число(тело)
        if значение is None:
            continue
        результат[источник] = {
            "value": значение,
            "votes": тело.get("votes"),
            "provider": тело.get("provider"),
            "scale": тело.get("scale", 10.0),
            "retrieved_at": тело.get("retrieved_at"),
            "match_state": тело.get("match_state"),
        }
    return результат


def _число(тело: dict):
    """Оценка как число на шкале десяти. Нечисловое значение — не оценка."""
    значение = тело.get("value_on_ten")
    if значение is None:
        значение = тело.get("value")
    try:
        return round(float(значение), 1)
    except (TypeError, ValueError):
        return None


def _сезоны(запись: dict) -> list[dict]:
    сезоны = []
    for с in запись.get("seasons") or []:
        try:
            номер = int(с.get("n"))
        except (TypeError, ValueError):
            continue
        серий = с.get("eps")
        доступно = с.get("avail")
        сезоны.append({
            "n": номер,
            "eps": int(серий) if isinstance(серий, (int, float)) else None,
            "avail": int(доступно) if isinstance(доступно, (int, float)) else None,
        })
    return sorted(сезоны, key=lambda с: с["n"])


def собрать(каталог: pathlib.Path, состав: pathlib.Path, сколько: int) -> dict:
    сырой = json.loads(каталог.read_text(encoding="utf-8"))
    подробно = json.loads(состав.read_text(encoding="utf-8"))
    детали = подробно["details"]
    записи = сырой.get("items") or []

    # id → slug, чтобы «похожее» указывало на записи каталога, а не на uuid.
    по_id = {}
    for ключ, тело in детали.items():
        if тело.get("id"):
            по_id[тело["id"]] = ключ
    в_каталоге = {з["slug"] for з in записи}

    отобранные: list[str] = []
    for запись in записи:
        if len(отобранные) >= сколько:
            break
        if запись["slug"] in детали:
            отобранные.append(запись["slug"])

    # Краевые случаи берутся настоящие, а не сочинённые: если в выборку не
    # попал длинный заголовок или запись без постера — они добавляются явно.
    краевые = _краевые(записи, детали, отобранные)
    for slug in краевые.values():
        if slug and slug not in отобранные:
            отобранные.append(slug)

    # Настоящий недельный снимок витрины — единственная подборка, которую никто
    # не составлял руками. Его записи включаются в выборку целиком, иначе
    # подборка развалится на случайное пересечение и перестанет быть снимком.
    for slug in _слаги_снимка():
        if slug in детали and slug in в_каталоге and slug not in отобранные:
            отобранные.append(slug)

    по_slug = {з["slug"]: з for з in записи}
    items = []
    for slug in отобранные:
        к = по_slug[slug]
        д = детали.get(slug, {})
        сезоны = _сезоны(д)
        рекомендации = [по_id[i] for i in (д.get("recommendation_ids") or [])
                        if i in по_id and по_id[i] in в_каталоге][:12]
        items.append({
            "slug": slug,
            "title": к.get("title") or д.get("name"),
            "original_name": д.get("original_name"),
            "url": к.get("url") or f"/title/{slug}/",
            "year": к.get("year") or д.get("year"),
            "kind": к.get("kind"),
            "type": д.get("type"),
            "is_series": bool(д.get("is_series") or сезоны),
            "poster": к.get("poster"),
            "genres": list(д.get("genres") or []),
            "countries": list(д.get("countries") or []),
            "description": д.get("description"),
            "short_description": д.get("short_description"),
            "duration": д.get("duration"),
            "premiere_date": д.get("premiere_date"),
            "published_at": к.get("published_at"),
            "published_at_estimated": bool(к.get("published_at_estimated")),
            "ratings": _оценки(д),
            "seasons": сезоны,
            "seasons_count": д.get("seasons_count") or (len(сезоны) or None),
            "voice_studios": list(д.get("voice_studios") or [])[:4],
            "recommendations": рекомендации,
            "playable": bool(д.get("playable")),
        })

    return {
        "schema": "lords-template-fixture/2",
        "source": {
            # Имя файла и ревизия, но не абсолютный путь: провенанс от этого не
            # беднеет, а артефакт данных не начинает называть production-путь.
            # Запрет на такие пути в файлах пакета — не формальность: именно так
            # шаблон однажды и прирастает к конкретной машине.
            "catalog": каталог.name,
            "details": состав.name,
            "root": "первичный каталог витрины вне репозитория",
            "revision": сырой.get("revision", ""),
            "built_at": сырой.get("builtAt", ""),
            "catalog_count": сырой.get("count", len(записи)),
            "details_count": подробно.get("details_total", len(детали)),
        },
        "sample_size": len(items),
        "items": items,
        "taxonomies": _таксономии(items),
        "collections": _подборки(items),
        "edge_cases": краевые,
        "search": _поиск(items),
        "absent_fields": _отсутствующие(items),
        "poster_mode": "absent",
    }


def _слаги_снимка() -> list[str]:
    """Слаги недельного снимка витрины. Файла нет — подборки просто не будет."""
    if not ПОДБОРКИ.is_file():
        return []
    снимок = json.loads(ПОДБОРКИ.read_text(encoding="utf-8"))
    for тело in (снимок.get("shelves") or {}).values():
        return list(тело.get("slugs") or [])
    return []


def _краевые(записи: list[dict], детали: dict, уже: list[str]) -> dict:
    """Настоящие краевые записи каталога: длинный заголовок, нет постера и т.д."""
    окно = [з for з in записи[:8000] if з["slug"] in детали]
    без_постера = next((з["slug"] for з in окно if not з.get("poster")), None)
    длинный = max(окно, key=lambda з: len(з.get("title") or ""))["slug"] if окно else None
    без_описания = next(
        (з["slug"] for з in окно
         if not (детали[з["slug"]].get("description") or "").strip()), None)
    без_года = next((з["slug"] for з in окно if not з.get("year")), None)
    длинное_описание = max(
        окно, key=lambda з: len(детали[з["slug"]].get("description") or ""))["slug"] \
        if окно else None
    много_сезонов = max(
        (з for з in окно if детали[з["slug"]].get("seasons")),
        key=lambda з: len(детали[з["slug"]]["seasons"]), default=None)
    один_сезон = next(
        (з["slug"] for з in окно
         if len(детали[з["slug"]].get("seasons") or []) == 1), None)
    без_жанров = next(
        (з["slug"] for з in окно if not детали[з["slug"]].get("genres")), None)
    return {
        "long_title": длинный,
        "long_description": длинное_описание,
        "no_poster": без_постера,
        "no_description": без_описания,
        "no_year": без_года,
        "no_genres": без_жанров,
        "many_seasons": много_сезонов["slug"] if много_сезонов else None,
        "single_season": один_сезон,
    }


def _таксономии(items: list[dict]) -> dict:
    def свод(поле: str) -> list[dict]:
        счёт: dict[str, int] = {}
        for з in items:
            for значение in з.get(поле) or []:
                счёт[значение] = счёт.get(значение, 0) + 1
        return [{"name": и, "slug": слаг(и), "count": n}
                for и, n in sorted(счёт.items(), key=lambda п: (-п[1], п[0]))]

    годы: dict[int, int] = {}
    виды: dict[str, int] = {}
    for з in items:
        if з.get("year"):
            годы[з["year"]] = годы.get(з["year"], 0) + 1
        if з.get("kind"):
            виды[з["kind"]] = виды.get(з["kind"], 0) + 1
    return {
        "genres": свод("genres"),
        "countries": свод("countries"),
        "years": [{"name": str(г), "slug": str(г), "count": n}
                  for г, n in sorted(годы.items(), reverse=True)],
        "kinds": [{"name": в, "slug": слаг(в), "count": n}
                  for в, n in sorted(виды.items(), key=lambda п: -п[1])],
    }


def _подборки(items: list[dict]) -> list[dict]:
    """Подборки — только реально существующие срезы, с указанием происхождения."""
    свои = {з["slug"] for з in items}
    подборки = []
    if ПОДБОРКИ.is_file():
        снимок = json.loads(ПОДБОРКИ.read_text(encoding="utf-8"))
        for ключ, тело in (снимок.get("shelves") or {}).items():
            slugs = [s for s in тело.get("slugs") or [] if s in свои]
            if len(slugs) >= 4:
                подборки.append({
                    "key": "popular-weekly",
                    "title": "Популярное за неделю",
                    "provenance": f"недельный снимок витрины, {тело.get('week')}, "
                                  f"режим {тело.get('mode')}",
                    "slugs": slugs,
                })
                break
    # Жанровые срезы — не выдумка, а группировка по полю записи.
    по_жанру: dict[str, list[str]] = {}
    for з in items:
        for ж in з.get("genres") or []:
            по_жанру.setdefault(ж, []).append(з["slug"])
    for жанр, slugs in sorted(по_жанру.items(), key=lambda п: -len(п[1]))[:4]:
        if len(slugs) >= 6:
            подборки.append({
                "key": f"genre-{слаг(жанр)}",
                "title": жанр[:1].upper() + жанр[1:],
                "provenance": "срез каталога по полю genres записи",
                "slugs": slugs[:24],
            })
    return подборки


def _поиск(items: list[dict]) -> dict:
    """Запросы для проверки поиска: с результатами и заведомо пустой."""
    запросы = []
    for проба in ("сер", "1", "а"):
        совпало = [з["slug"] for з in items
                   if проба.lower() in (з.get("title") or "").lower()]
        if len(совпало) >= 3:
            запросы.append({"q": проба, "hits": совпало[:40]})
    return {
        "queries": запросы[:3],
        # Строка, которой заведомо нет ни в одном заголовке выборки.
        "empty_query": "щщщыъ",
    }


def _отсутствующие(items: list[dict]) -> dict:
    """Чего именно не хватает и у скольких записей — по факту, а не по памяти."""
    поля = ("poster", "description", "year", "genres", "countries",
            "duration", "premiere_date", "ratings", "seasons")
    свод = {}
    for поле in поля:
        нет = [з["slug"] for з in items if not з.get(поле)]
        свод[поле] = {"missing": len(нет), "of": len(items), "examples": нет[:3]}
    свод["episode_titles"] = {
        "missing": len(items), "of": len(items),
        "note": "названий серий в источнике нет ни у одной записи; "
                "страница эпизода обязана обходиться номером сезона и серии",
    }
    return свод


def скачать_постеры(фикстура: dict, каталог: pathlib.Path) -> dict:
    """Постеры берутся у первичной службы витрины по локальному адресу."""
    каталог.mkdir(parents=True, exist_ok=True)
    взято, нет = 0, []
    for запись in фикстура["items"]:
        адрес = запись.get("poster")
        if not адрес or not адрес.startswith(ВНЕШНИЙ_ПОСТЕР):
            нет.append(запись["slug"])
            continue
        имя = адрес[len(ВНЕШНИЙ_ПОСТЕР):]
        файл = каталог / имя
        if not файл.is_file():
            запрос = urllib.request.Request(
                f"{ВИТРИНА}/poster/{имя}", headers={"Host": ДОМЕН_ВИТРИНЫ})
            try:
                with urllib.request.urlopen(запрос, timeout=25) as ответ:
                    if ответ.status != 200:
                        нет.append(запись["slug"]); continue
                    файл.write_bytes(ответ.read())
            except (urllib.error.URLError, OSError, TimeoutError):
                нет.append(запись["slug"]); continue
        запись["poster_local"] = f"posters/{имя}"
        взято += 1
    фикстура["poster_mode"] = "first-party-proxy" if взято else "absent"
    фикстура["poster_stats"] = {
        "fetched": взято, "without": len(нет),
        "source": "первичная служба витрины по локальному адресу, маршрут /poster/",
    }
    return фикстура


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", default=str(КАТАЛОГ))
    parser.add_argument("--details", default=str(СОСТАВ))
    parser.add_argument("--count", type=int, default=120)
    parser.add_argument("--posters", help="каталог для локальных копий постеров")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    фикстура = собрать(pathlib.Path(args.catalog), pathlib.Path(args.details), args.count)
    if args.posters:
        фикстура = скачать_постеры(фикстура, pathlib.Path(args.posters))

    путь = pathlib.Path(args.out)
    путь.parent.mkdir(parents=True, exist_ok=True)
    путь.write_text(json.dumps(фикстура, ensure_ascii=False, indent=1), encoding="utf-8")
    т = фикстура["taxonomies"]
    print(f"фикстура/2: записей {фикстура['sample_size']}, жанров {len(т['genres'])}, "
          f"стран {len(т['countries'])}, годов {len(т['years'])}, "
          f"подборок {len(фикстура['collections'])}, "
          f"постеры {фикстура['poster_mode']} "
          f"({фикстура.get('poster_stats', {}).get('fetched', 0)}) → {путь}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
