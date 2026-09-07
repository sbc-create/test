#!/usr/bin/env python3
"""Что владелец может открыть прямо сейчас: адреса, команда и что смотреть.

Собирается из фактов: адреса берутся из плана стенда, страницы — из собранных
предпросмотров, снимки — из каталога свидетельств, состояние — из отчётов
проверок. Ничего не объявляется готовым без файла, который это подтверждает.

Отдельно и крупно сказано, чем это не является. Предпросмотр — не production и
не приёмка витрины: у этих витрин нет ни боевого домена, ни окружения, ни
разрешения владельца. Назвать предпросмотр приёмкой значит отчитаться о том,
чего не было.

Запуск:
    .venv/bin/python scripts/owner_preview_package.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "artifacts" / "evidence" / "products"
PREVIEW_ROOT = ROOT / "var" / "product-preview"
OUT = EVIDENCE / "owner-package.json"
OUT_MD = ROOT / "docs" / "templates" / "OWNER-PREVIEW.md"

#: Что стоит открыть у каждой витрины и на что смотреть. Список короткий
#: намеренно: владельцу нужен путь проверки, а не полная карта сайта.
WHAT_TO_CHECK = {
    "zona-cinema": [
        ("/", "первый экран, карусель «Сейчас смотрят», полные ряды без пустых мест"),
        ("/catalog/", "24 карточки, фасеты сбоку, пагинация"),
        ("/genres/drama/", "выбор жанра меняет состав выдачи, адрес запоминает выбор"),
        ("/search/", "поиск по названию на полном каталоге"),
        ("/404.html", "страница «не найдено» с путём назад"),
    ],
    "animedia-portal": [
        ("/", "первый экран с поиском, «Продолжающиеся истории», сезоны в каталоге"),
        ("/anime/", "раздел аниме — 507 записей боевого каталога"),
        ("/catalog/", "плотная сетка в шесть колонок"),
        ("/search/", "поиск по названию"),
        ("/404.html", "страница «не найдено»"),
    ],
    "basis-video": [
        ("/", "первый экран, разделы рядами, «Все материалы» рядом с заголовком"),
        ("/lekcii/", "листинг с пагинацией и кнопкой «Показать ещё»"),
        ("/collections/izbrannoe/", "подборка"),
        ("/news/", "новости"),
        ("/search/", "поиск по 28 материалам: опечатка, чужая раскладка и «ё» находят"),
    ],
}

#: Известные ограничения предпросмотра. Названы прямо: без них снимок можно
#: принять за дефект витрины, а он им не является.
LIMITS = {
    "zona-cinema": [
        "постеры отдаёт внешний хост поставщика; часть их в этой обстановке не "
        "загружается, и на их месте видна заглушка с буквой — на боевом домене они придут",
        "каталог предпросмотра — срез в 4 000 записей из 53 251: полная сборка "
        "занимает часы и на облик не влияет",
    ],
    "animedia-portal": [
        "постеры отдаёт внешний хост поставщика — см. выше",
        "каталог предпросмотра — срез в 4 000 записей из 53 251",
    ],
    "basis-video": [
        "всё содержимое — синтетический набор «Фикстура: материал NN»: настоящие "
        "материалы требуют источника, прав и решения владельца",
        "поиск работает по указателю на странице: где движок отвечает сам, он и "
        "отвечает, скрипт туда не вмешивается",
    ],
}


def _json(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def build() -> dict:
    plan = _json(EVIDENCE / "preview-plan.json") or {}
    readiness = _json(EVIDENCE / "product-readiness.json") or {}
    products = {}
    for product, pages in WHAT_TO_CHECK.items():
        directory = PREVIEW_ROOT / product
        if not (directory / "index.html").is_file():
            products[product] = {"state": "не собран"}
            continue
        shots = sorted((EVIDENCE / product / "screenshots").glob("*.png"))
        functional = _json(EVIDENCE / product / "functional-report.json") or {}
        a11y = _json(EVIDENCE / product / "a11y-report.json") or {}
        checks = functional.get("checks") or []
        runs = a11y.get("runs") or []
        products[product] = {
            "url": (plan.get("products") or {}).get(product),
            "pages": [{"path": p, "look_for": w} for p, w in pages],
            "screenshots_dir": str((EVIDENCE / product / "screenshots").relative_to(ROOT)),
            "screenshots": len(shots),
            "documents": sum(1 for _ in directory.rglob("*.html")),
            "checks_passed": sum(1 for c in checks if c.get("ok") is True),
            "checks_not_applicable": sum(1 for c in checks if c.get("ok") is None),
            "checks_failed": sum(1 for c in checks if c.get("ok") is False),
            "axe_runs": len(runs),
            "axe_violations": sum(len(r.get("violations") or []) for r in runs),
            "readiness": (readiness.get("products") or {}).get(product, {}).get("total"),
            "limits": LIMITS.get(product, []),
        }
    # Команды собираются из фактических значений хоста, а не из образцов.
    # Инструкция с `<хост>` и `<путь>` непригодна: её нельзя выполнить, не
    # догадавшись, чем их заменить.
    import getpass
    import socket

    host = socket.gethostname()
    user = getpass.getuser()
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("10.255.255.255", 1))
        address = probe.getsockname()[0]
        probe.close()
    except OSError:
        address = host
    python = ROOT / ".venv" / "bin" / "python"
    ports = sorted({int(str(url).rsplit(":", 1)[1].rstrip("/"))
                    for url in (plan.get("products") or {}).values()}
                   | {int(str(plan.get("base", "")).rsplit(":", 1)[1] or 0)} - {0})
    forwards = " ".join(f"-L {port}:127.0.0.1:{port}" for port in ports)

    return {
        "artifact": "OWNER_PREVIEW_PACKAGE",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "host": {"hostname": host, "address": address, "user": user,
                 "worktree": str(ROOT), "python": str(python),
                 "listen": "только 127.0.0.1 — наружу стенд не смотрит"},
        "index": plan.get("base"),
        "tunnel": f"ssh -N {forwards} {user}@{address}",
        "start": f"cd {ROOT} && {python} scripts/product_preview_stand.py",
        "status": f"cd {ROOT} && {python} scripts/product_preview_stand.py --status",
        "stop": f"cd {ROOT} && {python} scripts/product_preview_stand.py --stop",
        "not_production": ("Это предпросмотр. Ни одна из витрин не выложена: у них нет "
                           "боевого домена, окружения и разрешения владельца. Приёмкой "
                           "витрины предпросмотр не является."),
        "products": products,
    }


def markdown(data: dict) -> str:
    lines = [
        "# Предпросмотр витрин для владельца",
        "",
        "> Это **предпросмотр**, а не production. Ни одна витрина не выложена: у них",
        "> нет боевого домена, окружения и разрешения владельца. Приёмкой витрины",
        "> предпросмотр не является ни при каких условиях.",
        "",
        "## Как открыть",
        "",
        "На сервере:",
        "",
        "```bash",
        f"{data['start']}",
        "```",
        "",
        "Стенд отцепляется от оболочки и переживает её завершение. Проверить и",
        "остановить:",
        "",
        "```bash",
        f"{data['status']}",
        f"{data['stop']}",
        "```",
        "",
        "С своей машины — один туннель на все витрины:",
        "",
        "```bash",
        f"{data.get('tunnel') or '—'}",
        "```",
        "",
        f"Хост: `{data['host']['hostname']}` ({data['host']['address']}), "
        f"пользователь `{data['host']['user']}`.  ",
        f"Рабочая копия: `{data['host']['worktree']}`.  ",
        f"Стенд слушает {data['host']['listen']}.",
        "",
        f"Опись со ссылками: {data.get('index') or '—'}",
        "",
    ]
    for product, info in data["products"].items():
        if info.get("state") == "не собран":
            lines += [f"## {product}", "", "Предпросмотр не собран.", ""]
            continue
        lines += [
            f"## {product}",
            "",
            f"**Адрес:** {info['url']}  ",
            f"**Готовность:** {info['readiness']}%  ",
            f"**Страниц собрано:** {info['documents']}  ",
            f"**Снимки:** `{info['screenshots_dir']}` ({info['screenshots']} файлов)  ",
            f"**Проверки:** {info['checks_passed']} пройдено"
            + (f", {info['checks_not_applicable']} не применимо"
               if info["checks_not_applicable"] else "")
            + (f", {info['checks_failed']} не прошли" if info["checks_failed"] else "")
            + f"; axe — {info['axe_runs']} прогонов, нарушений {info['axe_violations']}",
            "",
            "| Страница | На что смотреть |",
            "|---|---|",
        ]
        for page in info["pages"]:
            lines.append(f"| `{page['path']}` | {page['look_for']} |")
        if info["limits"]:
            lines += ["", "**Известные ограничения предпросмотра:**", ""]
            lines += [f"* {limit}" for limit in info["limits"]]
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(markdown(data), encoding="utf-8")
    print(f"опись: {data.get('index')}")
    for product, info in data["products"].items():
        if info.get("state") == "не собран":
            print(f"  {product:18} не собран")
            continue
        print(f"  {product:18} {info['url']}  готовность {info['readiness']}%  "
              f"снимков {info['screenshots']}  проверок {info['checks_passed']}")
    print(f"\n{OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
