#!/usr/bin/env python3
"""Слепок витрины до и после выпуска: сравнивается то, что видит зритель.

Директива требует сравнить шесть величин: число записей, снимок контента,
идентификаторы и адреса тайтлов, глубину пагинации, выборку главной и покрытие
поставщиком плеера. Ни одну из них нельзя взять из отчёта сборки — отчёт
описывает намерение, а зритель видит страницы. Поэтому всё снимается
обращением к работающей витрине.

Два режима:

    --capture before   снять слепок до переключения
    --capture after    снять слепок после и сравнить с «до»

Сравнение не решает, хорошо это или плохо: оно показывает расхождения. Правило
одно и записано явно — исчезновение страниц и падение покрытия плеером
считаются отказом, а рост числа записей отказом не является: каталог живой и
между слепками растёт сам.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Чтение страниц стенда — общая реализация: две дословные копии расходились бы
# молча, и разные отчёты об одном стенде читались бы как разница витрин.
from stand_probe import fetch  # noqa: E402

OUT_DIR = ROOT / "artifacts" / "evidence" / "release"
PORTS = {"lords-01": 9101, "lords-02": 9102, "lords-03": 9103}
FINGERPRINTS = Path("/srv/site-factory/repo/var/lords/fingerprints")
TITLE_RE = re.compile(r'href="(/title/[^"]+)"')


def snapshot(site: str) -> dict:
    base = f"http://127.0.0.1:{PORTS[site]}"
    home_status, home = fetch(base, "/")
    cat_status, catalog = fetch(base, "/catalog/")

    pages = [int(x) for x in re.findall(r"/catalog/page/(\d+)/", catalog)]
    home_titles = TITLE_RE.findall(home)
    catalog_titles = TITLE_RE.findall(catalog)

    # Покрытие плеером снимается по выборке страниц тайтлов, а не по отчёту:
    # отчёт говорит, сколько записей помечены воспроизводимыми, а страница
    # показывает, есть ли на ней посадочное место плеера.
    sample = catalog_titles[:15]
    with_player, checked, missing = 0, 0, []
    for path in sample:
        status, html = fetch(base, path)
        if status != 200:
            missing.append(path)
            continue
        checked += 1
        if "player" in html:
            with_player += 1

    fp_path = FINGERPRINTS / f"{site}.json"
    fingerprint = json.loads(fp_path.read_text(encoding="utf-8")) if fp_path.is_file() else {}

    return {
        "captured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "site_id": site,
        "base": base,
        "home": {"status": home_status, "bytes": len(home), "titles": len(home_titles),
                 "title_paths": sorted(home_titles)},
        "catalog": {"status": cat_status, "titles": len(catalog_titles),
                    "title_paths": sorted(catalog_titles),
                    "max_page": max(pages) if pages else None},
        "player_coverage": {"checked": checked, "with_player": with_player,
                            "unreachable": missing,
                            "ratio": round(with_player / checked, 4) if checked else None},
        "content_snapshot": {
            "catalog": fingerprint.get("catalog"),
            "enrichment": fingerprint.get("enrichment"),
            "playability": fingerprint.get("playability"),
            "template_version": fingerprint.get("template_version"),
        },
        "data_source_label": (re.search(
            r'<meta name="lords-data-source" content="([^"]*)"', home) or [None, None])[1]
        if home_status == 200 else None,
    }


def compare(before: dict, after: dict) -> dict:
    findings = []
    b_cat, a_cat = before["catalog"], after["catalog"]

    lost = set(b_cat["title_paths"]) - set(a_cat["title_paths"])
    gained = set(a_cat["title_paths"]) - set(b_cat["title_paths"])
    if lost:
        findings.append({"severity": "fail", "what": "страницы каталога исчезли",
                         "count": len(lost), "examples": sorted(lost)[:5]})
    if b_cat["max_page"] and a_cat["max_page"] and a_cat["max_page"] < b_cat["max_page"]:
        findings.append({"severity": "fail", "what": "глубина пагинации уменьшилась",
                         "before": b_cat["max_page"], "after": a_cat["max_page"]})
    bp, ap = before["player_coverage"]["ratio"], after["player_coverage"]["ratio"]
    if bp is not None and ap is not None and ap < bp:
        findings.append({"severity": "fail", "what": "покрытие плеером упало",
                         "before": bp, "after": ap})
    if after["home"]["status"] != 200 or a_cat["status"] != 200:
        findings.append({"severity": "fail", "what": "главная или каталог не отвечают 200",
                         "home": after["home"]["status"], "catalog": a_cat["status"]})
    # Рост каталога отказом не является: источник живой.
    if gained:
        findings.append({"severity": "info", "what": "в каталоге появились страницы",
                         "count": len(gained)})
    if before["data_source_label"] != after["data_source_label"]:
        findings.append({"severity": "info", "what": "метка происхождения данных изменилась",
                         "before": before["data_source_label"],
                         "after": after["data_source_label"]})
    return {
        "verdict": "FAIL" if any(f["severity"] == "fail" for f in findings) else "PASS",
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default="lords-02", choices=sorted(PORTS))
    parser.add_argument("--capture", required=True, choices=("before", "after"))
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"release-{args.capture}.{args.site}.json"
    data = snapshot(args.site)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{path.relative_to(ROOT)} снят")
    print(f"  главная {data['home']['status']}, тайтлов на ней {data['home']['titles']}")
    print(f"  каталог {data['catalog']['status']}, тайтлов {data['catalog']['titles']}, "
          f"страниц {data['catalog']['max_page']}")
    print(f"  плеер: {data['player_coverage']['with_player']} из "
          f"{data['player_coverage']['checked']}")
    print(f"  снимок каталога: {(data['content_snapshot']['catalog'] or '')[:16]}")
    print(f"  метка происхождения: {data['data_source_label']}")

    if args.capture == "after":
        before_path = OUT_DIR / f"release-before.{args.site}.json"
        if not before_path.is_file():
            print("\n  слепка «до» нет — сравнивать не с чем")
            return 1
        result = compare(json.loads(before_path.read_text(encoding="utf-8")), data)
        out = OUT_DIR / f"release-comparison.{args.site}.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        print(f"\n  вердикт сравнения: {result['verdict']}")
        for f in result["findings"]:
            print(f"    [{f['severity']}] {f['what']}")
        return 0 if result["verdict"] == "PASS" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
