#!/usr/bin/env python3
"""Публичный путь к просмотру через подборку — ДЕЙСТВИЕМ в браузере.

Поручение владельца 27.10: «проверь публичный путь на телефоне и компьютере:
главная/раздел → подборка → карточка → просмотр». Коды ответа на этот вопрос
не отвечают: страница отдаёт 200 и со сломанной ссылкой, и с плеером, который
не стартует с первого нажатия.

Проходит ровно тот путь, которым идёт читатель, в двух размерах — телефон
390×844 и компьютер 1366×768:

  1. открыть вход (главную или раздел-владельца);
  2. НАЙТИ на нём ссылку на подборку и нажать её — не перейти по адресу, а
     нажать: ссылка, закрытая чужим блоком, кодом 200 не отличается от рабочей;
  3. на странице подборки нажать ПЕРВУЮ карточку состава;
  4. на странице работы нажать плеер ОДИН раз и дождаться, пока
     `currentTime > 0`.

Шаг 4 отвечает и на вопрос T338 («второе нажатие»): если воспроизведение
начинается только со второго нажатия, здесь это видно числом попыток, а не на
слух. Никакие нажатия не повторяются молча: счётчик попыток в отчёте.

Только чтение: ничего не публикуется и не меняется, кроме снимков экрана в
каталоге отчёта.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
if str(КОРЕНЬ) not in sys.path:
    sys.path.insert(0, str(КОРЕНЬ))

#: Размеры: телефон первым, потому что доля мобильного трафика выше и беда чаще
#: именно там (перекрытие плеера панелью, невидимая ссылка под шапкой).
РАЗМЕРЫ = (("телефон", 390, 844, True), ("компьютер", 1366, 768, False))
#: Сколько ждать начала воспроизведения после ОДНОГО нажатия.
ОЖИДАНИЕ_С = 25
#: Сколько нажатий допустимо всего. Второе нажатие — уже дефект (T338), но
#: измерить его надо, а не предположить.
НАЖАТИЙ = 3


def _плеер_играет(страница) -> float:
    """Текущая позиция воспроизведения, 0.0 — не играет.

    Источников два, и оба нужны: витрина может показывать <video> напрямую или
    фрейм поставщика, у которого позиция приходит сообщением и складывается в
    `window.__pmLastPos` (так устроена подтверждающая проводка плеера).
    """
    try:
        return float(страница.evaluate(
            """() => {
                const v = document.querySelector('video');
                if (v && !Number.isNaN(v.currentTime) && v.currentTime > 0)
                    return v.currentTime;
                const p = window.__pmLastPos;
                return (typeof p === 'number' && p > 0) ? p : 0;
            }"""))
    except Exception:  # noqa: BLE001 — страница могла уйти на переход
        return 0.0


def пройти(домен: str, вход: str, ключ: str, размер: tuple, снимки: pathlib.Path,
           страница_фабрики) -> dict:
    имя, ширина, высота, мобильный = размер
    итог = {"размер": имя, "вход": вход, "подборка": ключ}
    контекст = страница_фабрики.new_context(
        viewport={"width": ширина, "height": высота},
        is_mobile=мобильный, has_touch=мобильный,
        user_agent=("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                    "Mobile/15E148 Safari/604.1") if мобильный else None)
    страница = контекст.new_page()
    try:
        страница.goto(f"https://{домен}{вход}", wait_until="domcontentloaded",
                      timeout=45000)
        адрес = f"/collection/{ключ}/"
        ссылка = страница.locator(f'a[href="{адрес}"]').first
        итог["ссылка видна"] = bool(ссылка.count()) and ссылка.is_visible()
        if not итог["ссылка видна"]:
            итог["беда"] = f"на {вход} нет видимой ссылки на {адрес}"
            return итог
        ссылка.scroll_into_view_if_needed(timeout=10000)
        ссылка.click(timeout=15000)
        страница.wait_for_load_state("domcontentloaded", timeout=45000)
        итог["адрес подборки"] = страница.url
        итог["на подборке"] = адрес in страница.url
        карточки = страница.locator('.col__i a[href^="/title/"]')
        итог["карточек в составе"] = карточки.count()
        if not карточки.count():
            итог["беда"] = "на странице подборки нет карточек состава"
            return итог
        первая = карточки.first
        итог["первая работа"] = первая.get_attribute("href")
        первая.scroll_into_view_if_needed(timeout=10000)
        первая.click(timeout=15000)
        страница.wait_for_load_state("domcontentloaded", timeout=45000)
        итог["адрес работы"] = страница.url
        итог["на работе"] = "/title/" in страница.url
        # --- просмотр: ОДНО нажатие, потом ожидание ---------------------------
        рамка = страница.locator("[data-player]").first
        итог["плеер есть"] = bool(рамка.count())
        if not рамка.count():
            итог["беда"] = "на странице работы нет блока плеера"
            return итог
        позиция, нажатий = 0.0, 0
        for _ in range(НАЖАТИЙ):
            нажатий += 1
            try:
                рамка.scroll_into_view_if_needed(timeout=10000)
                рамка.click(timeout=15000)
            except Exception as сбой:  # noqa: BLE001
                итог.setdefault("нажатие не удалось", str(сбой)[:160])
            край = time.monotonic() + ОЖИДАНИЕ_С
            while time.monotonic() < край:
                позиция = _плеер_играет(страница)
                if позиция > 0:
                    break
                страница.wait_for_timeout(500)
            if позиция > 0:
                break
        итог["нажатий до старта"] = нажатий if позиция > 0 else None
        итог["позиция"] = round(позиция, 2)
        итог["просмотр начался"] = позиция > 0
        снимки.mkdir(parents=True, exist_ok=True)
        файл = снимки / f"{домен}-{ключ}-{имя}.png"
        страница.screenshot(path=str(файл), full_page=False)
        итог["снимок"] = str(файл)
    except Exception as сбой:  # noqa: BLE001
        итог["беда"] = f"{type(сбой).__name__}: {str(сбой)[:200]}"
    finally:
        контекст.close()
    return итог


def главная(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("--domain", required=True)
    р.add_argument("--entry", default="/", help="вход: / или /movies/")
    р.add_argument("--collection", required=True, help="ключ подборки")
    р.add_argument("--out", default=None)
    а = р.parse_args(аргв)
    снимки = pathlib.Path(а.out or (КОРЕНЬ / "artifacts" / "evidence"
                                    / "collection-path"))
    from factory.seo.render_check import chromium_path
    from playwright.sync_api import sync_playwright

    путь_хрома = chromium_path()
    пуск = {"headless": True}
    if путь_хрома:
        пуск["executable_path"] = путь_хрома
    итоги = []
    with sync_playwright() as pw:
        браузер = pw.chromium.launch(**пуск)
        try:
            for размер in РАЗМЕРЫ:
                итоги.append(пройти(а.domain, а.entry, а.collection, размер,
                                    снимки, браузер))
        finally:
            браузер.close()
    беда = 0
    for и in итоги:
        if и.get("беда") or not и.get("просмотр начался"):
            беда += 1
        print(json.dumps(и, ensure_ascii=False))
    print(f"\nпроходов с бедой: {беда} из {len(итоги)}")
    return 1 if беда else 0


if __name__ == "__main__":
    raise SystemExit(главная())
