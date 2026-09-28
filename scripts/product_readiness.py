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
    """Поиск, фильтры и навигация: проверено ли, что они меняют выдачу.

    Отдельный набор поиска, если он есть, входит в счёт: у basis-video поиск
    проверяется восемью сценариями в трёх движках — опечатка, чужая раскладка,
    «ё», бессмысленный запрос, адрес, поведение без скрипта, — и сводить это к
    одной строке «поиск отвечает» значило бы потерять предмет проверки.
    """
    path = EVIDENCE / product / "functional-report.json"
    if not path.is_file():
        return 0, "работа поиска и фильтров не проверялась"
    data = json.loads(path.read_text(encoding="utf-8"))
    search_report = EVIDENCE / product / "search-report.json"
    search_checks = 0
    if search_report.is_file():
        try:
            search_checks = len(json.loads(
                search_report.read_text(encoding="utf-8")).get("checks") or [])
        except Exception:  # noqa: BLE001
            search_checks = 0
    checks = data.get("checks") or []
    # `ok: null` — неприменимость, а не провал: серверный поиск в статической
    # выгрузке не работает по устройству, и требовать его здесь значит
    # требовать невозможного.
    failed = [c for c in checks if c.get("ok") is False]
    if not checks:
        return 0, "проверок нет"
    if failed:
        return 4, f"{len(failed)} из {len(checks)} проверок не прошли"
    подпись = f"{len(checks)} проверок: поиск, фильтры, навигация, пагинация"
    if search_checks:
        подпись += f"; отдельный набор поиска — {search_checks} сценариев"
    return MAX, подпись


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
    # Локальный стенд из оценки исключён: владелец решил, что приёмка идёт
    # только на настоящих адресах, и адрес вида `127.0.0.1` в неё не входит.
    # Здесь считается то, что от стенда не зависит: витрина **собирается** в
    # набор страниц, готовый к выкладке.
    return (9 if documents >= 20 else 6), (
        f"{documents} страниц собрано и готово к выкладке; "
        "локальная витрина в приёмку не входит")


def score_adapter(product: str, pkg: dict) -> tuple[int, str]:
    # У Yummy пакета в фабрике нет, и раздел админки взять неоткуда. Но слой
    # подключения существует: версионированный контракт потребителя, перечень
    # требований с владельцами и запрос недостающих входов. Считать это нулём
    # значило бы сказать, что работы нет, — а она есть и проверяема.
    if product == "yummy":
        try:
            from factory.yummy import adapter_contract as yummy

            assessment = yummy.assess()
        except Exception as error:  # noqa: BLE001
            return 0, f"контракт подключения нечитаем: {str(error)[:60]}"
        доля = len(assessment.satisfied) / max(len(assessment.requirements), 1)
        # Полного балла нет и быть не может: пакет не заведён, и заведён не
        # будет, пока владелец не назовёт домены, а Core — ветку.
        return round(6 * доля), (
            f"{yummy.CONTRACT_VERSION}: выполнено {len(assessment.satisfied)} требований "
            f"из {len(assessment.requirements)}; заблокировано "
            + ", ".join(r.key for r in assessment.blocked))

    admin = (pkg.get("admin") or {}) if isinstance(pkg.get("admin"), dict) else {}
    contract = admin.get("contract")
    if not contract:
        return 0, "контракт site-admin в пакете не объявлен"
    if not str(contract).startswith("site-admin/"):
        return 3, f"контракт объявлен нестандартно: {contract}"
    return 7, f"контракт объявлен ({contract}); потребление на этой витрине не проверено"


#: Короткие имена состояний приёмки для таблицы. Каждое описывает адрес, а не
#: витрину: ни одно не является её отказом.
ЖДЁТ = {
    "BLOCKED_OWNER_URLS": "ждёт адреса",
    "PENDING_DNS": "ждёт DNS",
    "NAME_NOT_RESOLVED": "имя не найдено",
    "HTTPS_NOT_SERVED": "нет HTTPS",
    "SERVES_SOMETHING_ELSE": "чужая витрина",
    "IDENTITY_UNVERIFIED": "не опознан",
    "IDENTITY_CONFIRMED": "опознан, не проведена",
}


