#!/usr/bin/env python3
"""Кандидаты для редакционной подборки: цепочка чисел и поимённый список.

ПОВОД — поручение владельца: «покажите короткую цепочку чисел: кандидаты →
соответствуют теме → доступны на сайте → включены», и отдельно: «пять карточек
в ряду не означает пять произведений во всей подборке».

ЧТО МЕРЯЕТ. Пул по снимку витрины, шаг за шагом, с числом на каждом шаге:
год, вид, объявленные серии, ПОЛНОТА серий (`avail` против `eps`),
воспроизводимость, первый ли это сезон, есть ли постер и описание. На выходе —
числа и поимённый список годных, который линия SEO разбирает редакционно.

ЧЕГО НЕ МЕРЯЕТ, и это главное ограничение: в снимке НЕТ даты эфира. Есть
`year` и `published_at` — дата появления на НАШЕМ сайте, а не выхода в эфир.
Поэтому «летний сезон», «завершён», «онгоинг» по снимку не определяются вовсе;
их источник внешний, и обращение к нему — не дело этого инструмента. Он
отвечает на вопрос «сколько у нас вообще есть пригодного», а не «что из этого
вышло летом».

Только чтение: снимок не правится.

    python3 automation/local/collection-candidates.py --site animedia-01 \
        [--year 2026] [--type tv] [--first-season] [--out-json f] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
if str(КОРЕНЬ) not in sys.path:
    sys.path.insert(0, str(КОРЕНЬ))

#: Где лежат снимки витрин. Читается, не пишется.
СНИМКИ = {
    "animedia-01": pathlib.Path("/srv/animedia-icu/data"),
    "animedia-02": pathlib.Path("/srv/animedia-space/data"),
    "zona-01": pathlib.Path("/srv/zonafilm-space/data"),
    "zona-03": pathlib.Path("/srv/zonafilm12-site/data"),
}


def снимок(site_id: str) -> tuple[list, dict]:
    каталог = СНИМКИ[site_id]
    файл_к = next(каталог.glob("*-catalog.json"))
    файл_д = next(каталог.glob("*-details.json"))
    к = json.loads(файл_к.read_text(encoding="utf-8"))
    записи = к.get("items") if isinstance(к, dict) else к
    д = json.loads(файл_д.read_text(encoding="utf-8"))
    return записи, (д.get("details") if isinstance(д, dict) else d) or {}


def сезоны(запись: dict, подробности: dict) -> list:
    return (подробности.get(запись.get("slug")) or {}).get("seasons") or []


def полные_серии(сез: list) -> bool:
    """Все объявленные серии доступны. Ноль серий полнотой не считается."""
    if not сез:
        return False
    return all((с.get("avail") or 0) >= (с.get("eps") or 0) > 0 for с in сез)


def цепочка(записи: list, подробности: dict, *, год: int | None,
            вид: str | None, первый_сезон: bool) -> tuple[list, list]:
    """(шаги, годные). Шаг — (название, число, что отсеялось)."""
    шаги = []
    текущие = list(записи)
    шаги.append(("всего в каталоге", len(текущие), ""))
    if год is not None:
        было = len(текущие)
        текущие = [з for з in текущие if з.get("year") == год]
        шаги.append((f"год {год}", len(текущие), f"−{было - len(текущие)}"))
    if вид:
        было = len(текущие)
        текущие = [з for з in текущие
                   if (подробности.get(з.get("slug")) or {}).get("type") == вид]
        шаги.append((f"type={вид}", len(текущие), f"−{было - len(текущие)}"))
    было = len(текущие)
    текущие = [з for з in текущие if сезоны(з, подробности)]
    шаги.append(("серии объявлены", len(текущие), f"−{было - len(текущие)}"))
    было = len(текущие)
    текущие = [з for з in текущие if полные_серии(сезоны(з, подробности))]
    шаги.append(("все серии доступны", len(текущие), f"−{было - len(текущие)}"))
    было = len(текущие)
    текущие = [з for з in текущие
               if (подробности.get(з.get("slug")) or {}).get("playable")]
    шаги.append(("воспроизводится", len(текущие), f"−{было - len(текущие)}"))
    if первый_сезон:
        было = len(текущие)
        текущие = [з for з in текущие
                   if max((с.get("n") or 0) for с in сезоны(з, подробности)) == 1]
        шаги.append(("первый сезон", len(текущие), f"−{было - len(текущие)}"))
    было = len(текущие)
    текущие = [з for з in текущие
               if (подробности.get(з.get("slug")) or {}).get("poster_url")
               or з.get("poster")]
    шаги.append(("есть постер", len(текущие), f"−{было - len(текущие)}"))
    return шаги, текущие


def описать(запись: dict, подробности: dict) -> dict:
    п = подробности.get(запись.get("slug")) or {}
    сез = сезоны(запись, подробности)
    оценка = None
    for ист, зн in (п.get("ratings_by_source") or {}).items():
        if isinstance(зн, dict) and зн.get("votes"):
            оценка = {"источник": ист,
                      "оценка": зн.get("rating") or зн.get("value"),
                      "голосов": зн.get("votes")}
            break
    return {
        "id": п.get("id"),
        "slug": запись.get("slug"),
        "название": запись.get("title"),
        "оригинал": п.get("original_name"),
        "год": запись.get("year"),
        "серий": sum((с.get("eps") or 0) for с in сез),
        "доступно серий": sum((с.get("avail") or 0) for с in сез),
        "жанры": (п.get("genres") or [])[:6],
        "описание есть": bool(п.get("description")),
        "оценка": оценка,
        "внешние": п.get("external_ids") or {},
        "адрес": запись.get("url") or f"/title/{запись.get('slug')}/",
    }


def главная(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("--site", required=True, choices=sorted(СНИМКИ))
    р.add_argument("--year", type=int, default=None)
    р.add_argument("--type", dest="вид", default=None,
                   help="tv или movie — по полю подробностей")
    р.add_argument("--first-season", action="store_true")
    р.add_argument("--limit", type=int, default=0,
                   help="сколько годных печатать (0 — все)")
    р.add_argument("--out-json", default="")
    а = р.parse_args(аргв)
    записи, подробности = снимок(а.site)
    шаги, годные = цепочка(записи, подробности, год=а.year, вид=а.вид,
                           первый_сезон=а.first_season)
    print(f"цепочка по снимку {а.site}:")
    for имя, число, убыль in шаги:
        print(f"   {имя:<24} {число:>6} {убыль}")
    список = [описать(з, подробности) for з in годные]
    список.sort(key=lambda к: (-(к["оценка"] or {}).get("голосов", 0),
                               -(к["серий"] or 0), к["название"] or ""))
    с_оценкой = sum(1 for к in список if к["оценка"])
    с_описанием = sum(1 for к in список if к["описание есть"])
    print(f"\nгодных: {len(список)} | с оценкой и числом голосов: {с_оценкой}"
          f" | с описанием: {с_описанием}")
    print("ВАЖНО: даты эфира в снимке нет — «сезон» и «завершён» отсюда не "
          "определяются, их источник внешний.")
    показать = список[:а.limit] if а.limit else список
    for к in показать:
        о = к["оценка"]
        метка = (f"{о['оценка']}/{о['голосов']}" if о else "—")
        print(f"   {(к['название'] or '')[:44]:<46} серий {к['серий']:>3} "
              f"| оценка {метка:<12} | {к['slug']}")
    if а.out_json:
        pathlib.Path(а.out_json).write_text(
            json.dumps({"витрина": а.site,
                        "цепочка": [{"шаг": и, "число": ч, "убыль": у}
                                    for и, ч, у in шаги],
                        "годных": len(список), "кандидаты": список},
                       ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"\nотчёт: {а.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(главная())
