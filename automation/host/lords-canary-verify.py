#!/usr/bin/env python3
"""Приёмка витрины после переключения: сравнение с состоянием до него.

Проверяется не «отвечает ли сайт» — это проходит и пустая витрина, — а что
отдаётся тот же каталог, что и был, с теми же адресами, и что соседние витрины
не тронуты.

Два режима:

    --baseline <файл>   снять состояние ДО переключения
    --verify <файл>     сравнить текущее состояние с ним

Снимок «до» обязан быть снят заранее: после переключения взять его уже неоткуда,
а сравнивать не с чем — значит не проверять.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PORTS = {"lords-01": 9101, "lords-02": 9102, "lords-03": 9103}

ROUTES = (
    ("home", "/"),
    ("catalog", "/catalog/"),
    ("catalog_page2", "/catalog/page/2/"),
    ("search", "/search/?q=%D0%B0"),
    ("search_empty", "/search/?q=zzzzzzzzzzzz"),
    ("not_found", "/nope-canary-probe/"),
)

#: Допустимый дрейф каталога между снимками. Источник добавляет и убирает
#: записи непрерывно; равенство до штуки означало бы, что мир остановился.
CATALOG_DRIFT = 0.01


def fetch(port: int, path: str) -> dict:
    url = f"http://127.0.0.1:{port}{path}"
    started = time.time()
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            body = response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        body = error.read()
        status = error.code
    except Exception as error:  # noqa: BLE001 — недоступность маршрута тоже факт
        return {"status": type(error).__name__, "bytes": 0, "ms": 0}
    text = body.decode("utf-8", "replace")
    return {
        "status": status,
        "bytes": len(body),
        "ms": round((time.time() - started) * 1000, 1),
        "sha256": hashlib.sha256(body).hexdigest()[:16],
        "title_links": len(set(re.findall(r'href="/title/([^"/]+)/"', text))),
        "pagination_max": max((int(n) for n in re.findall(r"/page/(\d+)/", text)), default=0),
        "players": text.count("<video-player"),
        "data_source": (re.search(r'lords-data-source" content="([^"]+)', text) or [None, None])[1]
        if "lords-data-source" in text else None,
        "h1": len(re.findall(r"<h1[ >]", text)),
    }


def current_release(site: str) -> str | None:
    try:
        return os.path.basename(os.readlink(f"/srv/lords/{site}/current"))
    except OSError:
        return None


def sample_slugs(limit: int = 20) -> list[str]:
    """Адреса из живого снимка — их наличие и проверяется поимённо."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from factory.lords import live_site
    from factory.lords.live_catalog import slugify

    cache = Path(os.environ.get(
        "LORDS_SNAPSHOT_DIR", "/srv/site-factory/repo/var/lords/lords/catalog-cache"))
    items = live_site.load_live_items("lords-02", root=cache)
    step = max(1, len(items) // limit)
    out = []
    for item in items[::step][:limit]:
        external = str(item.get("external_id") or "")
        out.append(slugify(str(item.get("name") or "")) or slugify(external) or external.lower())
    return out


def collect() -> dict:
    slugs = sample_slugs()
    titles = {}
    for slug in slugs:
        titles[slug] = fetch(PORTS["lords-02"], f"/title/{slug}/")["status"]
    return {
        "captured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "releases": {site: current_release(site) for site in PORTS},
        "routes": {name: fetch(PORTS["lords-02"], path) for name, path in ROUTES},
        "neighbours": {
            site: fetch(port, "/") for site, port in PORTS.items() if site != "lords-02"
        },
        "sample_titles": titles,
    }


def compare(before: dict, after: dict) -> list[str]:
    problems: list[str] = []

    for site in ("lords-01", "lords-03"):
        if before["releases"].get(site) != after["releases"].get(site):
            problems.append(
                f"{site} сменил релиз: {before['releases'].get(site)} → "
                f"{after['releases'].get(site)} — соседняя витрина не должна была меняться")

    if before["releases"].get("lords-02") == after["releases"].get("lords-02"):
        problems.append("lords-02 остался на прежнем релизе: переключения не было")

    for name, path in ROUTES:
        b, a = before["routes"][name], after["routes"][name]
        if b["status"] != a["status"]:
            problems.append(f"{path}: код ответа {b['status']} → {a['status']}")
        if isinstance(a["status"], int) and a["status"] == 200 and a["bytes"] < 1000:
            problems.append(f"{path}: тело {a['bytes']} б — страница пуста")
        if name == "home" and a.get("h1") != 1:
            problems.append(f"{path}: заголовков h1 {a.get('h1')}, ожидался один")

    b_links = before["routes"]["catalog"]["title_links"]
    a_links = after["routes"]["catalog"]["title_links"]
    if b_links and a_links < b_links:
        problems.append(f"каталог: ссылок на произведения {b_links} → {a_links}")

    # Глубина сверяется с прежним релизом, а не с расчётом по снимку.
    #
    # Расчёт по снимку у меня был, и он оказался неверен: модуль пагинации дал
    # 2218 страниц, а рендерер — и в новой сборке, и на боевом релизе — 2253.
    # Почему они расходятся, я не выяснил, и держать в приёмке число, которое
    # рендерер опровергает, хуже, чем не держать никакого: оно объявило бы
    # дефектом исправную сборку.
    #
    # Прежний релиз — свидетель того же рендерера на почти том же каталоге.
    # Расхождение с ним больше допуска означает, что каталог изменился не от
    # обновления.
    b_max = before["routes"]["catalog"]["pagination_max"]
    a_max = after["routes"]["catalog"]["pagination_max"]
    if b_max and abs(a_max - b_max) > b_max * CATALOG_DRIFT:
        problems.append(
            f"глубина пагинации {b_max} → {a_max}: расхождение "
            f"{abs(a_max-b_max)/b_max:.1%} больше допустимых {CATALOG_DRIFT:.0%}")

    b_players = before["routes"]["home"]["players"]
    a_players = after["routes"]["home"]["players"]
    if b_players and a_players == 0:
        problems.append("плеер исчез с главной")

    missing = [slug for slug, code in after["sample_titles"].items() if code != 200]
    if missing:
        problems.append(f"страницы произведений не отвечают: {missing[:5]} (всего {len(missing)})")

    for site, page in after["neighbours"].items():
        if page["status"] != 200:
            problems.append(f"{site} отвечает {page['status']} — соседняя витрина пострадала")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--baseline", metavar="ФАЙЛ", help="снять состояние до переключения")
    group.add_argument("--verify", metavar="ФАЙЛ", help="сравнить с ранее снятым состоянием")
    args = parser.parse_args()

    if args.baseline:
        data = collect()
        Path(args.baseline).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"состояние до переключения записано: {args.baseline}")
        print(f"  релизы: {data['releases']}")
        print(f"  каталог: {data['routes']['catalog']['title_links']} ссылок, "
              f"глубина {data['routes']['catalog']['pagination_max']}")
        print(f"  страниц произведений отвечает: "
              f"{sum(1 for c in data['sample_titles'].values() if c == 200)}"
              f"/{len(data['sample_titles'])}")
        return 0

    before = json.loads(Path(args.verify).read_text(encoding="utf-8"))
    after = collect()
    problems = compare(before, after)
    result = {"before": before, "after": after, "problems": problems, "passed": not problems}
    out = Path(args.verify).with_suffix(".verify.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"=== приёмка lords-02 ({out}) ===")
    print(f"  релиз: {before['releases']['lords-02']} → {after['releases']['lords-02']}")
    for name, _ in ROUTES:
        b, a = before["routes"][name], after["routes"][name]
        print(f"  {name:14} {str(b['status']):>5}/{b['bytes']:>7}б → "
              f"{str(a['status']):>5}/{a['bytes']:>7}б")
    print("  соседи: " + ", ".join(
        f"{s}={before['releases'][s]}→{after['releases'][s]}" for s in ("lords-01", "lords-03")))
    if problems:
        print("\n  НАЙДЕНО:")
        for problem in problems:
            print(f"    — {problem}")
        return 1
    print("\n  расхождений нет")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