def score_live(product: str, pkg: dict) -> tuple[int, str]:
    """Приёмка на действующем сайте: состояние адреса, а не оценка продукта.

    Числа здесь нет и быть не может, пока приёмка не проведена. Ноль означал бы
    «проверяли и не прошло», а верное — «не проверяли и вот почему». Продукт,
    работающий на трёх витринах, и продукт, который не собирается, одинаковым
    нулём уравнивались бы.

    Источник — слот адресов `config/live-acceptance.json` и запись опознания
    `scripts/live_identity_probe.py`, а не поле `domain` в пакете сайта. Пакет
    описывает цель выкладки; писать туда адрес действующего чужого сайта до
    подтверждения его личности значило бы объявить его нашей целью.

    Состояния и их смысл:

    * `BLOCKED_OWNER_URLS` — адреса нет, ожидание входа;
    * `PENDING_DNS` — адрес назван, имя ещё не разошлось; по прямому указанию
      владельца отказом не считается;
    * `NAME_NOT_RESOLVED` — имя не разрешается, хотя объявлено переданным;
    * `HTTPS_NOT_SERVED` — хост жив, TLS не обслуживается;
    * `SERVES_SOMETHING_ELSE` — адрес отвечает, но отдаёт не эту витрину;
    * `IDENTITY_CONFIRMED` — опознано, приёмку можно проводить.

    Ни одно из них не является дефектом витрины: все они описывают адрес.
    """
    config_path = ROOT / "config" / "live-acceptance.json"
    identity_path = ROOT / "artifacts" / "evidence" / "products" / "live-identity.json"
    if not config_path.is_file():
        return 0, "BLOCKED_OWNER_URLS: слот адресов не заведён"
    entry = (json.loads(config_path.read_text(encoding="utf-8"))
             .get("products", {}).get(product, {}))
    if not entry.get("base_url"):
        return 0, "BLOCKED_OWNER_URLS: адрес для приёмки не передан владельцем"

    адрес = entry["base_url"]
    if entry.get("status") == "PENDING_DNS":
        return 0, f"PENDING_DNS: {адрес} — имя ещё не разошлось, отказом не считается"

    if not identity_path.is_file():
        return 0, f"IDENTITY_UNVERIFIED: {адрес} — опознание не выполнялось"
    primary = ((json.loads(identity_path.read_text(encoding="utf-8")).get(product) or {})
               .get("primary") or {})
    verdict = primary.get("verdict", "IDENTITY_UNVERIFIED")
    note = primary.get("note", "")
    if verdict == "SERVES_OUR_STOREFRONT":
        return 2, f"IDENTITY_CONFIRMED: {адрес} отдаёт эту витрину; приёмка не выполнялась"
    return 0, f"{verdict}: {адрес} — {note}"


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
            # Ноль и ожидание читаются одинаково, а означают противоположное:
            # первое — что проверяли и не прошло, второе — что не проверяли и
            # не на чем. Пока адреса нет, числа нет тоже.
            # Числа нет, пока приёмка не проведена. Состояний, при которых её
            # нельзя провести, теперь несколько — нет адреса, имя не разошлось,
            # TLS не обслуживается, адрес отдаёт не эту витрину, — и все они
            # описывают адрес, а не витрину. Ноль уравнял бы их с провалом.
            "live_acceptance": None,
            "live_state": dims["live"]["note"].split(":", 1)[0].strip(),
            "total": round(100 * total / (MAX * len(DIMENSIONS))),
        }
    # Две средние, а не одна. Смешивать готовность работающего сайта с
    # отсутствием его адаптера в новой фабрике — значит получить число, которое
    # не отвечает ни на один вопрос: ни «работает ли продукт», ни «подключён ли
    # он». У Yummy эти величины расходятся предельно: продукт в production на
    # трёх витринах, а адаптера к фабрике нет вовсе.
    #
    # `product` — то, что видит зритель: пакет, данные, работа, облик,
    # доступность. `integration` — то, что видит фабрика: адаптер, предпросмотр
    # в общем стенде, приёмка боевой витрины её средствами.
    PRODUCT_DIMS = ("package", "data", "functional", "visual", "responsive")
    # Приёмки боевой витрины здесь нет намеренно. Она была слагаемым, и
    # слагаемое это равнялось нулю — не потому что витрина не прошла приёмку, а
    # потому что адреса для неё не передали. Ожидание входа занижало число,
    # которое к нему не относится. Владелец потребовал трёх раздельных величин,
    # и приёмка витрины — третья из них, а не часть второй.
    INTEGRATION_DIMS = ("preview", "adapter")
    for name, info in products.items():
        dims = info["dimensions"]
        if name == "yummy":
            # Готовность продукта Yummy этой рубрикой не измеряется, и ноль
            # здесь был бы неправдой. Рубрика смотрит на артефакты фабрики —
            # пакет, предпросмотр, снимки, — а Yummy живёт вне её: отдельное
            # приложение на трёх боевых витринах.
            #
            # Что известно и откуда: ARCHITECT_CORE записал в PROGRAM_STATE
            # ревизию 4460031, три витрины и health healthy, проверено
            # 2026-09-04. Это измерение Core, а не этой полосы, и выдавать его
            # за своё нельзя. Прочитано на месте: 41 страничный маршрут, 66
            # модульных тестов, 13 браузерных спеков.
            #
            # Чего эта полоса не делала: не запускала ни один из тестов —
            # рабочая копия занята активной веткой другого потока, и `typecheck`
            # пишет в дерево; не открывала боевые домены — они закрыты профилем
            # разрешений. Поэтому число не ставится вовсе.
            info["product_readiness"] = None
            info["product_note"] = (
                "не измерено этой полосой: приложение вне фабрики, боевые адреса "
                "закрыты профилем разрешений, чужая активная ветка не запускается. "
                "Известно от ARCHITECT_CORE: ревизия 4460031, три витрины, "
                "health healthy на 2026-09-04. Прочитано: 41 маршрут, 66 модульных "
                "тестов, 13 браузерных спеков")
            info["integration_readiness"] = round(
                100 * sum(dims[k]["points"] for k in INTEGRATION_DIMS)
                / (MAX * len(INTEGRATION_DIMS)))
            continue
        info["product_readiness"] = round(
            100 * sum(dims[k]["points"] for k in PRODUCT_DIMS) / (MAX * len(PRODUCT_DIMS)))
        info["integration_readiness"] = round(
            100 * sum(dims[k]["points"] for k in INTEGRATION_DIMS)
            / (MAX * len(INTEGRATION_DIMS)))

    return {
        "artifact": "TEMPLATE_PRODUCT_READINESS",
        # Средняя считается только по измеренным: продукт, который эта полоса
        # не мерила, не имеет права ни поднять её, ни опустить.
        "average_product": round(sum(
            p["product_readiness"] for p in products.values()
            if p["product_readiness"] is not None) / max(1, sum(
                1 for p in products.values() if p["product_readiness"] is not None))),
        "average_product_measured": sorted(
            k for k, v in products.items() if v["product_readiness"] is not None),
        "average_integration": round(
            sum(p["integration_readiness"] for p in products.values()) / len(products)),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "rubric": dict(DIMENSIONS),
        "product_dimensions": list(PRODUCT_DIMS),
        "integration_dimensions": list(INTEGRATION_DIMS),
        "measured_products": sum(
            1 for p in products.values() if p["product_readiness"] is not None),
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
        cells = []
        for n in names:
            info = report["products"][n]
            if key == "live" and info["live_acceptance"] is None:
                cells.append(f"{ЖДЁТ.get(info['live_state'], 'не проведена'):>17}")
            else:
                cells.append(f"{info['dimensions'][key]['points']:>17}")
        print(f"{label:30}" + "".join(cells))
    print("-" * (30 + 17 * len(names)))
    for label, field in (("ГОТОВНОСТЬ ПРОДУКТА, %", "product_readiness"),
                         ("ГОТОВНОСТЬ ИНТЕГРАЦИИ, %", "integration_readiness"),
                         ("  готовность пакета, %", "package_readiness"),
                         ("  предпросмотр, %", "preview_acceptance"),
                         ("  приёмка витрины, %", "live_acceptance")):
        cells = []
        for n in names:
            value = report["products"][n][field]
            if value is not None:
                cells.append(f"{value:>17}")
            elif field == "live_acceptance":
                cells.append(f"{ЖДЁТ.get(report['products'][n]['live_state'], 'не проведена'):>17}")
            else:
                cells.append(f"{'не измерено':>17}")
        print(f"{label:30}" + "".join(cells))
    print(f"\nсредняя готовность продуктов:   {report['average_product']}%")
    print(f"средняя готовность интеграции: {report['average_integration']}%")
    print(f"{OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
