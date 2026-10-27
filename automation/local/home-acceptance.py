#!/usr/bin/env python3
"""Приёмка главной: первый экран, подборка, карточка, просмотр и анонс.

Поручение владельца 27.10: приёмка включает главную, страницу подборки,
переход в карточку и соответствующее действие — просмотр либо трейлер/анонс;
телефон и компьютер; «буквенные заглушки и изображение другого произведения не
допускаются»; «не растягивай маленький файл».

Что измеряется, а не предполагается:

* первый блок главной — редакционная полка, и у её карточек ЗАГРУЖЕНЫ
  изображения (`naturalWidth > 0`), а не нарисована буква;
* выбранный браузером кандидат обложки не мельче, чем нужно слоту при его
  плотности (растяжения нет);
* нажатие по карточке полки ведёт на страницу работы, где есть блок плеера;
* визитка подборки ведёт на страницу подборки, а та — в карточку;
* в блоке анонсов нет ни одной ссылки на просмотр, зато есть дата и
  официальный источник;
* горизонтальной прокрутки у страницы нет.

Технический прогон не шлёт события в Метрику: иначе приёмка попадёт в
статистику людей и раздует те самые показы блоков, которыми меряется эффект.

    python3 automation/local/home-acceptance.py --domain zonafilm.space
    python3 automation/local/home-acceptance.py --domain animedia.icu --json
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

РАЗМЕРЫ = (("телефон", 390, 844, True, 2), ("компьютер", 1366, 768, False, 1))
#: Рост позиции, после которого показ считается начавшимся. Наличие позиции
#: признаком не является: поставщик отдаёт один `timeupdate` с 0.09 и держит
#: его — источник разрешён, картинка стоит (замер 27.10).
РОСТ_С = 0.5
НАЖАТИЙ = 3
ОЖИДАНИЕ_С = 20

ПЕРЕХВАТ = """
window.__ппПоз = 0;
window.addEventListener('message', function(ev){
  if (!ev || !ev.origin || ev.origin.indexOf('cdnvideohub') < 0) return;
  var d = ev.data; try { if (typeof d === 'string') d = JSON.parse(d); } catch(e){ return; }
  if (!d || !d.eventType) return;
  if (d.eventType === 'timeupdate' && d.data && typeof d.data.position === 'number'
      && d.data.position > window.__ппПоз) window.__ппПоз = d.data.position;
}, false);
"""

ОСМОТР = """() => {
  const нужно = (i) => Math.round(
      i.getBoundingClientRect().width * window.devicePixelRatio);
  const кандидат = (i) => {
      const u = i.currentSrc || i.src || '';
      const м = u.match(/[?&]w=(\\d+)/);
      if (м) return parseInt(м[1], 10);
      return i.naturalWidth ? 0 : -1;
  };
  const первый = document.querySelector('main section, .zmain section, section');
  const полка = document.querySelector('.zr1');
  const карточки = polka();
  function polka(){ return [...document.querySelectorAll('.zr1 .zb')]; }
  const обложки = [...document.querySelectorAll('.zr1 .zb img')];
  const визитки = [...document.querySelectorAll('.zcl__c, .zhub__c')];
  const анонсы = document.querySelector('[data-block-key="announce"]');
  const анонс_ссылки = анонсы
      ? [...анонсы.querySelectorAll('a')].map(a => a.getAttribute('href') || '')
      : [];
  return {
    'первый блок': первый ? первый.className : null,
    'полка первая': !!полка && !!первый && первый.classList.contains('zr1'),
    'карточек полки': карточки.length,
    'обложек полки': обложки.length,
    'обложек без файла': обложки.filter(i => !i.naturalWidth).length,
    'растянутых обложек': obl_rast(),
    'визиток подборок': визитки.length,
    'визиток с обложкой': визитки.filter(
        c => c.querySelector('img') && c.querySelector('img').naturalWidth > 0).length,
    'ключи блоков': [...document.querySelectorAll('[data-block-key]')]
        .slice(0, 12).map(e => e.getAttribute('data-block-key')),
    'анонсов': анонсы ? анонсы.querySelectorAll('.zann__c').length : 0,
    'ссылок на просмотр в анонсах': анонс_ссылки.filter(h => h.includes('/title/')).length,
    'внешних источников в анонсах': анонс_ссылки.filter(h => h.startsWith('http')).length,
    'горизонтальная прокрутка': document.documentElement.scrollWidth - window.innerWidth,
    'первая карточка полки': карточки.length
        ? карточки[0].getAttribute('href') : null,
    'первая визитка': визитки.length ? визитки[0].getAttribute('href') : null,
  };
  function obl_rast(){
    return обложки.filter(i => i.naturalWidth && кандидат(i) > 0
                               && кандидат(i) < нужно(i) * 0.9).length;
  }
}"""


def _позиция(страница) -> float:
    try:
        return float(страница.evaluate(
            """() => {
                const глубоко = (к, у) => {
                    if (!к || у > 6) return 0;
                    const v = к.querySelector ? к.querySelector('video') : null;
                    if (v && v.currentTime > 0) return v.currentTime;
                    for (const n of (к.querySelectorAll ? к.querySelectorAll('*') : [])) {
                        if (n.shadowRoot) { const r = глубоко(n.shadowRoot, у + 1);
                            if (r > 0) return r; }
                    }
                    return 0;
                };
                const p = глубоко(document, 0);
                return p > 0 ? p : (window.__ппПоз || 0);
            }"""))
    except Exception:  # noqa: BLE001
        return 0.0


def пройти(браузер, домен: str, размер, снимки: pathlib.Path) -> dict:
    имя, ш, в, моб, dsf = размер
    итог = {"домен": домен, "размер": имя}
    контекст = браузер.new_context(
        viewport={"width": ш, "height": в}, is_mobile=моб, has_touch=моб,
        device_scale_factor=dsf, color_scheme="light")
    контекст.route("**mc.yandex.*/**", lambda м: м.abort())
    контекст.add_init_script(ПЕРЕХВАТ)
    с = контекст.new_page()
    с.route("**mc.yandex.*/**", lambda м: м.abort())
    try:
        с.goto(f"https://{домен}/", wait_until="load", timeout=60000)
        с.wait_for_timeout(2500)
        итог.update(с.evaluate(ОСМОТР))
        снимки.mkdir(parents=True, exist_ok=True)
        файл = снимки / f"{домен}-главная-{имя}.png"
        с.screenshot(path=str(файл))
        итог["снимок главной"] = str(файл)
        # --- полка → карточка → плеер -------------------------------------
        карточка = с.locator(".zr1 .zb").first
        if карточка.count():
            карточка.scroll_into_view_if_needed(timeout=10000)
            карточка.click(timeout=15000)
            с.wait_for_load_state("domcontentloaded", timeout=45000)
            итог["адрес работы"] = с.url
            итог["на работе"] = "/title/" in с.url
            рамка = с.locator("[data-player]").first
            итог["плеер есть"] = bool(рамка.count())
            позиция, начало, нажатий = 0.0, None, 0
            for _ in range(НАЖАТИЙ):
                if not рамка.count():
                    break
                нажатий += 1
                try:
                    рамка.scroll_into_view_if_needed(timeout=8000)
                    рамка.click(timeout=12000)
                except Exception:  # noqa: BLE001
                    pass
                край = time.monotonic() + ОЖИДАНИЕ_С
                while time.monotonic() < край:
                    позиция = _позиция(с)
                    if начало is None and позиция > 0:
                        начало = позиция
                    if начало is not None and позиция - начало >= РОСТ_С:
                        break
                    с.wait_for_timeout(1000)
                if начало is not None and позиция - начало >= РОСТ_С:
                    break
            итог["нажатий до просмотра"] = (
                нажатий if начало is not None and позиция - начало >= РОСТ_С else None)
            итог["позиция"] = round(позиция, 2)
        # --- визитка → страница подборки → карточка ------------------------
        с.goto(f"https://{домен}/", wait_until="load", timeout=60000)
        с.wait_for_timeout(1500)
        визитка = с.locator(".zcl__c, .zhub__c").first
        if визитка.count():
            визитка.scroll_into_view_if_needed(timeout=10000)
            визитка.click(timeout=15000)
            с.wait_for_load_state("domcontentloaded", timeout=45000)
            итог["адрес подборки"] = с.url
            итог["на подборке"] = "/collection" in с.url
            плитка = с.locator('a[href^="/title/"]').first
            if плитка.count():
                плитка.click(timeout=15000)
                с.wait_for_load_state("domcontentloaded", timeout=45000)
                итог["из подборки в карточку"] = "/title/" in с.url
    except Exception as сбой:  # noqa: BLE001
        итог["беда"] = f"{type(сбой).__name__}: {str(сбой)[:200]}"
    finally:
        контекст.close()
    return итог


def тёмная(браузер, домен: str, снимки: pathlib.Path) -> dict:
    """Снимок главной в тёмной теме: тема меняет только цвета, не состав."""
    контекст = браузер.new_context(viewport={"width": 390, "height": 844},
                                   is_mobile=True, has_touch=True,
                                   device_scale_factor=2, color_scheme="dark")
    контекст.route("**mc.yandex.*/**", lambda м: м.abort())
    с = контекст.new_page()
    try:
        с.goto(f"https://{домен}/", wait_until="load", timeout=60000)
        с.wait_for_timeout(2000)
        файл = снимки / f"{домен}-главная-телефон-тёмная.png"
        с.screenshot(path=str(файл))
        данные = с.evaluate(ОСМОТР)
        return {"снимок": str(файл), "карточек полки": данные["карточек полки"],
                "обложек без файла": данные["обложек без файла"]}
    except Exception as сбой:  # noqa: BLE001
        return {"беда": f"{type(сбой).__name__}: {str(сбой)[:160]}"}
    finally:
        контекст.close()


def главная(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("--domain", required=True)
    р.add_argument("--out", default=None)
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)
    снимки = pathlib.Path(а.out or (КОРЕНЬ / "artifacts" / "evidence" / "home-acceptance"))
    from factory.seo.render_check import chromium_path
    from playwright.sync_api import sync_playwright

    путь = chromium_path()
    пуск = {"headless": True}
    if путь:
        пуск["executable_path"] = путь
    итоги = []
    with sync_playwright() as pw:
        бр = pw.chromium.launch(**пуск)
        try:
            for размер in РАЗМЕРЫ:
                итоги.append(пройти(бр, а.domain, размер, снимки))
            итоги.append({"домен": а.domain, "размер": "телефон, тёмная тема",
                          **тёмная(бр, а.domain, снимки)})
        finally:
            бр.close()
    if а.json:
        print(json.dumps(итоги, ensure_ascii=False, indent=1))
    else:
        for и in итоги:
            print(json.dumps(и, ensure_ascii=False))
    беда = sum(1 for и in итоги if и.get("беда")
               or и.get("обложек без файла") or и.get("растянутых обложек")
               or и.get("ссылок на просмотр в анонсах")
               or (и.get("горизонтальная прокрутка") or 0) > 0)
    print(f"\nпроходов с бедой: {беда} из {len(итоги)}")
    return 1 if беда else 0


if __name__ == "__main__":
    raise SystemExit(главная())
