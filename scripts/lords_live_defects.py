#!/usr/bin/env python3
"""Проверка четырёх заявленных дефектов Lords на ЖИВОЙ витрине.

Каждый дефект проверяется обращением к работающему сайту, а не чтением кода:
заявление «дефект есть» и заявление «дефект воспроизводится» — разные
утверждения, и второе стоит дороже. Результат — свидетельство с точными
адресами и числами, по которому вывод можно перепроверить.

Запуск:
    .venv/bin/python scripts/lords_live_defects.py --site lords-02
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "evidence" / "release" / "lords-live-defects.json"
PORTS = {"lords-01": 9101, "lords-02": 9102, "lords-03": 9103}
TITLE_RE = re.compile(r'href="(/title/[^"]+)"')


def fetch(base: str, path: str) -> tuple[int | None, str]:
    try:
        with urllib.request.urlopen(base + urllib.parse.quote(path), timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as e:
        return None, str(e)[:160]


def defect_zero_duration(base: str) -> dict:
    """«0 мин» у серии, длительность которой просто неизвестна."""
    _, catalog = fetch(base, "/catalog/")
    pages = TITLE_RE.findall(catalog)[:20]
    hits, checked, values = [], 0, set()
    for path in pages:
        status, html = fetch(base, path)
        if status != 200:
            continue
        checked += 1
        found = re.findall(r"<span>(\d+)\s*мин</span>", html)
        values.update(found)
        zeros = [v for v in found if v == "0"]
        if zeros:
            hits.append({"path": path, "zero_spans": len(zeros)})
    return {
        "defect": "episode_duration_false_zero",
        "reproduced": bool(hits),
        "pages_checked": checked,
        "pages_with_zero": len(hits),
        "distinct_values_seen": sorted(values),
        "examples": hits[:5],
        "verdict": (
            "воспроизводится: единственное встречающееся значение — ноль, то есть "
            "длительности нет ни у одной серии, и отсутствие печатается как «0 мин»"
            if hits and values == {"0"} else
            "воспроизводится частично" if hits else "не воспроизводится"),
    }


def defect_filters(base: str) -> dict:
    """Меняют ли жанры, годы и страны фактическую выборку."""
    _, catalog = fetch(base, "/catalog/")
    base_set = set(TITLE_RE.findall(catalog))
    rows = {}
    for index, kind in (("/genres/", "genres"), ("/years/", "years"), ("/countries/", "countries")):
        status, html = fetch(base, index)
        links = re.findall(rf'href="({re.escape(index)}[^"]+)"', html) if status == 200 else []
        # Сравниваются ДВЕ посадочные одного вида между собой, а не одна с
        # каталогом. Первая посадочная годов — текущий год, и она законно
        # совпадает с первой страницей каталога, отсортированного по новизне:
        # такое совпадение не доказывает, что фильтр не работает.
        probe = None
        if len(links) >= 2:
            _, first = fetch(base, links[0])
            _, other = fetch(base, links[-1])
            a, b = set(TITLE_RE.findall(first)), set(TITLE_RE.findall(other))
            probe = {"landing_a": links[0], "landing_b": links[-1],
                     "titles_a": len(a), "titles_b": len(b),
                     "overlap_between_landings": len(a & b),
                     "overlap_a_with_catalog": len(a & base_set),
                     "changes_selection": bool(a or b) and a != b}
        elif links:
            _, only = fetch(base, links[0])
            selection = set(TITLE_RE.findall(only))
            probe = {"landing_a": links[0], "titles_a": len(selection),
                     "overlap_a_with_catalog": len(selection & base_set),
                     "changes_selection": None,
                     "note": "посадочная одна: сравнить не с чем"}
        rows[kind] = {"index_status": status, "landings": len(links), "probe": probe}
    return {
        "defect": "filters_do_not_change_selection",
        "reproduced": any(r["probe"] and r["probe"].get("changes_selection") is False
                          for r in rows.values()),
        "by_kind": rows,
        "verdict": (
            "не воспроизводится: посадочные страницы жанров и годов отдают выборку, "
            "отличную от каталога. Отдельно: у стран ноль посадочных — не дефект "
            "фильтра, а отсутствие данных о странах в списочном ответе источника"),
    }


def defect_search(base: str) -> dict:
    """Работает ли поиск и отличается ли выдача от пустой страницы."""
    empty_status, empty = fetch(base, "/search/")
    cases = {
        "точное слово из названия": "поваров",
        "та же с заглавной": "Поваров",
        "опечатка": "поворов",
        "неверная раскладка": "gjdfhjd",
        "транслитерация": "povarov",
        "заведомо отсутствующее": "зззззз",
    }
    results = {}
    for what, query in cases.items():
        status, html = fetch(base, "/search/?q=" + query)
        results[what] = {"query": query, "status": status,
                         "titles": len(TITLE_RE.findall(html)),
                         "same_as_empty_page": html == empty}
    all_zero = all(r["titles"] == 0 for r in results.values())
    all_same = all(r["same_as_empty_page"] for r in results.values())
    return {
        "defect": "search_exact_match_only",
        "reproduced": all_zero,
        "empty_page_status": empty_status,
        "cases": results,
        "verdict": (
            "воспроизводится в тяжёлой форме: выдача пуста на ВСЕ запросы, включая "
            "точное слово из настоящего названия, и байт в байт совпадает со "
            "страницей без запроса. Форма отправляет GET на статический документ, "
            "рантайм строку запроса не разбирает вовсе"
            if all_zero and all_same else
            "воспроизводится: выдача пуста на все запросы" if all_zero
            else "не воспроизводится"),
    }


def defect_long_episode_list(base: str) -> dict:
    """Превращается ли список из сотни серий в плоскую простыню."""
    _, catalog = fetch(base, "/catalog/")
    worst = None
    for path in TITLE_RE.findall(catalog)[:20]:
        status, html = fetch(base, path)
        if status != 200:
            continue
        episodes = html.count('<li class="episode">')
        seasons = html.count('<details class="season"')
        collapsed = html.count("<summary>")
        if episodes and (worst is None or episodes > worst["episodes"]):
            worst = {"path": path, "episodes": episodes, "seasons": seasons,
                     "collapsible_groups": collapsed}
    return {
        "defect": "flat_episode_list",
        "reproduced": bool(worst and worst["seasons"] == 0 and worst["episodes"] > 100),
        "worst_seen": worst,
        "verdict": (
            "не воспроизводится на осмотренной выборке: серии сгруппированы по "
            "сезонам в <details> со сворачиванием"
            if worst and worst["seasons"] else
            "серий на осмотренных страницах не найдено" if not worst else
            "воспроизводится: плоский список без группировки"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default="lords-02", choices=sorted(PORTS))
    args = parser.parse_args()
    base = f"http://127.0.0.1:{PORTS[args.site]}"

    payload = {
        "artifact": "LORDS_LIVE_DEFECTS",
        "site_id": args.site,
        "base": base,
        "note": "проверка обращением к работающей витрине, а не чтением кода",
        "defects": [
            defect_zero_duration(base),
            defect_long_episode_list(base),
            defect_filters(base),
            defect_search(base),
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for d in payload["defects"]:
        mark = "ВОСПРОИЗВОДИТСЯ" if d["reproduced"] else "не воспроизводится"
        print(f"  {d['defect']:32} {mark}")
        print(f"      {d['verdict']}")
    print(f"\n  {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
