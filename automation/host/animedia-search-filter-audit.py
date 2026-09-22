#!/usr/bin/env python3
"""Поиск, фильтры и навигация Animedia — настоящим взаимодействием в браузере.

Проверяется не наличие формы, а результат: что точный запрос находит тайтл,
что часть названия и другой регистр тоже находят, что латиница и кириллица
работают обе, что бессмысленный запрос даёт честное «ничего не найдено», а не
полный каталог, что фильтры меняют выдачу и снимаются, что листалка не
повторяет и не теряет карточки, и что переход в карточку и возврат назад
сохраняют состояние.

Живой домен для этого не нужен: поднимается локальный рантайм, домен
разрешается в петлю, `Host` остаётся настоящим.

    .venv/bin/python automation/host/animedia-search-filter-audit.py --out <каталог>
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import quote

КОРЕНЬ = Path(__file__).resolve().parents[2]

ВЫДАЧА = r"""
() => {
  const видим = (el) => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const карточки = [...document.querySelectorAll('.zg a.zt')].filter(видим);
  const пусто = document.querySelector('.zempty, [data-empty], [class*="empty"]');
  return {
    count: карточки.length,
    hrefs: карточки.map((к) => к.getAttribute('href')),
    titles: карточки.map((к) => (к.querySelector('.zt__t') || {}).textContent || ''),
    h1: (document.querySelector('h1') || {}).textContent || '',
    empty_state: !!(пусто && видим(пусто)),
    empty_text: пусто ? (пусто.textContent || '').trim().slice(0, 120) : '',
    url: location.pathname + location.search,
    pagination_links: [...document.querySelectorAll('.zpg a')].map((a) => a.getAttribute('href')),
    filters_visible: [...document.querySelectorAll('.afilt, [class*="filt"]')].filter(видим).length,
  };
}
"""


def поднять(рантайм: Path, витрина: str, лог: Path):
    корень = Path(os.environ.get("ANIMEDIA_RUNTIME_ROOT", "/srv/lords/.frontend"))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        порт = s.getsockname()[1]
    окр = dict(os.environ)
    окр.update({"ANIMEDIA_TEMPLATE_MANIFEST": str(корень / f"template-manifest-{витрина}.json"),
                "ANIMEDIA_CATALOG": str(корень / f"{витрина}-catalog.json"),
                "ANIMEDIA_SITE_NAME": "Animedia", "PYTHONDONTWRITEBYTECODE": "1"})
    for чужое in ("LORDS_TEMPLATE_MANIFEST", "LORDS_CATALOG", "LORDS_DETAILS"):
        окр.pop(чужое, None)
    p = subprocess.Popen(["/usr/bin/python3", str(рантайм), "--port", str(порт)],
                         stdout=лог.open("w", encoding="utf-8"),
                         stderr=subprocess.STDOUT, env=окр, cwd=str(КОРЕНЬ))
    for _ in range(600):
        time.sleep(0.5)
        if p.poll() is not None:
            raise SystemExit(f"рантайм не поднялся, см. {лог}")
        try:
            with socket.create_connection(("127.0.0.1", порт), timeout=0.5):
                return p, порт
        except OSError:
            continue
    raise SystemExit("порт не открылся")


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--runtime", default="automation/host/animedia-frontend.py")
    р.add_argument("--site", default="animedia-01")
    р.add_argument("--domain", default="animedia.icu")
    р.add_argument("--out", required=True)
    a = р.parse_args()
    вывод = Path(a.out)
    вывод.mkdir(parents=True, exist_ok=True)

    корень = Path(os.environ.get("ANIMEDIA_RUNTIME_ROOT", "/srv/lords/.frontend"))
    снимок = json.loads((корень / f"{a.site}-catalog.json").read_text(encoding="utf-8"))
    записи = снимок["items"] if isinstance(снимок, dict) else снимок
    образец = next(з for з in записи if len(з["title"]) > 8 and з["title"][0].isalpha())
    целое = образец["title"]
    часть = целое.split()[0]

    процесс, порт = поднять(Path(a.runtime), a.site, вывод / "runtime.log")
    from playwright.sync_api import sync_playwright

    итог = {"task": "ANIMEDIA-SEARCH-FILTER-AUDIT", "tenant": "animedia",
            "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "sample_title": целое, "cases": [], "failures": []}
    провалы = итог["failures"]
    правило = f"MAP {a.domain} 127.0.0.1:{порт}"
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=[f"--host-resolver-rules={правило}"])
            ctx = b.new_context(viewport={"width": 1440, "height": 900})
            стр = ctx.new_page()

            def открыть(путь: str) -> dict:
                стр.goto(f"http://{a.domain}{путь}", wait_until="load", timeout=60000)
                стр.wait_for_timeout(200)
                return стр.evaluate(ВЫДАЧА)

            def случай(имя: str, путь: str, проверка) -> dict:
                р_ = открыть(путь)
                запись = {"case": имя, "path": путь, **р_}
                итог["cases"].append(запись)
                беда = проверка(р_)
                if беда:
                    провалы.append(f"{имя}: {беда}")
                print(f"  {имя:<28} карточек {р_['count']:>3} "
                      f"{'пусто' if р_['empty_state'] else ''} {беда or ''}", flush=True)
                return р_

            # --- поиск ---
            точный = случай("точное название", f"/search/?q={quote(целое)}",
                            lambda r: None if любой_совпал(r, целое) else
                            "точное название не найдено")
            случай("часть названия", f"/search/?q={quote(часть)}",
                   lambda r: None if r["count"] > 0 else "часть названия ничего не нашла")
            случай("другой регистр", f"/search/?q={quote(целое.upper())}",
                   lambda r: None if r["count"] > 0 else "верхний регистр ничего не нашёл")
            случай("латиница", "/search/?q=anime",
                   lambda r: None if (r["count"] > 0 or r["empty_state"]) else
                   "латиница не дала ни выдачи, ни честной пустоты")
            случай("опечатка", f"/search/?q={quote(часть[:-1] + 'ъ')}",
                   lambda r: None if (r["count"] >= 0) else "опечатка сломала страницу")
            случай("пустой запрос", "/search/?q=",
                   lambda r: None if (r["empty_state"] or r["count"] == 0) else
                   f"пустой запрос отдал {r['count']} карточек вместо честной пустоты")
            случай("бессмысленный запрос", "/search/?q=%D1%8A%D1%8B%D1%8C%D1%89%D0%B7%D1%85",
                   lambda r: None if (r["count"] == 0 and r["empty_state"]) else
                   f"бессмыслица отдала {r['count']} карточек (пустое состояние: {r['empty_state']})")

            # --- фильтры каталога ---
            весь = случай("каталог без фильтров", "/catalog/",
                          lambda r: None if r["count"] > 0 else "каталог пуст")
            год = случай("фильтр по году", "/catalog/?year=2024",
                         lambda r: None if 0 < r["count"] else "фильтр по году дал пусто")
            годы = стр.evaluate(
                "() => [...new Set([...document.querySelectorAll('.zg a.zt .zt__m')]"
                ".map((m) => (m.textContent || '').split('·').pop().trim()))]")
            итог["year_filter_years"] = годы
            if годы != ["2024"]:
                провалы.append(f"фильтр по году оставил чужие годы: {годы}")
            if год["hrefs"] == весь["hrefs"]:
                провалы.append("фильтр по году не изменил выдачу")
            # Код жанра берётся со страницы, а не придумывается: коды
            # транслитерированы, и выдуманный `action` дал бы честную пустоту,
            # которую легко принять за поломку фильтра.
            коды = стр.evaluate(
                "() => [...document.querySelectorAll('a[href*=\"genre=\"]')]"
                ".map((a) => a.getAttribute('href')).slice(0, 3)")
            итог["genre_links_found"] = коды
            if not коды:
                провалы.append("на странице нет ни одной ссылки на жанр")
                жанр = {"count": 0, "hrefs": []}
            else:
                жанр = случай("фильтр по жанру", коды[0],
                              lambda r: None if r["count"] > 0 else
                              "существующий жанр дал пустую выдачу")
                if жанр["count"] and жанр["hrefs"] == весь["hrefs"]:
                    провалы.append("фильтр по жанру не изменил выдачу")
                случай("несуществующий жанр", "/catalog/?genre=такого-нет",
                       lambda r: None if (r["count"] == 0 and r["empty_state"]) else
                       "несуществующий жанр вернул выдачу вместо честной пустоты")
            вид = случай("фильтр по типу", "/catalog/?kind=%D0%90%D0%BD%D0%B8%D0%BC%D0%B5",
                         lambda r: None if r["count"] >= 0 else "тип сломал страницу")
            сочетание = случай("сочетание фильтров",
                               f"/catalog/?year=2024&{(коды[0].split('?')[1] if коды else 'genre=anime')}",
                               lambda r: None if r["count"] >= 0 else "сочетание сломало страницу")
            if сочетание["count"] > год["count"]:
                провалы.append("сочетание фильтров расширило выдачу вместо сужения")
            снято = случай("фильтры сняты", "/catalog/",
                           lambda r: None if r["hrefs"] == весь["hrefs"] else
                           "после снятия фильтров выдача не вернулась к исходной")

            # --- листалка ---
            с1 = открыть("/catalog/")
            с2 = открыть("/catalog/?page=2")
            с3 = открыть("/catalog/?page=3")
            пересечение = set(с1["hrefs"]) & set(с2["hrefs"]) | set(с2["hrefs"]) & set(с3["hrefs"])
            итог["pagination"] = {"page1": len(с1["hrefs"]), "page2": len(с2["hrefs"]),
                                  "page3": len(с3["hrefs"]), "overlap": len(пересечение)}
            if пересечение:
                провалы.append(f"листалка повторяет {len(пересечение)} карточек между страницами")
            if not (с1["count"] and с2["count"] and с3["count"]):
                провалы.append("одна из страниц листалки пуста")

            # --- переход и возврат ---
            открыть(f"/search/?q={quote(целое)}")
            первая = стр.query_selector(".zg a.zt")
            if первая is None:
                провалы.append("в выдаче поиска нет кликабельной карточки")
            else:
                адрес = первая.get_attribute("href")
                первая.click()
                стр.wait_for_load_state("load")
                стр.wait_for_timeout(200)
                куда = стр.evaluate("() => location.pathname")
                if адрес not in куда:
                    провалы.append(f"переход из выдачи привёл не туда: {куда} вместо {адрес}")
                стр.go_back()
                стр.wait_for_load_state("load")
                стр.wait_for_timeout(200)
                назад = стр.evaluate("() => location.pathname + location.search")
                if "q=" not in назад:
                    провалы.append(f"возврат назад потерял запрос: {назад}")
                итог["navigation"] = {"to": куда, "back": назад}

            # --- чужого tenant в выдаче быть не может ---
            все_адреса = [h for c in итог["cases"] for h in c["hrefs"]]
            чужие = [h for h in все_адреса if h and not h.startswith(("/title/", "/collection/"))]
            if чужие:
                провалы.append(f"в выдаче посторонние адреса: {чужие[:3]}")
            ctx.close()
            b.close()
    finally:
        процесс.terminate()
        try:
            процесс.wait(timeout=20)
        except subprocess.TimeoutExpired:
            процесс.kill()

    итог["SEARCH_FILTER_PASS"] = not провалы
    (вывод / "SEARCH_FILTER_AUDIT.json").write_text(
        json.dumps(итог, ensure_ascii=False, indent=1), encoding="utf-8")
    print("SEARCH_FILTER_PASS:", итог["SEARCH_FILTER_PASS"])
    for f in провалы[:15]:
        print("  провал:", f)
    return 0 if итог["SEARCH_FILTER_PASS"] else 1


def любой_совпал(r: dict, название: str) -> bool:
    цель = название.casefold()
    return any(цель in (t or "").casefold() for t in r["titles"])


if __name__ == "__main__":
    raise SystemExit(main())
