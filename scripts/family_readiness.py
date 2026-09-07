#!/usr/bin/env python3
"""Готовность пяти семейств шаблонов по девяти измерениям.

Рубрика одна на все циклы этапа и не меняется между прогонами: знаменатель,
пороги и набор измерений зафиксированы здесь. Менять их ради роста процента
запрещено прямо, и это не формальность — подвижная рубрика превращает отчёт о
готовности в отчёт о выборе рубрики.

Средняя по пяти семействам печатается последней и намеренно не выделяется:
Lords не должен прикрывать отставание остальных, поэтому семейство считается
отдельно и печатается отдельно.

Разделение, без которого число лгало бы. **Готовность пакета** — то, что можно
доказать в репозитории: схема, адаптер, отрисовка, браузер, доступность.
**Приёмка боевой витрины** — то, что доказывается только на настоящем домене с
настоящим окружением. Второе не выводится из первого ни при каких условиях, и
фикстурный прогон в него не засчитывается. Отсутствующий домен, окружение,
секрет или разрешение владельца дают `BLOCKED`, а не PASS.

Запуск:
    .venv/bin/python scripts/family_readiness.py [--json]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "artifacts" / "evidence" / "templates" / "family-readiness.json"
EVIDENCE = ROOT / "artifacts" / "evidence" / "templates"

#: Семейство → витрины, которые его несут. Соответствие снято из пакетов
#: (`tenant.theme`), а не назначено здесь.
FAMILIES: dict[str, tuple[str, ...]] = {
    "lords_dark": ("lords-01", "lords-02"),
    "lords_light": ("lords-03", "lords-04"),
    "portal_light": ("site-a",),
    "pulse": ("site-b",),
    "editorial": ("site-c",),
}

#: Девять измерений. Вес одинаковый: ни одно из них не важнее остальных
#: настолько, чтобы это можно было обосновать числом.
DIMENSIONS = (
    ("package", "готовность пакета"),
    ("adapter", "адаптер админки"),
    ("content", "содержимое и данные"),
    ("ssr", "отрисовка без JavaScript"),
    ("browser", "браузерные проверки"),
    ("a11y", "доступность"),
    ("visual", "визуальный эталон"),
    ("admin_preview", "предпросмотр и сборка"),
    ("live", "приёмка боевой витрины"),
)

MAX = 10


def _package(site: str) -> dict:
    path = ROOT / "sites" / site / "package.yaml"
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load(name: str):
    path = EVIDENCE / name
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — повреждённое свидетельство не свидетельство
        return None


def score_package(site: str, pkg: dict) -> tuple[int, str]:
    if not pkg:
        return 0, "пакета нет"
    result = subprocess.run(
        [sys.executable, "-m", "factory", "validate", "--site", site],
        capture_output=True, text=True, cwd=ROOT)
    if result.returncode == 0:
        return MAX, "схема и семантика пакета: exit 0"
    tail = (result.stdout or result.stderr).strip().splitlines()
    return 4, f"validate exit {result.returncode}: {tail[-1][:80] if tail else '—'}"


def score_adapter(site: str, pkg: dict) -> tuple[int, str]:
    """Адаптер админки: объявлен в манифесте и доказан потреблением.

    Одного объявления мало. Версия в пакете — это обещание; доказательством
    служит прогон, показавший, что отданное админкой доходит до страницы, что
    витрины не видят настроек друг друга и что пустая настройка не подменяется
    выдуманным текстом. Без прогона объявление остаётся бумагой.
    """
    admin = (pkg.get("admin") or {}) if isinstance(pkg.get("admin"), dict) else {}
    contract = admin.get("contract") or admin.get("adapter")
    if not contract:
        return 0, "контракт site-admin в пакете не объявлен"
    if not str(contract).startswith("site-admin/"):
        return 3, f"контракт объявлен нестандартно: {contract}"
    evidence = _load("admin-contract.json")
    if not evidence:
        return 5, f"контракт объявлен ({contract}), потребление не проверено"
    isolation = evidence.get("isolation") or []
    leaks = [x for entry in isolation for x in (entry.get("leaks") or [])]
    consumption = evidence.get("consumption") or []
    if leaks:
        return 4, f"утечки между витринами: {len(leaks)}"
    if not consumption:
        return 5, f"контракт объявлен ({contract}), потребление не измерено"
    return MAX, (f"{contract}: потребление проверено на {len(consumption)} витринах, "
                 f"утечек нет")


def score_content(site: str, pkg: dict) -> tuple[int, str]:
    source = pkg.get("content_source") or {}
    kind = str(source.get("kind") or "")
    if kind == "cdnvideohub":
        cache = Path("/srv/site-factory/repo/var/lords/lords/catalog-cache") / f"{site}.json"
        if cache.is_file():
            try:
                raw = json.loads(cache.read_text(encoding="utf-8"))
                count = len(raw.get("items") if isinstance(raw, dict) else raw)
            except Exception:  # noqa: BLE001
                return 5, "снимок живого каталога нечитаем"
            return MAX, f"живой источник, снимок {count} записей"
        return 4, "живой источник объявлен, снимка нет"
    if kind == "fixture":
        # Ссылка на набор объявлена на верхнем уровне пакета, а не внутри
        # `content_source`: первая редакция признака искала её не там и
        # показывала «файла нет» при существующем файле.
        ref = pkg.get("content_package_ref") or source.get("content_package_ref")
        path = ROOT / "sites" / site / str(ref) if ref else None
        if not (path and path.is_file()):
            return 2, "источник fixture объявлен, файла нет"
        declared = pkg.get("content_package_sha256") or source.get("content_package_sha256")
        import hashlib

        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if declared and declared != actual:
            return 3, f"отпечаток набора не сошёлся: объявлен {str(declared)[:12]}…"
        try:
            records = len((json.loads(path.read_text(encoding="utf-8")) or {}).get("titles") or [])
        except Exception:  # noqa: BLE001
            return 4, "набор нечитаем"
        # Синтетика проверяет путь, но боевыми данными не является и полного
        # балла не даёт: приёмка витрины считается отдельным измерением.
        return 6, f"набор на месте, {records} записей, отпечаток сошёлся"
    return 0, "источник содержимого не объявлен"


#: Семейства, живущие на движке payload-next-multisite. Их страницы собирает
#: не статический рендерер Lords, а компоненты приложения; полный запуск
#: приложения требует базы и секретов Payload, недоступных этой полосе, и
#: потому измеряется слой шаблонов — серверная отрисовка настоящих компонентов
#: настоящими стилями.
MULTISITE = {"portal_light", "pulse", "editorial"}
FAMILY_STAND = (ROOT / "blueprints" / "payload-next-multisite" / "app"
                / "var" / "family-stand")


def _family_stand_page(family: str) -> Path | None:
    path = FAMILY_STAND / f"{family}.html"
    return path if path.is_file() else None


def score_ssr_multisite(family: str) -> tuple[int, str]:
    """Серверная отрисовка слоя шаблонов: страница собрана без единой строки JS."""
    page = _family_stand_page(family)
    if page is None:
        return 0, "стенд семейства не собран"
    html = page.read_text(encoding="utf-8")
    cards = html.count('class="card"')
    # Разметка структурированных данных — не исполняемый скрипт: она ничего не
    # выполняет и содержимое страницы не строит. Первая редакция признака
    # считала её скриптом и снижала оценку за честную разметку.
    import re as _re

    executable = [m for m in _re.findall(r"<script[^>]*>", html)
                  if "application/ld+json" not in m]
    if executable:
        return 6, f"{cards} карточек, но в разметке есть исполняемый скрипт"
    if cards < 4:
        return 4, f"страница собрана, карточек всего {cards}"
    return MAX, f"страница собрана на сервере: {cards} карточек, скриптов нет"


def score_ssr(site: str) -> tuple[int, str]:
    """Отрисовка без единой строки JavaScript: страницы собираются на сервере."""
    code = (
        "import sys; sys.path.insert(0, %r)\n"
        "from factory.lords import preview as p, render as r, fixtures as fx\n"
        "pkg, _ = p._package(%r)\n"
        "site = r.render_site(pkg, catalog=fx.build_catalog(), environ={})\n"
        "html = [x for x in site.pages.values() if x.content_type.startswith('text/html')]\n"
        "print(len(site.pages), len(html))\n" % (str(ROOT), site)
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT)
    if result.returncode != 0:
        tail = (result.stderr or "").strip().splitlines()
        return 0, f"отрисовка падает: {tail[-1][:80] if tail else '—'}"
    total, html = (int(x) for x in result.stdout.split())
    if html < 10:
        return 4, f"страниц мало: {html} документов"
    return MAX, f"{total} страниц, из них {html} документов"


def score_browser(family: str, sites: tuple[str, ...]) -> tuple[int, str]:
    report = _load("playwright-lords-cross.json")
    if family in MULTISITE:
        families_run = ROOT / "var" / "artifacts" / "playwright-families.json"
        if not families_run.is_file():
            return 0, "браузерных прогонов на этом семействе нет"
        try:
            data = json.loads(families_run.read_text(encoding="utf-8"))
            expected = data.get("stats", {}).get("expected", 0)
            unexpected = data.get("stats", {}).get("unexpected", 0)
        except Exception:  # noqa: BLE001
            return 3, "свидетельство прогона нечитаемо"
        if unexpected:
            return 4, f"прогон с отказами: {unexpected}"
        # Полного балла нет намеренно: проверен слой шаблонов на стенде, а не
        # витрина в боевом окружении. Приёмка витрины считается отдельно.
        return 8, f"Chromium и Firefox, {expected} проверок без отказов (стенд семейств)"
    lords = family.startswith("lords_")
    if not lords:
        return 0, "браузерных прогонов на этом семействе нет"
    main = ROOT / "var" / "artifacts" / "playwright-lords.json"
    passed = 0
    if main.is_file():
        try:
            data = json.loads(main.read_text(encoding="utf-8"))
            passed = data.get("stats", {}).get("expected", 0)
        except Exception:  # noqa: BLE001
            passed = 0
    cross = (report or {}).get("stats", {}).get("expected", 0) if report else 0
    if passed and cross:
        return MAX, f"Chromium {passed}, Firefox+WebKit {cross}"
    if passed:
        return 7, f"Chromium {passed}; кросс-браузерных свидетельств нет"
    return 3, "свидетельств браузерного прогона нет"


def score_a11y(family: str) -> tuple[int, str]:
    runs = sorted((EVIDENCE / "a11y").glob("axe-*.json"))
    if not runs:
        return 0, "прогонов axe нет"
    if family in MULTISITE:
        relevant = [f for f in runs if f.name.startswith(f"axe-family-{family}-")]
    else:
        relevant = [f for f in runs if family.startswith("lords_") and "lords-" in f.name]
    if not relevant:
        return 0, "прогонов axe на этом семействе нет"
    violations = 0
    for f in relevant:
        try:
            violations += len(json.loads(f.read_text(encoding="utf-8")).get("violations", []))
        except Exception:  # noqa: BLE001
            return 5, "свидетельство axe нечитаемо"
    if violations:
        return 3, f"{len(relevant)} прогонов, нарушений {violations}"
    return MAX, f"{len(relevant)} прогонов WCAG 2.2 AA, нарушений нет"


def score_visual(family: str) -> tuple[int, str]:
    if family in MULTISITE:
        identity = _load("family-identity.json")
        if not identity:
            return 0, "измерений облика семейства нет"
        rows = [k for k in (identity.get("families") or {}) if k.startswith(f"{family}@")]
        pairs = [p for p in (identity.get("distinctness") or []) if family in p.get("pair", [])]
        if not rows:
            return 0, "измерений облика этого семейства нет"
        if not pairs:
            return 5, f"{len(rows)} измерений, различие с соседями не проверено"
        worst = min(len(p["differing"]) for p in pairs)
        # Эталон раскладки как таковой у этих семейств ещё не заведён, поэтому
        # полного балла нет: измерен облик и его отличие от соседей.
        return 8, (f"{len(rows)} измерений на трёх ширинах; расхождение с соседями "
                   f"не менее {worst} признаков из девяти")
    baseline = ROOT / "tests" / "e2e-lords" / "visual-baseline.json"
    if not baseline.is_file():
        return 0, "эталона раскладки нет"
    if not family.startswith("lords_"):
        return 0, "эталона раскладки на этом семействе нет"
    try:
        data = json.loads(baseline.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return 3, "эталон нечитаем"
    rows = data.get("measurements") or {}
    return MAX, f"{len(rows)} измерений, допуск {data.get('tolerance_px')} px"


def score_admin_preview(site: str, family: str) -> tuple[int, str]:
    """Собирается ли витрина в вид, который можно показать до публикации."""
    if family in MULTISITE:
        pages = sorted(FAMILY_STAND.glob(f"{family}*.html")) if FAMILY_STAND.is_dir() else []
        if not pages:
            return 3, "стенд семейства не собран"
        surfaces = {p.stem.replace(f"{family}-", "") for p in pages}
        # Полного балла нет намеренно: собран предпросмотр слоя шаблонов, а не
        # путь оператора «правка → предпросмотр → согласование → публикация».
        # Тот путь живёт в админке, и он принадлежит другой полосе.
        return 8, (f"{len(pages)} страниц предпросмотра, поверхностей {len(surfaces)}; "
                   "путь публикации принадлежит админке")
    directory = ROOT / "artifacts" / "lords" / "preview" / site
    if directory.is_dir() and any(directory.glob("*")):
        return MAX, "предпросмотр собран"
    return 3, "собранного предпросмотра нет"


def score_live(site: str, pkg: dict) -> tuple[int, str]:
    """Приёмка боевой витрины. Ни одно фикстурное доказательство сюда не идёт."""
    domain = pkg.get("domain")
    if not domain:
        return 0, "BLOCKED: домен не задан владельцем"
    if str(domain).endswith((".localhost", ".localhost.test", ".test")):
        return 0, f"BLOCKED: {domain} — не боевой домен"
    if not pkg.get("production_authorized"):
        return 0, f"BLOCKED: production не авторизован в пакете ({domain})"
    current = Path("/srv/lords") / site / "current"
    if not current.exists():
        return 2, f"домен {domain} задан, выложенного релиза нет"
    return 6, f"релиз выложен, приёмка артефакта этой полосы не подтверждена"


def evaluate() -> dict:
    families = {}
    for family, sites in FAMILIES.items():
        per_site = {}
        for site in sites:
            pkg = _package(site)
            scores = {
                "package": score_package(site, pkg),
                "adapter": score_adapter(site, pkg),
                "content": score_content(site, pkg),
                "ssr": (score_ssr_multisite(family) if family in MULTISITE
                        else score_ssr(site)),
                "browser": score_browser(family, sites),
                "a11y": score_a11y(family),
                "visual": score_visual(family),
                "admin_preview": score_admin_preview(site, family),
                "live": score_live(site, pkg),
            }
            per_site[site] = {k: {"points": v[0], "note": v[1]} for k, v in scores.items()}
        # Семейство не сильнее своей слабейшей витрины: показывать среднее
        # значило бы прятать неготовую витрину за готовой соседкой.
        merged = {}
        for key, _label in DIMENSIONS:
            worst = min(per_site[s][key]["points"] for s in sites)
            note = next(per_site[s][key]["note"] for s in sites
                        if per_site[s][key]["points"] == worst)
            merged[key] = {"points": worst, "note": note}
        total = sum(m["points"] for m in merged.values())
        families[family] = {
            "sites": list(sites),
            "dimensions": merged,
            "per_site": per_site,
            "package_readiness": round(
                100 * sum(merged[k]["points"] for k, _ in DIMENSIONS if k != "live")
                / (MAX * (len(DIMENSIONS) - 1))),
            "live_acceptance": round(100 * merged["live"]["points"] / MAX),
            "total": round(100 * total / (MAX * len(DIMENSIONS))),
        }
    average = round(sum(f["total"] for f in families.values()) / len(families))
    return {
        "artifact": "TEMPLATE_FAMILY_READINESS",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "rubric": {k: v for k, v in DIMENSIONS},
        "max_per_dimension": MAX,
        "families": families,
        "average": average,
        "note": ("Готовность пакета и приёмка боевой витрины считаются отдельно. "
                 "Фикстурные проверки в приёмку не входят."),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = evaluate()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    names = list(FAMILIES)
    print(f"{'измерение':24}" + "".join(f"{n:>14}" for n in names))
    print("-" * (24 + 14 * len(names)))
    for key, label in DIMENSIONS:
        row = "".join(f"{report['families'][n]['dimensions'][key]['points']:>14}" for n in names)
        print(f"{label:24}{row}")
    print("-" * (24 + 14 * len(names)))
    print(f"{'ИТОГО, %':24}" + "".join(f"{report['families'][n]['total']:>14}" for n in names))
    print(f"{'  готовность пакета, %':24}"
          + "".join(f"{report['families'][n]['package_readiness']:>14}" for n in names))
    print(f"{'  приёмка витрины, %':24}"
          + "".join(f"{report['families'][n]['live_acceptance']:>14}" for n in names))
    print(f"\nсредняя по пяти семействам: {report['average']}%")
    print(f"{OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
