#!/usr/bin/env python3
"""Готовность четырёх продуктов по восьми измерениям.

Рубрика одна на весь этап и не меняется между прогонами. Средняя цифра
печатается последней и намеренно не выделяется: продукт считается отдельно,
иначе сильный прикрывает слабый.

Разделение, без которого число лгало бы:

* **готовность пакета** — то, что доказуемо в репозитории;
* **приёмка предпросмотра** — витрина открывается и проходится;
* **приёмка боевой витрины** — доказывается только на настоящем домене с
  настоящим окружением. Из первых двух она не выводится ни при каких условиях,
  и ни фикстура, ни `localhost`, ни стенд в неё не засчитываются.

Соответствие продукт → пакет берётся из `scripts/product_map.py`: держать его
в двух местах значит рано или поздно развести.

Запуск:
    .venv/bin/python scripts/product_readiness.py [--json]
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

OUT = ROOT / "artifacts" / "evidence" / "products" / "product-readiness.json"
EVIDENCE = ROOT / "artifacts" / "evidence" / "products"
PREVIEW_ROOT = ROOT / "var" / "product-preview"

DIMENSIONS = (
    ("package", "готовность пакета"),
    ("data", "данные"),
    ("functional", "поиск, фильтры, навигация"),
    ("visual", "визуальная законченность"),
    ("responsive", "адаптивность и доступность"),
    ("preview", "предпросмотр"),
    ("adapter", "адаптер админки"),
    ("live", "приёмка боевой витрины"),
)

MAX = 10

#: Продукт → пакет. Совпадает с `scripts/product_map.py`.
PRODUCTS = {
    "zona-cinema": "zona-cinema-preview",
    "animedia-portal": "animedia-preview",
    "basis-video": "pilot-local",
    "yummy": None,
}


def _package(site: str | None) -> dict:
    if not site:
        return {}
    path = ROOT / "sites" / site / "package.yaml"
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _visual(product: str) -> dict | None:
    path = EVIDENCE / product / "visual-report.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def score_package(product: str, site: str | None, pkg: dict) -> tuple[int, str]:
    if site is None:
        return 0, "BLOCKED: пакета в этой фабрике нет — приложение в другом репозитории"
    if not pkg:
        return 0, f"пакета {site} нет в дереве"
    result = subprocess.run([sys.executable, "-m", "factory", "validate", "--site", site],
                            capture_output=True, text=True, cwd=ROOT)
    if result.returncode == 0:
        return MAX, "схема и семантика: exit 0"
    tail = (result.stdout or result.stderr).strip().splitlines()
    reason = tail[-1].strip()[:90] if tail else "—"
    return 4, f"validate exit {result.returncode}: {reason}"


def score_data(product: str, pkg: dict) -> tuple[int, str]:
    report = PREVIEW_ROOT / product / "preview-report.json"
    if not report.is_file():
        return 0, "предпросмотр не собран, данные не наблюдались"
    data = json.loads(report.read_text(encoding="utf-8"))
    provenance = data.get("data_provenance") or {}
    if provenance.get("source") == "fixture":
        # Синтетика проверяет путь, но продуктом не является: показывать
        # владельцу «Фикстура: материал 01» значит показывать оснастку.
        return 3, "синтетический набор: боевыми данными не является"
    records = provenance.get("records") or 0
    enriched = provenance.get("enriched") or 0
    if not records:
        return 2, "данных в предпросмотре нет"
    if records < 1000:
        return 6, f"{records} записей — срез, а не каталог"
    return MAX, (f"{records} записей боевого снимка, обогащено {enriched}; "
                 f"снимок витрины {provenance.get('snapshot_site')}")


def score_functional(product: str) -> tuple[int, str]:
    """Поиск, фильтры и навигация: проверено ли, что они меняют выдачу."""
    path = EVIDENCE / product / "functional-report.json"
    if not path.is_file():
        return 0, "работа поиска и фильтров не проверялась"
    data = json.loads(path.read_text(encoding="utf-8"))
    checks = data.get("checks") or []
    # `ok: null` — неприменимость, а не провал: серверный поиск в статической
    # выгрузке не работает по устройству, и требовать его здесь значит
    # требовать невозможного.
    failed = [c for c in checks if c.get("ok") is False]
    if not checks:
        return 0, "проверок нет"
    if failed:
        return 4, f"{len(failed)} из {len(checks)} проверок не прошли"
    return MAX, f"{len(checks)} проверок: поиск, фильтры, навигация, пагинация"


def score_visual(product: str) -> tuple[int, str]:
    report = _visual(product)
    if report is None:
        return 0, "снимки не сняты"
    pages = report.get("pages") or []
    if not pages:
        return 0, "снимков нет"
    issues = [p for p in pages if p.get("overflowX") or p.get("emptyElements")]
    console = report.get("consoleErrors") or []
    if issues:
        return 5, f"{len(issues)} страниц с пустыми элементами или прокруткой"
    if console:
        return 7, f"{len(console)} ошибок в консоли"
    surfaces = {p["page"] for p in pages}
    return MAX, f"{len(surfaces)} поверхностей на трёх ширинах, замечаний нет"


def score_responsive(product: str) -> tuple[int, str]:
    path = EVIDENCE / product / "a11y-report.json"
    if not path.is_file():
        return 0, "доступность и адаптивность не проверялись"
    data = json.loads(path.read_text(encoding="utf-8"))
    runs = data.get("runs") or []
    if not runs:
        return 0, "прогонов нет"
    violations = sum(len(r.get("violations") or []) for r in runs)
    if violations:
        return 4, f"{violations} нарушений на {len(runs)} прогонах"
    return MAX, f"{len(runs)} прогонов axe WCAG 2.2 AA без нарушений"


def score_preview(product: str) -> tuple[int, str]:
    directory = PREVIEW_ROOT / product
    if not (directory / "index.html").is_file():
        return 0, "предпросмотр не собран"
    documents = sum(1 for _ in directory.rglob("*.html"))
    plan = EVIDENCE / "preview-plan.json"
    url = None
    if plan.is_file():
        url = (json.loads(plan.read_text(encoding="utf-8")).get("products") or {}).get(product)
    if not url:
        return 6, f"{documents} страниц собрано, адрес владельцу не назначен"
    # Полного балла нет намеренно: собранный предпросмотр — не приёмка витрины.
    return 9, f"{documents} страниц, адрес {url}"


def score_adapter(product: str, pkg: dict) -> tuple[int, str]:
    admin = (pkg.get("admin") or {}) if isinstance(pkg.get("admin"), dict) else {}
    contract = admin.get("contract")
    if not contract:
        return 0, "контракт site-admin в пакете не объявлен"
    if not str(contract).startswith("site-admin/"):
        return 3, f"контракт объявлен нестандартно: {contract}"
    return 7, f"контракт объявлен ({contract}); потребление на этой витрине не проверено"


def score_live(product: str, pkg: dict) -> tuple[int, str]:
    domain = pkg.get("domain")
    if not domain:
        return 0, "BLOCKED: домен не задан владельцем"
    text = str(domain)
    if text.endswith((".localhost", ".localhost.test", ".test", ".invalid")):
        return 0, f"BLOCKED: {text} — не боевой домен"
    if not pkg.get("production_authorized"):
        return 0, f"BLOCKED: production не авторизован ({text})"
    return 2, f"домен {text} задан, приёмка не выполнялась"


def evaluate() -> dict:
    products = {}
    for product, site in PRODUCTS.items():
        pkg = _package(site)
        scores = {
            "package": score_package(product, site, pkg),
            "data": score_data(product, pkg),
            "functional": score_functional(product),
            "visual": score_visual(product),
            "responsive": score_responsive(product),
            "preview": score_preview(product),
            "adapter": score_adapter(product, pkg),
            "live": score_live(product, pkg),
        }
        dims = {k: {"points": v[0], "note": v[1]} for k, v in scores.items()}
        total = sum(d["points"] for d in dims.values())
        products[product] = {
            "package": site or "—",
            "dimensions": dims,
            "package_readiness": round(
                100 * sum(dims[k]["points"] for k, _ in DIMENSIONS if k != "live")
                / (MAX * (len(DIMENSIONS) - 1))),
            "preview_acceptance": round(100 * dims["preview"]["points"] / MAX),
            "live_acceptance": round(100 * dims["live"]["points"] / MAX),
            "total": round(100 * total / (MAX * len(DIMENSIONS))),
        }
    return {
        "artifact": "TEMPLATE_PRODUCT_READINESS",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "rubric": dict(DIMENSIONS),
        "max_per_dimension": MAX,
        "products": products,
        "average": round(sum(p["total"] for p in products.values()) / len(products)),
        "note": ("Приёмка боевой витрины не выводится из готовности пакета и "
                 "предпросмотра. Фикстура, localhost и стенд в неё не входят."),
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

    names = list(PRODUCTS)
    print(f"{'измерение':30}" + "".join(f"{n:>17}" for n in names))
    print("-" * (30 + 17 * len(names)))
    for key, label in DIMENSIONS:
        row = "".join(f"{report['products'][n]['dimensions'][key]['points']:>17}" for n in names)
        print(f"{label:30}{row}")
    print("-" * (30 + 17 * len(names)))
    for label, field in (("ИТОГО, %", "total"),
                         ("  готовность пакета, %", "package_readiness"),
                         ("  предпросмотр, %", "preview_acceptance"),
                         ("  приёмка витрины, %", "live_acceptance")):
        print(f"{label:30}" + "".join(f"{report['products'][n][field]:>17}" for n in names))
    print(f"\nсредняя по четырём продуктам: {report['average']}%")
    print(f"{OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
