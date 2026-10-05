#!/usr/bin/env python3
"""Что показывает плеер САМ, без единого нажатия: путь обычного посетителя.

    python3 automation/local/player-idle-check.py <домен|полный адрес> [секунды]

Зачем отдельный инструмент рядом с `playback-check.py`
------------------------------------------------------

`playback-check.py` щёлкает по кадру СРАЗУ и доказывает, что поток
декодируется. Это нужная проверка, и она закрывает вопрос «играет ли видео,
если посетитель нажал пуск». Но сторож плеера в выложенном коде устроен так,
что из своих таймеров выходит по условию `playing`:

    setTimeout(function(){ if(... || playing) return; ... }, 25000)

То есть при начавшемся воспроизведении сторож безвреден, и проверка с
немедленным нажатием НЕ МОЖЕТ его увидеть — по построению, а не по
невезению. Посетитель же нередко открывает карточку и ждёт: у него
воспроизведение не начато, `playing` ложно, и таймеры срабатывают.

Измерено 2026-10-05 на живом `zonafilm.cc/title/100-atletov-italiya/` без
единого нажатия:

      0.0 с  state=resolving
      5.1 с  state=ready
     25.2 с  state=resolving      <- сторож пересоздал плеер на 25-й секунде
     30.3 с  state=ready
     50.4 с  state=provider, показан блок
             «Видео временно недоступно. Попробуйте другую озвучку или
              вернитесь позже.»

Поэтому к проверке «играет после нажатия» добавляется эта: «что увидит тот,
кто не нажимал». Вывод — по тому, что ВИДНО посетителю (`data-state` корня и
видимость блока состояния), а не по перечню сетевых запросов.
"""
import json
import sys
import time

from playwright.sync_api import sync_playwright

ХРОМ = "/home/claude/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome"
#: Те же проверенные формы адреса карточки, что у `playback-check.py`.
ПРЕФИКСЫ = ("/title/", "/anime/")
#: Состояния, при которых посетитель видит отказ, а не ожидание.
ОТКАЗНЫЕ = ("provider", "unavailable", "error", "nosource")

ОПРОС = """
() => {
  const f = document.querySelector('[data-player]');
  const st = f && f.querySelector('[data-player-state]');
  const видно = !!(st && !st.hasAttribute('hidden') && st.offsetParent !== null);
  const видео = [];
  const обойти = (корень) => {
    корень.querySelectorAll('*').forEach(э => {
      if (э.tagName === 'VIDEO') видео.push(э);
      if (э.shadowRoot) обойти(э.shadowRoot);
    });
  };
  обойти(document);
  const v = видео[0];
  return {
    state: f ? f.getAttribute('data-state') : null,
    state_visible: видно,
    state_text: видно ? (st.innerText || '').replace(/\\s+/g, ' ').slice(0, 100) : '',
    videos: видео.length,
    t: v ? Number(v.currentTime.toFixed(2)) : null,
    ready: v ? v.readyState : null,
  };
}
"""


def адрес_карточки(стр, домен: str) -> str:
    """Первая ссылка на карточку с главной. Адрес не выдумывается."""
    стр.goto(f"https://{домен}/", wait_until="domcontentloaded", timeout=60000)
    for префикс in ПРЕФИКСЫ:
        ссылки = стр.eval_on_selector_all(
            f'a[href*="{префикс}"]', "ээ => ээ.map(э => э.getAttribute('href'))")
        свои = [с for с in ссылки if с and с.startswith(префикс)]
        if свои:
            return f"https://{домен}{свои[0]}"
    raise SystemExit(f"{домен}: ссылок на карточку не найдено; формы: "
                     + ", ".join(ПРЕФИКСЫ))


def главная(argv: list[str]) -> int:
    если = argv[1] if len(argv) > 1 else ""
    if not если:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    срок = float(argv[2]) if len(argv) > 2 else 130.0
    with sync_playwright() as p:
        б = p.chromium.launch(executable_path=ХРОМ, args=["--no-sandbox"])
        стр = б.new_page()
        адрес = если if если.startswith("http") else адрес_карточки(стр, если)
        print(f"АДРЕС: {адрес}  (без единого нажатия, {срок:.0f} с)")
        стр.goto(адрес, wait_until="domcontentloaded", timeout=60000)
        начало = time.time()
        линия = []
        while time.time() - начало < срок:
            прошло = round(time.time() - начало, 1)
            try:
                з = стр.evaluate(ОПРОС)
            except Exception as ош:  # noqa: BLE001 — причина называется в отчёте
                з = {"ошибка": f"{type(ош).__name__}: {str(ош)[:60]}"}
            линия.append({"с": прошло, **з})
            time.sleep(5)
        б.close()

    прежнее = None
    for з in линия:
        ключ = (з.get("state"), з.get("state_visible"), з.get("videos"),
                з.get("ready"))
        if ключ != прежнее:
            print(f"  {з['с']:6.1f} с  state={str(з.get('state')):12} "
                  f"блок={з.get('state_visible')} видео={з.get('videos')} "
                  f"ready={з.get('ready')} t={з.get('t')}"
                  + (f"  текст={з.get('state_text')!r}"
                     if з.get("state_text") else ""))
            прежнее = ключ
    отказ = [з for з in линия
             if з.get("state_visible") or str(з.get("state")) in ОТКАЗНЫЕ]
    пересоздания = sum(
        1 for а, б2 in zip(линия, линия[1:])
        if а.get("state") in ("ready", "playing", "ok")
        and б2.get("state") == "resolving")
    print(f"пересозданий плеера (ready -> resolving): {пересоздания}")
    if отказ:
        print(f"ВЫВОД: посетитель БЕЗ НАЖАТИЯ видит отказ на {отказ[0]['с']} с: "
              f"{отказ[0].get('state')} {отказ[0].get('state_text') or ''}".strip())
        return 3
    print("ВЫВОД: за весь срок отказа посетитель не видит")
    print("состояния:", json.dumps(sorted({str(з.get('state')) for з in линия}),
                                   ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(главная(sys.argv))
