#!/usr/bin/env python3
"""Проверка ВОСПРОИЗВЕДЕНИЯ видео на карточке: браузер, а не код ответа.

    python3 automation/local/playback-check.py <домен> [слаг]

Ответ скрипта провайдера HTTP 200 воспроизведением не является — это и было
причиной завести проверку. Здесь поднимается настоящий Chromium, открывается
карточка, плеер запускается щелчком по центру кадра, и решение принимается по
состоянию элемента `<video>`:

* `currentTime` растёт между замерами — поток действительно декодируется;
* `readyState == 4` — данных достаточно, а не «началась загрузка»;
* `videoWidth/Height` называет фактическое разрешение; его смена по ходу
  (720p -> 1080p) означает работу адаптивного потока.

Две особенности, из-за которых наивная проверка даёт ложный отрицательный
ответ, и обе измерены на lordserials22.info 2026-10-04:

1. плеер VK держит `<video>` в SHADOW DOM, и `document.querySelectorAll` его
   не находит. Обход теневых корней обязателен;
2. запросы сегментов по расширению (`.m3u8`, `.ts`) не видны: источник —
   `blob:` через MSE, сегменты тянет код внутри кадра. Поэтому вывод делается
   по состоянию элемента, а не по перечню сетевых запросов.

Реклама в этом окружении отвечает 404 (`yandex.ru/ads/adfox/...`) — на старт
воспроизведения это не влияет, но в консоли видны ошибки VAST, и путать их с
отказом плеера нельзя.
"""
import json, re, sys, time
from playwright.sync_api import sync_playwright
ХРОМ = "/home/claude/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome"
ДОМЕН = sys.argv[1]
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
    paused: в.paused, err: в.error && в.error.code, w: в.videoWidth,
    h: в.videoHeight, src: (в.currentSrc || '').slice(0, 110)}));
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
with sync_playwright() as p:
    б = p.chromium.launch(executable_path=ХРОМ,
                          args=["--autoplay-policy=no-user-gesture-required"])
    к = б.new_context(ignore_https_errors=True, viewport={"width": 1280, "height": 800},
                      user_agent=("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                                  "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"))
    стр = к.new_page()
    медиа = []
    стр.on("response", lambda о: медиа.append((о.status, о.url))
           if re.search(r"\.(m3u8|ts|mp4|m4s|mpd)(\?|$)", о.url) else None)
    стр.goto(f"https://{ДОМЕН}/", wait_until="domcontentloaded", timeout=60000)
    путь = стр.eval_on_selector('a[href^="/title/"]', "э => э.getAttribute('href')")
    стр.goto(f"https://{ДОМЕН}{путь}", wait_until="load", timeout=60000)
    print("АДРЕС:", f"https://{ДОМЕН}{путь}")
    стр.wait_for_timeout(5000)
    кадр = next((ф for ф in стр.frames if "player.cdnvideohub" in ф.url), None)
    if кадр is None:
        print("кадра плеера нет"); б.close(); raise SystemExit(1)
    # Щелчок по центру кадра — как делает человек.
    try:
        рамка = стр.query_selector("iframe[src*=cdnvideohub]").bounding_box()
        стр.mouse.click(рамка["x"] + рамка["width"]/2, рамка["y"] + рамка["height"]/2)
        print("щелчок по центру плеера: сделан")
    except Exception as e:
        print("щелчок:", type(e).__name__, str(e)[:80])
    замеры = []
    for н in range(16):
        стр.wait_for_timeout(2000)
        try:
            сколько = кадр.evaluate(ПУСК)
            состояние = кадр.evaluate(ОБХОД)
        except Exception as e:
            сколько, состояние = -1, [{"ошибка": f"{type(e).__name__}: {str(e)[:80]}"}]
        замеры.append(состояние)
        if н in (0, 5, 10, 15):
            print(f"  замер {н}: видео {сколько} | {json.dumps(состояние, ensure_ascii=False)[:220]}")
    времена = [max([в.get("t") or 0 for в in с] or [0]) for с in замеры]
    print("currentTime:", [round(т, 2) for т in времена])
    print("ВЫВОД: воспроизведение", "ИДЁТ" if max(времена) - min(времена) > 0.5 else "НЕ ЗАФИКСИРОВАНО")
    print("медиа-ответы:", len(медиа))
    for с, u in медиа[:8]: print("   ", с, u[:110])
    б.close()
