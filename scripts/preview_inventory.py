#!/usr/bin/env python3
"""Опись предпросмотров: что готово, а что ещё нет.

Директива требует по каждому предпросмотру назвать точный адрес, отпечатки,
снимок контента, готовые страницы и оставшиеся заглушки. Опись собирается
обращением к работающему стенду, а не чтением исходников: страница может
существовать в дереве и не отдаваться, и наоборот.

Готовой считается страница, которая отвечает 200, несёт заголовок и хоть
какое-то содержимое сверх каркаса. Всё остальное называется своим состоянием,
а не округляется до «готово».
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "artifacts" / "evidence" / "release" / "owner-preview.json"
OUT = ROOT / "artifacts" / "evidence" / "release" / "preview-inventory.json"
SHOTS = ROOT / "artifacts" / "evidence" / "release" / "preview-screenshots"

#: Маршруты, которым краткость положена по устройству. Страница «не найдено»
#: обязана быть короткой, и записывать её в недоделанные значило бы занижать
#: готовность так же неверно, как завышать.
BRIEF_BY_DESIGN = {"404/", "410/", "search/"}

#: Маршруты, которые проверяются у каждого семейства. Разные семейства строят
#: разные разделы — отсутствие маршрута не дефект, а факт устройства витрины.
ROUTES = {
    "zona-cinema": ["", "catalog/", "search/", "genres/", "years/", "countries/",
                    "new/", "movies/", "series/"],
    "animedia-portal": ["", "catalog/", "search/", "genres/", "years/", "countries/",
                        "new/", "schedule/", "movies/"],
    "basis-video": ["", "lekcii/", "search/", "news/", "collections/izbrannoe/",
                    "praktikum/", "legal/terms/", "404/", "410/"],
}


def probe(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            body = r.read().decode("utf-8", "replace")
            status, headers = r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        status, headers = e.code, dict(e.headers)
    except (urllib.error.URLError, OSError) as e:
        return {"status": None, "error": str(e)[:120]}

    main = re.search(r"<main.*?</main>", body, re.S)
    text = re.sub(r"<[^>]+>", " ", main.group(0) if main else body)
    words = len(text.split())
    h1 = re.findall(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    cards = body.count('class="card')
    return {
        "status": status,
        "bytes": len(body),
        "h1": re.sub(r"<[^>]+>", "", h1[0]).strip()[:60] if h1 else None,
        "words_in_main": words,
        "cards": cards,
        "robots_header": headers.get("X-Robots-Tag"),
        "robots_meta": (re.search(r'<meta name="robots" content="([^"]*)"', body)
                        or [None, None])[1],
        # «Готова» — отвечает, подписана и несёт содержимое сверх каркаса.
        # Порог в сорок слов выбран так, чтобы пустая страница с одним
        # заголовком и навигацией готовой не считалась.
        "ready": bool(status == 200 and h1 and words >= 40),
    }


def main() -> int:
    if not PLAN.is_file():
        print("нет карты предпросмотра: сначала запустите owner-preview-stand.py")
        return 1
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    base = plan["base"]

    families = {}
    for name, row in plan["families"].items():
        pages = {}
        for route in ROUTES.get(name, [""]):
            url = f"{base}/{name}/{route}"
            pages[route or "home"] = {"url": url, **probe(url)}
        ready = sorted(k for k, v in pages.items() if v.get("ready"))
        thin = sorted(k for k, v in pages.items()
                      if v.get("status") == 200 and not v.get("ready")
                      and k not in BRIEF_BY_DESIGN and f"{k}/" not in BRIEF_BY_DESIGN)
        brief = sorted(k for k, v in pages.items()
                       if v.get("status") == 200 and not v.get("ready")
                       and (k in BRIEF_BY_DESIGN or f"{k}/" in BRIEF_BY_DESIGN))
        absent = sorted(k for k, v in pages.items() if v.get("status") != 200)
        closed = all(v.get("robots_header") for v in pages.values() if v.get("status"))
        families[name] = {
            "url": row["url"],
            "root": row["root"],
            "pages_ready": ready,
            "pages_thin": thin,
            "pages_brief_by_design": brief,
            "pages_absent": absent,
            "indexing_closed_on_every_response": closed,
            "screenshots": sorted(p.name for p in SHOTS.glob(f"{name}-*.png"))
                           if SHOTS.is_dir() else [],
            "pages": pages,
        }

    payload = {
        "artifact": "PREVIEW_INVENTORY",
        "captured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base": base,
        "tunnel": plan["tunnel"],
        # Ни один из трёх шаблонов не имеет ни зарегистрированного siteId, ни
        # домена, ни живого источника контента. Это не предположение: реестр
        # Control API отвечает семью витринами, и ни одной из этих трёх в нём
        # нет. Поэтому у предпросмотров нет ни отпечатка артефакта, ни снимка
        # живого каталога — заполнять эти поля было бы выдумкой.
        "artifactDigest": None,
        "artifactDigestNote": "артефакт шаблона определён только для направления "
                              "lords; у этих трёх семейств артефакта нет",
        "contentSnapshot": None,
        "contentSnapshotNote": "живого источника нет: витрины собраны на фикстуре",
        "rollback": "остановка стенда предпросмотра; боевого состояния не затрагивает",
        "families": families,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for name, row in families.items():
        print(f"  {name}")
        print(f"      адрес: {row['url']}")
        print(f"      готовы ({len(row['pages_ready'])}): {', '.join(row['pages_ready']) or '—'}")
        print(f"      тонкие ({len(row['pages_thin'])}): {', '.join(row['pages_thin']) or '—'}")
        print(f"      кратки по устройству ({len(row['pages_brief_by_design'])}): "
              f"{', '.join(row['pages_brief_by_design']) or '—'}")
        print(f"      отсутствуют ({len(row['pages_absent'])}): "
              f"{', '.join(row['pages_absent']) or '—'}")
        print(f"      индексация закрыта на всех ответах: "
              f"{'да' if row['indexing_closed_on_every_response'] else 'НЕТ'}")
        print(f"      снимков: {len(row['screenshots'])}")
    print(f"\n  {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
