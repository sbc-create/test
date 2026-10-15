#!/usr/bin/env python3
"""Пограничные сценарии витрины: поиск без результатов, границы, ошибки, серии.

Зачем отдельно от `browser-audit-cell.py`. Тот осматривает ОСНОВНОЙ путь:
главная, каталог, карточка, меню, мобильная ширина. Здесь — то, что ломается
не на основном пути и потому дольше всего живёт незамеченным:

  * **поиск**: пустой запрос, запрос-мусор без результатов, очень длинный
    запрос, запрос с пробелами и кавычками — страница обязана отвечать и
    говорить, что не найдено, а не отдавать пустую выдачу под видом результата;
  * **границы пагинации**: первая страница, последняя, страница за пределами и
    нечисловая — `page/9999` не должна отдавать 200 с пустым списком;
  * **фильтры без результатов**: сочетание жанра и года, которого нет;
  * **ошибки**: несуществующая карточка, несуществующий раздел, мусорный путь,
    несуществующая серия и сезон — каждый обязан отвечать 404, а не 200 и не 500;
  * **серии**: первая и последняя серия сезона, переход между сезонами,
    нумерация (серия с номером 0 не должна терять свою ссылку);
  * **узкий телефон**: 320 px — проверяется отсутствие горизонтальной
    прокрутки и размер нажимаемых целей.

Стенд поднимается тем же способом, что и основной осмотр: функции берутся из
`browser-audit-cell.py`, а не копируются — две копии разошлись бы на первой же
правке рантайма.

    python3 automation/local/edge-cases-check.py --site lords-10 \\
        --data var/k2-data/publish-stage8
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.seo.render_check import chromium_path  # noqa: E402

ТЕЛЕФОН_УЗКИЙ = {"width": 320, "height": 568}
КОМПЬЮТЕР = {"width": 1366, "height": 768}
#: Минимальная сторона нажимаемой цели. 24 px — не выдумка: это нижняя граница
#: WCAG 2.2 (2.5.8 Target Size Minimum, уровень AA).
МИНИМАЛЬНАЯ_ЦЕЛЬ = 24
#: Цели, размер которых задан межстрочным расстоянием окружающего
#: текста, исключены самим WCAG 2.5.8 — но остаются в отчёте.
ИСКЛЮЧЕНИЕ_INLINE = "целей inline (исключение WCAG 2.5.8)"


def _основной_осмотр():
    """Функции стенда из основного осмотра: одна реализация на два инструмента."""
    путь = КОРЕНЬ / "automation" / "local" / "browser-audit-cell.py"
    спец = importlib.util.spec_from_file_location("browser_audit_cell", путь)
    м = importlib.util.module_from_spec(спец)
    sys.modules[спец.name] = м
    спец.loader.exec_module(м)
    return м


def поиск(стр, база: str) -> dict:
    """Поиск: пустой, мусорный, длинный, с кавычками.

    Пустой запрос — отдельный случай: витрина показывает форму и подсказку
    («Введите название»), и это правильно. Требовать от него «ничего не
    найдено» значит требовать неверного поведения — измерено 14.10.
    """
    запросы = {
        "пустой": "",
        "мусор": "цъйщэъфывапролдж",
        "длинный": "а" * 300,
        "кавычки и пробелы": '  "драма"  ',
        "служебные символы": "<script>&%",
    }
    итог: dict = {}
    for имя, запрос in запросы.items():
        ответ = стр.goto(f"{база}/search/?q={запрос}", wait_until="domcontentloaded")
        текст = стр.inner_text("body")[:4000]
        карточки = стр.locator("a[href^='/title/']").count()
        запись = {"код": ответ.status if ответ else None, "карточек": карточки}
        if имя == "пустой":
            # Приглашение к вводу: форма на месте и подсказка видна.
            запись["форма поиска"] = стр.locator(
                "input[type='search'], input[name='q']").count() > 0
            запись["подсказка"] = bool(re.search(
                r"введите|начните вводить|поиск по", текст, re.I))
        else:
            запись["сообщение о пустой выдаче"] = bool(re.search(
                r"не найдено|ничего не найден|нет результатов", текст, re.I))
            запись["эхо запроса в разметке"] = запрос.strip()[:40] in текст
        итог[имя] = запись
    return итог


def границы_пагинации(стр, база: str) -> dict:
    """Пагинация в ЕЁ форме адреса: `?page=N`.

    Форма взята из разметки каталога, а не придумана: ссылки там выглядят как
    `/catalog/?page=2` и `/catalog/?page=<последняя>`. Прежняя проба спрашивала
    `/catalog/page/2/`, такой формы у витрины нет вовсе, и 404 был правильным
    ответом — проверялась моя догадка, а не витрина.
    """
    стр.goto(база + "/catalog/", wait_until="domcontentloaded")
    ссылки = стр.eval_on_selector_all(
        "a[href*='page=']", "ээ => ээ.map(э => э.getAttribute('href'))")
    номера = sorted({int(m.group(1)) for m in
                     (re.search(r"page=(\d+)", с or "") for с in ссылки) if m})
    последняя = номера[-1] if номера else 1
    случаи = {
        "первая": "/catalog/?page=1",
        "вторая": "/catalog/?page=2",
        "последняя": f"/catalog/?page={последняя}",
        "за последней": f"/catalog/?page={последняя + 1}",
        "нечисловая": "/catalog/?page=abc",
        "нулевая": "/catalog/?page=0",
        "отрицательная": "/catalog/?page=-1",
    }
    итог: dict = {"последняя страница по разметке": последняя}
    for имя, путь in случаи.items():
        ответ = стр.goto(база + путь, wait_until="domcontentloaded")
        итог[имя] = {"код": ответ.status if ответ else None,
                     "карточек": стр.locator("a[href^='/title/']").count()}
    return итог


def ошибки(стр, база: str) -> dict:
    """Несуществующее обязано отвечать 404, а не 200 и не 500."""
    пути = {
        "карточки нет": "/title/takogo-tochno-net-12345/",
        "раздела нет": "/razdel-kotorogo-net/",
        "мусорный путь": "/catalog/../../etc/passwd",
        "сезона нет": "/title/takogo-tochno-net-12345/season-99/",
        "серии нет": "/title/takogo-tochno-net-12345/season-1/episode-99/",
        "длинный путь": "/" + "a" * 500,
    }
    итог: dict = {}
    for имя, путь in пути.items():
        try:
            ответ = стр.goto(база + путь, wait_until="domcontentloaded")
            итог[имя] = {"код": ответ.status if ответ else None}
        except Exception as ош:  # noqa: BLE001
            итог[имя] = {"код": None, "ошибка": f"{type(ош).__name__}"}
    return итог


def серии(стр, база: str, данные: Path, site_id: str) -> dict:
    """Серии и сезоны: первая, последняя, переход, нумерация с нуля."""
    подробности = данные / f"{site_id}-details.json"
    if not подробности.is_file():
        return {"проверено": False, "причина": "нет файла подробностей"}
    детали = json.loads(подробности.read_text(encoding="utf-8")).get("details") or {}
    сериал = None
    for слаг, запись in детали.items():
        сезоны = (запись or {}).get("seasons") or []
        if сезоны and sum(len((с or {}).get("episodes") or []) for с in сезоны) > 1:
            сериал = (слаг, запись)
            break
    if not сериал:
        return {"проверено": False, "причина": "в данных нет сериала с сериями"}

    слаг, запись = сериал
    сезоны = запись.get("seasons") or []
    номера_серий = [(с.get("number"), [э.get("number") for э in (с.get("episodes") or [])])
                    for с in сезоны]
    итог: dict = {"проверено": True, "слаг": слаг, "сезонов": len(сезоны),
                  "номера": номера_серий[:3]}

    ответ = стр.goto(f"{база}/title/{слаг}/", wait_until="domcontentloaded")
    итог["страница сериала"] = ответ.status if ответ else None
    ссылки = стр.eval_on_selector_all(
        "a[href*='/episode-']", "ээ => ээ.map(э => э.getAttribute('href'))")
    итог["ссылок на серии в разметке"] = len(ссылки)

    # Все ли серии из данных имеют ссылку. Потерянная серия 0 — именно этот
    # случай: при подсчёте «по счётчику» вместо номера она исчезает из списка.
    ожидаемые = {f"season-{с.get('number')}/episode-{э.get('number')}"
                 for с in сезоны for э in (с.get("episodes") or [])}
    в_разметке = {m.group(1) for m in
                  (re.search(r"(season-\d+/episode-\d+)", с or "") for с in ссылки) if m}
    итог["серий в данных"] = len(ожидаемые)
    итог["серий со ссылкой"] = len(ожидаемые & в_разметке)
    итог["серии без ссылки"] = sorted(ожидаемые - в_разметке)[:8]

    if ссылки:
        первая, последняя = ссылки[0], ссылки[-1]
        for имя, адрес in (("первая серия", первая), ("последняя серия", последняя)):
            ответ = стр.goto(база + адрес, wait_until="domcontentloaded")
            рамка = стр.locator("[data-publisher-id], [data-state]").count()
            итог[имя] = {"адрес": адрес, "код": ответ.status if ответ else None,
                         "рамка плеера в разметке": рамка > 0}
    return итог


def узкий_телефон(контекст, база: str) -> dict:
    """320 px: прокрутка и размер нажимаемых целей.

    Исключение WCAG 2.5.8 («inline») учитывается: цель, размер которой задан
    межстрочным расстоянием окружающего текста — ссылка внутри заголовка или
    абзаца, — под минимум не попадает. Такие цели попадают в отчёт отдельной
    строкой с названной причиной, а не исчезают из него.
    """
    стр = контекст.new_page()
    стр.set_viewport_size(ТЕЛЕФОН_УЗКИЙ)
    итог: dict = {}
    ЗАМЕР = """(предел) => Array.from(document.querySelectorAll(
        'a, button, input, [role=button]')).map(э => {
        const r = э.getBoundingClientRect();
        const предок = э.parentElement;
        return {
          t: ((э.textContent || э.getAttribute('aria-label') || э.tagName) || '')
               .trim().slice(0, 30),
          w: Math.round(r.width), h: Math.round(r.height),
          inline: getComputedStyle(э).display.startsWith('inline')
                  && !!предок && /^(H1|H2|H3|H4|H5|H6|P|LI|SPAN|TD)$/.test(предок.tagName),
        };
      }).filter(x => x.w > 0 && x.h > 0 && (x.w < предел || x.h < предел))"""
    for имя, путь in (("главная", "/"), ("каталог", "/catalog/")):
        стр.goto(база + путь, wait_until="domcontentloaded")
        прокрутка = стр.evaluate(
            "() => document.documentElement.scrollWidth > "
            "document.documentElement.clientWidth + 1")
        мелкие = стр.evaluate(ЗАМЕР, МИНИМАЛЬНАЯ_ЦЕЛЬ)
        строгие = [м for м in мелкие if not м["inline"]]
        исключения = [м for м in мелкие if м["inline"]]
        итог[имя] = {
            "горизонтальная прокрутка": прокрутка,
            "целей меньше минимума": len(строгие),
            "примеры": [f"{м['t']} {м['w']}x{м['h']}" for м in строгие][:6],
            ИСКЛЮЧЕНИЕ_INLINE: [f"{м['t']} {м['w']}x{м['h']}" for м in исключения][:6],
        }
    стр.close()
    return итог


def фильтр_без_результатов(стр, база: str) -> dict:
    """Сочетание фильтров, которого нет в данных: сообщение, а не пустота."""
    стр.goto(база + "/catalog/?year=1902", wait_until="domcontentloaded")
    текст = стр.inner_text("body")[:4000]
    карточки = стр.locator("a[href^='/title/']").count()
    сказано = bool(re.search(r"не найдено|ничего не|нет результатов|уточните",
                             текст, re.I))
    return {"карточек": карточки, "сообщение о пустой выдаче": сказано}


def главное(site_id: str, данные_исх: Path, порт: int, выход: Path) -> dict:
    осн = _основной_осмотр()
    проект = КОРЕНЬ / "var" / "new-sites" / site_id
    конфиг = json.loads((проект / "config" / "site.json").read_text(encoding="utf-8"))

    врем = Path(tempfile.mkdtemp(prefix=f"edge-{site_id}-"))
    данные = врем / "data"
    данные.mkdir()
    for ф in данные_исх.glob(f"{site_id}-*.json"):
        shutil.copy(ф, данные / ф.name)

    процесс, готово = осн.поднять(проект, конфиг, данные, порт)
    итог: dict = {"site": site_id, "domain": конфиг.get("domain")}
    if not готово:
        вывод = (процесс.stdout.read() if процесс.stdout else b"").decode("utf-8", "replace")
        итог["итог"] = "ОТКАЗ: рантайм не поднялся"
        итог["журнал"] = вывод[-800:]
        процесс.kill()
        shutil.rmtree(врем, ignore_errors=True)
        return итог

    база = f"http://127.0.0.1:{порт}"
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            путь_браузера = chromium_path()
            браузер = pw.chromium.launch(
                **({"executable_path": путь_браузера} if путь_браузера else {}))
            контекст = браузер.new_context(viewport=КОМПЬЮТЕР)
            стр = контекст.new_page()
            итог["поиск"] = поиск(стр, база)
            итог["пагинация"] = границы_пагинации(стр, база)
            итог["фильтр без результатов"] = фильтр_без_результатов(стр, база)
            итог["ошибки"] = ошибки(стр, база)
            итог["серии"] = серии(стр, база, данные, site_id)
            итог["узкий телефон"] = узкий_телефон(контекст, база)
            контекст.close()
            браузер.close()
    finally:
        процесс.terminate()
        try:
            процесс.wait(timeout=20)
        except Exception:  # noqa: BLE001
            процесс.kill()
        shutil.rmtree(врем, ignore_errors=True)

    выход.mkdir(parents=True, exist_ok=True)
    (выход / f"{site_id}-edge.json").write_text(
        json.dumps(итог, ensure_ascii=False, indent=2), encoding="utf-8")
    итог["итог"] = "осмотр выполнен"
    return итог


def находки(итог: dict) -> list[str]:
    """Что из измеренного является дефектом. Правила названы, а не подразумеваются."""
    плохо: list[str] = []
    for имя, з in (итог.get("поиск") or {}).items():
        if з.get("код") != 200:
            плохо.append(f"поиск «{имя}»: код {з.get('код')} вместо 200")
            continue
        if имя == "пустой":
            if not з.get("форма поиска"):
                плохо.append("поиск с пустым запросом: нет формы ввода")
            if not з.get("подсказка"):
                плохо.append("поиск с пустым запросом: нет подсказки, что вводить")
        elif з.get("карточек") == 0 and not з.get("сообщение о пустой выдаче"):
            плохо.append(f"поиск «{имя}»: пустая выдача без сообщения")

    п = итог.get("пагинация") or {}
    for имя in ("первая", "вторая", "последняя"):
        з = п.get(имя) or {}
        if з.get("код") != 200:
            плохо.append(f"пагинация «{имя}»: код {з.get('код')} вместо 200")
        elif not (з.get("карточек") or 0):
            плохо.append(f"пагинация «{имя}»: 200 без карточек")
    for имя in ("за последней", "нечисловая", "нулевая", "отрицательная"):
        з = п.get(имя) or {}
        if з.get("код") != 404:
            плохо.append(f"пагинация «{имя}»: код {з.get('код')} вместо 404")

    for имя, з in (итог.get("ошибки") or {}).items():
        if з.get("код") != 404:
            плохо.append(f"ошибка «{имя}»: код {з.get('код')} вместо 404")
    ф = итог.get("фильтр без результатов") or {}
    if ф.get("карточек") == 0 and not ф.get("сообщение о пустой выдаче"):
        плохо.append("фильтр без результатов: пустая выдача без сообщения")
    с = итог.get("серии") or {}
    if с.get("проверено"):
        if с.get("серии без ссылки"):
            плохо.append(f"серии без ссылки на странице: {с['серии без ссылки']}")
        for имя in ("первая серия", "последняя серия"):
            если = с.get(имя) or {}
            if если.get("код") != 200:
                плохо.append(f"{имя}: код {если.get('код')}")
            elif not если.get("рамка плеера в разметке"):
                плохо.append(f"{имя}: нет рамки плеера в разметке")
    for имя, з in (итог.get("узкий телефон") or {}).items():
        if з.get("горизонтальная прокрутка"):
            плохо.append(f"узкий телефон, {имя}: горизонтальная прокрутка")
        if з.get("целей меньше минимума"):
            плохо.append(f"узкий телефон, {имя}: "
                         f"{з['целей меньше минимума']} целей меньше "
                         f"{МИНИМАЛЬНАЯ_ЦЕЛЬ} px — {з.get('примеры')}")
    return плохо


def не_пусто(запись: dict) -> bool:
    return (запись.get("карточек") or 0) > 0


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--site", action="append", required=True,
                   help="site_id витрины; можно повторять")
    р.add_argument("--data", required=True, help="каталог с доставленными данными")
    р.add_argument("--port", type=int, default=19500)
    р.add_argument("--out", default=None)
    а = р.parse_args()
    выход = Path(а.out or (КОРЕНЬ / "var" / "k2-data" / "edge"))

    всего_находок = 0
    сводка = []
    for н, site_id in enumerate(а.site):
        итог = главное(site_id, Path(а.data), а.port + н, выход)
        список = находки(итог) if итог.get("итог") == "осмотр выполнен" else [итог["итог"]]
        всего_находок += len(список)
        сводка.append({"site": site_id, "находок": len(список), "что": список})
        print(f"\n=== {site_id}: находок {len(список)}")
        for строка in список:
            print("   -", строка)
    (выход / "edge-all.json").write_text(
        json.dumps(сводка, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nвсего находок: {всего_находок}; сводка: {выход / 'edge-all.json'}")
    return 0 if всего_находок == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
