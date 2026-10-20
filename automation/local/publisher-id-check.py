#!/usr/bin/env python3
"""Фактический `publisher_id` в ЗАПРОСАХ плеера, а не только в разметке.

    python3 automation/local/publisher-id-check.py <домен> [слаг]
    python3 automation/local/publisher-id-check.py http://lordfilm.group/ \
        --map=lordfilm.group=145.63.129.86      # до перевода DNS: на узел

Зачем смотреть запросы, а не атрибут
------------------------------------

Витрина рендерит `data-publisher-id` в разметку страницы, и прочитать его
можно одним `curl`. Но это ВХОД: значение берётся из `config/player.json`
выпуска и отдаётся SDK провайдера. Что ушло в сам провайдер — видно только в
запросах кадра плеера, и именно это решает, чей поток играет.

Поэтому проверка делает три вещи сразу:

* читает `data-publisher-id` из DOM (вход);
* перехватывает запросы к `player.cdnvideohub.com` и вынимает из них значения
  `publisher`-параметров (что ушло провайдеру);
* подтверждает, что воспроизведение действительно идёт, — иначе совпадение
  идентификаторов ничего не значит: поток может не играть вовсе.

Плеер VK держит `<video>` в теневом DOM, а сегменты тянет через MSE из
`blob:`, поэтому решение принимается по состоянию элемента, а не по перечню
сетевых запросов (см. `playback-check.py`).
"""
from __future__ import annotations

import json
import re
import sys

from pathlib import Path
from playwright.sync_api import sync_playwright

КОРЕНЬ_ФАБРИКИ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ_ФАБРИКИ))

from factory.seo.render_check import chromium_path  # noqa: E402

#: Путь к готовой сборке Chromium. Номер сборки здесь НЕ вписывается числом:
#: закреплённый номер однажды выключил браузерную приёмку целиком (на машине с
#: другой сборкой проверка сообщала «Chromium не найден»). Поиск общий —
#: `factory.seo.render_check.chromium_path`: явный `FACTORY_CHROMIUM`, затем
#: известные каталоги, затем шаблон от новой сборки к старой.
ХРОМ = chromium_path() or ""
#: Проверенные формы адреса карточки — те же, что в `registry.ФОРМА_АДРЕСА`.
ПРЕФИКСЫ = ("/title/", "/anime/")
#: Первым аргументом принимается домен ИЛИ готовый базовый адрес
#: (`http://127.0.0.1:19400`): витрина, которая ещё не живёт публично,
#: проверяется на локальном стенде теми же мерками.

ОБХОД = """
() => {
  const найденные = [];
  const обойти = (корень) => {
    корень.querySelectorAll('*').forEach(э => {
      if (э.tagName === 'VIDEO') найденные.push(э);
      if (э.shadowRoot) обойти(э.shadowRoot);
    });
  };
  обойти(document);
  return найденные.map(в => ({t: в.currentTime, ready: в.readyState,
    w: в.videoWidth, h: в.videoHeight}));
}
"""

ПУСК = """
() => {
  const видео = [];
  const обойти = (корень) => {
    корень.querySelectorAll('*').forEach(э => {
      if (э.tagName === 'VIDEO') видео.push(э);
      if (э.shadowRoot) обойти(э.shadowRoot);
    });
  };
  обойти(document);
  видео.forEach(в => { в.muted = true; const п = в.play(); if (п) п.catch(()=>{}); });
  return видео.length;
}
"""

#: Как идентификатор издателя появляется в запросах провайдера.
#:
#: Измерено 2026-10-05 на lordserials22.info: SDK запрашивает плейлист
#: `https://plapi.cdnvideohub.com/api/v1/player/sv/playlist?pub=10238&aggr=cvh&id=…`
#: — то есть параметр называется `pub`, а не `publisher_id`. Искать только
#: длинное имя значило бы не найти ничего и назвать это «не передаётся».
ИЗ_ЗАПРОСА = re.compile(
    r"(?:\bpub|publisher[_-]?id|publisherId|pub[_-]?id)=([0-9]{3,8})",
    re.IGNORECASE)


