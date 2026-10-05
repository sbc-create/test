"""Сторож плеера считает время от нажатия Play и не идёт во время рекламы.

Замер 2026-10-05 (СКОРОСТЬ — СЕТЬ САЙТОВ, docs/PERF_NETWORK_AUDIT_20261005.md
фабрики), страница фильма /title/ad-dzheffri/:

* после нажатия Play идёт преролл провайдера; на 25-й секунде ОТ ЗАГРУЗКИ
  СТРАНИЦЫ клиентский скрипт удалял `<video-player>` и монтировал следующий
  источник (`removed/added <video-player>` на 25 050 мс, состояние
  `resolving`) — реклама обрывалась, и посетитель снова видел кнопку Play;
* посетитель, который просто читал страницу, через 25 с получал замену
  плеера, ещё через 25 с — вторую, а на 110-й секунде — «Видео временно
  недоступно» на исправном фильме.

Причина — в `СКРИПТ_ПЛЕЕРА_КЛИЕНТ` закреплённого рантайма: таймеры
`timeout-no-playing` (25 с) и показа отказа (35 с) взводились в `bind()`, то
есть при монтировании плеера, и не знали ни о нажатии, ни о рекламе.

Правка — та же логика, но с правильной точкой отсчёта:

* таймеры «нет воспроизведения» и «показать отказ» взводятся по сообщению
  провайдера `requestPlay` (посетитель нажал Play);
* на время рекламы (`adStart` / `rollState: start`) они снимаются и заново
  взводятся по её окончании (`adComplete` / `adClosed` / `rollState` с другим
  состоянием / `adError` / `adSkipped`);
* таймер `timeout-no-ready` (10 с без `ready` после монтирования) не
  меняется: это настоящий отказ провайдера, а не ожидание посетителя.

Закреплённый артефакт не меняется: подменяется значение константы при
загрузке рантайма, как это делают правки themes/snapshot. Каждый якорь
обязан найтись ровно один раз; иначе запуск отказывает — молча работать с
прежним сторожем нельзя. Проверка — checks/player_watchdog.py.
"""

from __future__ import annotations

ИМЯ_ПРАВКИ = "сторож плеера: таймеры от нажатия Play, пауза на рекламу"

ЗАМЕНЫ = (
    (
        " var maxFallback=3, baseAttrs={}, lastPos=0, readyAt=0, activeSource=null;",
        " var maxFallback=3, baseAttrs={}, lastPos=0, readyAt=0, activeSource=null;\n"
        " var requested=false, adActive=false, playTimers=[];",
    ),
    (
        " function clearTimers(){ timers.forEach(clearTimeout); timers=[]; if(seen){clearInterval(seen);seen=null;} }",
        " function clearPlayTimers(){ playTimers.forEach(clearTimeout); playTimers=[]; }\n"
        " function clearTimers(){ timers.forEach(clearTimeout); timers=[]; clearPlayTimers(); if(seen){clearInterval(seen);seen=null;} }\n"
        " function armPlayTimers(myGen, myAttempt){\n"
        "  clearPlayTimers();\n"
        "  playTimers.push(setTimeout(function(){\n"
        "   if(myGen!==generation || myAttempt!==attempt || playing || adActive) return;\n"
        "   nextOrFail('timeout-no-playing');\n"
        "  },25000));\n"
        "  playTimers.push(setTimeout(function(){\n"
        "   if(myGen!==generation || myAttempt!==attempt || playing || adActive) return;\n"
        "   if(!отказ) state('provider', MSG, '');\n"
        "  },35000));\n"
        " }",
    ),
    (
        "  if(!type) return;\n"
        "  if(type==='statechange' && data==='ready'){",
        "  if(!type) return;\n"
        "  if(type==='requestPlay'){\n"
        "   requested=true;\n"
        "   if(!playing && !adActive) armPlayTimers(myGen, myAttempt);\n"
        "   return;\n"
        "  }\n"
        "  if(type==='adStart' || (type==='rollState' && data && data.state==='start')){\n"
        "   adActive=true; clearPlayTimers();\n"
        "   return;\n"
        "  }\n"
        "  if(type==='adComplete' || type==='adClosed' || type==='adSkipped' || type==='adError'\n"
        "     || (type==='rollState' && data && data.state && data.state!=='start')){\n"
        "   if(adActive){ adActive=false; if(requested && !playing) armPlayTimers(myGen, myAttempt); }\n"
        "   return;\n"
        "  }\n"
        "  if(type==='statechange' && data==='ready'){",
    ),
    (
        "  playing=false; отказ=false; lastPos=0; readyAt=0;\n",
        "  playing=false; отказ=false; lastPos=0; readyAt=0; requested=false; adActive=false;\n",
    ),
    (
        "  timers.push(setTimeout(function(){\n"
        "   if(myGen!==generation || myAttempt!==attempt || playing) return;\n"
        "   nextOrFail('timeout-no-playing');\n"
        "  },25000));\n"
        "  timers.push(setTimeout(function(){\n"
        "   if(myGen!==generation || myAttempt!==attempt || playing) return;\n"
        "   if(!отказ) state('provider', MSG, '');\n"
        "  },35000));\n",
        "  // Таймеры «нет воспроизведения» взводятся по requestPlay (armPlayTimers),\n"
        "  // а не при монтировании: см. src/player_watchdog.py витрины.\n",
    ),
)


def исправить(скрипт: str) -> str:
    """Применить замены к тексту скрипта. Каждый якорь — ровно один раз."""
    for старое, новое in ЗАМЕНЫ:
        n = скрипт.count(старое)
        if n != 1:
            raise RuntimeError(
                f"сторож плеера: якорь найден {n} раз(а), ожидался 1: {старое[:70]!r}")
        скрипт = скрипт.replace(старое, новое, 1)
    return скрипт


def установить(рантайм) -> str:
    if getattr(рантайм, "_сторож_плеера_исправлен", False):
        return ИМЯ_ПРАВКИ + " — уже стоит"
    рантайм.СКРИПТ_ПЛЕЕРА_КЛИЕНТ = исправить(рантайм.СКРИПТ_ПЛЕЕРА_КЛИЕНТ)
    рантайм._сторож_плеера_исправлен = True
    return ИМЯ_ПРАВКИ
