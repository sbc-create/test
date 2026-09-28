#!/usr/bin/env python3
"""Локальный кандидат витрины Lords — для визуальной работы, не для выкладки.

Собирается из того же закреплённого снимка каталога, что и остальные витрины,
тем же отрисовщиком и с той же политикой адресов. Ничего не выкладывает и
production не касается: пишет дерево в указанный каталог.

    python3 build_lords_candidate.py --site lords-02 --titles 400 --out var/lords-candidate
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(КОРЕНЬ))

from factory.lords import detail_enrichment as enrich_mod   # noqa: E402
from factory.lords import live_catalog as live_mod          # noqa: E402
from factory.lords import preview as preview_mod            # noqa: E402
from factory.lords import render as render_mod              # noqa: E402
from factory.lords import serve as serve_mod                # noqa: E402
from factory.lords import urlmap as um                      # noqa: E402

СНИМОК = pathlib.Path(
    "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-02.json")
ДЕТАЛИ = pathlib.Path("/srv/site-factory/repo/var/lords/detail-cache")


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--site", default="lords-02")
    р.add_argument("--titles", type=int, default=400,
                   help="сколько страниц произведений отрисовать; 0 — все")
    р.add_argument("--out", required=True)
    а = р.parse_args(аргв)

    начало = time.perf_counter()
    сырое = json.loads(СНИМОК.read_text(encoding="utf-8"))
    записи = сырое["items"] if isinstance(сырое, dict) else сырое
    детали, битые = enrich_mod.load_cached_details(ДЕТАЛИ)
    слитые, обогащено = enrich_mod.merge_cached(записи, детали)
    каталог = live_mod.catalog_from_live(слитые)
    пакет, _ = preview_mod._package(а.site)

    слаги = None
    if а.titles > 0:
        по_порядку = sorted(t.slug for t in каталог.titles)
        шаг = max(1, len(по_порядку) // а.titles)
        слаги = frozenset(по_порядку[::шаг][:а.titles])

    сайт = render_mod.render_site(
        пакет, catalog=каталог, environ={}, publisher_id="1",
        only_title_slugs=слаги, restrict_cards_to_rendered=слаги is not None)

    отрисованные = {а_[len("/title/"):].strip("/") for а_ in сайт.pages
                    if а_.startswith("/title/") and а_.count("/") == 3}
    карта = um.построить(отрисованные)

    # Переезды считает та же функция, что и у остальных витрин. Своя копия
    # здесь означала бы, что два одинаковых по смыслу правила разъедутся —
    # и разойдутся они молча, в редиректах, которых никто не проверяет.
    import importlib.util
    _спец = importlib.util.spec_from_file_location(
        "_сборщик_витрин", КОРЕНЬ / "scripts" / "build_product_preview.py")
    _сборщик = importlib.util.module_from_spec(_спец)
    _спец.loader.exec_module(_сборщик)
    ограниченный = каталог
    if слаги is not None:
        ограниченный = type(каталог)(
            titles=[t for t in каталог.titles if t.slug in слаги],
            collections=каталог.collections,
            _by_slug={t.slug: t for t in каталог.titles if t.slug in слаги})
    переезды, надгробия = _сборщик._переезды(ограниченный, карта)
    петли = [а for а, ц in переезды.items() if ц in переезды or ц == а]
    if петли:
        raise SystemExit(f"переезды образуют цепочку: {петли[:3]}")

    куда = pathlib.Path(а.out)
    if куда.exists() and (куда / "release-provisioned.marker").is_file():
        raise SystemExit(f"{куда}: срез уже провизионирован, перезапись запрещена")
    serve_mod.clear_directory(куда)
    итог = serve_mod.export(сайт, куда)
    (куда / "redirects.json").write_text(
        json.dumps({"version": "lords-redirects/1.0.0", "moved": переезды,
                    "tombstones": надгробия}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    (куда / "route-map.json").write_text(
        json.dumps(карта.в_словарь(), ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    отчёт = {"site": а.site, "redirects": len(переезды),
             "tombstones": len(надгробия), "catalog_records": len(слитые), "enriched": обогащено,
             "broken_detail_files": len(битые), "title_pages": len(карта.routes),
             "documents": len(сайт.pages), "files": len(итог["files"]),
             "route_map_sha256": карта.отпечаток, "root": str(куда),
             "seconds": round(time.perf_counter() - начало, 1),
             "not_acceptance": "локальный кандидат для визуальной работы; "
                               "выкладкой и приёмкой не является"}
    (куда / "candidate-report.json").write_text(
        json.dumps(отчёт, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(отчёт, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