def главная(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    # `--map <имя>=<адрес>` разрешает имя в заданный узел средствами самого
    # Chromium. Нужно до перевода DNS: публичное имя ведёт на ПРЕЖНИЙ сервер,
    # и проверка по имени измерила бы старую копию, а стенд меряет тот же код,
    # но не тот путь — мимо nginx узла, его upstream и установленного там
    # config/player.json. Заголовок Host при этом остаётся верным, поэтому
    # nginx выбирает блок именно этой витрины; подмена Host через
    # extraHTTPHeaders так не работает — Chromium его менять не даёт.
    карта: list[str] = []
    остаток: list[str] = []
    for арг in argv:
        if арг.startswith("--map="):
            имя, _, адрес = арг[len("--map="):].partition("=")
            if not (имя and адрес):
                print(f"нужен вид --map=имя=адрес, получено {арг!r}")
                return 2
            карта.append(f"MAP {имя} {адрес}")
        else:
            остаток.append(арг)
    argv = остаток
    if not argv:
        print("нужен домен или базовый адрес")
        return 2
    домен = argv[0]
    слаг = argv[1] if len(argv) > 1 else ""

    доводы = ["--autoplay-policy=no-user-gesture-required"]
    if карта:
        # Адрес плеера (`player.cdnvideohub.com`) правилу не подчиняется:
        # перечислено только то, что названо явно, и запрос к провайдеру идёт
        # обычным путём. Иначе проверка измеряла бы ещё и чужой origin.
        доводы.append("--host-resolver-rules=" + ",".join(карта))
        print("разрешение имени:", "; ".join(карта))

    with sync_playwright() as p:
        б = p.chromium.launch(executable_path=ХРОМ, args=доводы)
        к = б.new_context(ignore_https_errors=True,
                          viewport={"width": 1280, "height": 800})
        стр = к.new_page()
        запросы: list[str] = []
        стр.on("request", lambda з: запросы.append(з.url)
               if "cdnvideohub" in з.url else None)

        # База: домен превращается в https-адрес, а готовый адрес берётся как
        # есть. Так один инструмент проверяет и живую витрину, и локальный
        # стенд — мерки при этом одни и те же.
        # Хвостовая косая снимается: иначе адрес склеивался в
        # `http://домен//`, и проверка ждала страницу, которой нет.
        БАЗА = (домен if домен.startswith("http")
                else f"https://{домен}").rstrip("/")
        if слаг:
            путь = f"/title/{слаг}/"
        else:
            стр.goto(f"{БАЗА}/", wait_until="domcontentloaded",
                     timeout=60000)
            путь = ""
            for префикс in ПРЕФИКСЫ:
                ссылки = стр.query_selector_all(f'a[href^="{префикс}"]')
                if ссылки:
                    путь = ссылки[0].get_attribute("href")
                    break
            if not путь:
                print("на главной нет ссылок проверенной формы: "
                      + ", ".join(ПРЕФИКСЫ))
                б.close()
                return 1
        адрес = f"{БАЗА}{путь}"
        стр.goto(адрес, wait_until="load", timeout=60000)
        print("АДРЕС:", адрес)

        # 1. ВХОД: что витрина отдала в разметку.
        в_разметке = стр.eval_on_selector_all(
            "[data-publisher-id]",
            "узлы => узлы.map(у => у.getAttribute('data-publisher-id'))")
        print("data-publisher-id в разметке:", sorted(set(в_разметке)) or "нет")

        стр.wait_for_timeout(5000)
        кадр = next((ф for ф in стр.frames if "player.cdnvideohub" in ф.url), None)
        if кадр is None:
            for селектор in ('[class*="player-shell"]', '[id*="player"]',
                             '[class*="pl__frame"]', '[class*="player"]'):
                узел = стр.query_selector(селектор)
                if узел is None:
                    continue
                try:
                    узел.click(timeout=5000)
                except Exception:  # noqa: BLE001
                    continue
                стр.wait_for_timeout(6000)
                кадр = next((ф for ф in стр.frames
                             if "player.cdnvideohub" in ф.url), None)
                if кадр is not None:
                    break
        if кадр is None:
            print("кадра плеера нет: ни при загрузке, ни после щелчка")
            print("запросы к провайдеру:", len(запросы))
            б.close()
            return 1

        try:
            рамка = стр.query_selector("iframe[src*=cdnvideohub]").bounding_box()
            стр.mouse.click(рамка["x"] + рамка["width"] / 2,
                            рамка["y"] + рамка["height"] / 2)
        except Exception:  # noqa: BLE001
            pass
        стр.wait_for_timeout(2000)
        if not кадр.evaluate(ОБХОД):
            for селектор in ("button[aria-label*=оспроизв]", "button"):
                узел = кадр.query_selector(селектор)
                if узел is None:
                    continue
                try:
                    узел.click(timeout=5000)
                    break
                except Exception:  # noqa: BLE001
                    continue

        замеры = []
        for н in range(12):
            стр.wait_for_timeout(2000)
            try:
                кадр.evaluate(ПУСК)
                состояние = кадр.evaluate(ОБХОД)
            except Exception as ош:  # noqa: BLE001
                состояние = [{"ошибка": type(ош).__name__}]
            времена = [з.get("t") for з in состояние if isinstance(з, dict)
                       and isinstance(з.get("t"), (int, float))]
            замеры.append(round(max(времена), 2) if времена else 0.0)

        # 2. ЧТО УШЛО ПРОВАЙДЕРУ.
        из_запросов: set[str] = set()
        for url in запросы:
            из_запросов.update(ИЗ_ЗАПРОСА.findall(url))
        print("publisher_id в запросах провайдера:", sorted(из_запросов) or "нет")
        print("адресов к провайдеру:", len(запросы))
        for url in запросы[:3]:
            print("   ", url[:150])

        # 3. ИДЁТ ЛИ ВОСПРОИЗВЕДЕНИЕ.
        print("currentTime:", замеры)
        растёт = len([1 for а, б2 in zip(замеры, замеры[1:], strict=False) if б2 > а]) >= 3
        print("ВЫВОД:", "воспроизведение ИДЁТ" if растёт
              else "воспроизведение НЕ ЗАФИКСИРОВАНО")
        б.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(главная(sys.argv[1:]))
