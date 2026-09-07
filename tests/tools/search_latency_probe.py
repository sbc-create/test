"""Замер подсказки с переиспользованием соединения.

Прошлый замер открывал новое TLS-соединение на каждый запрос. Браузер так не
делает: подсказка идёт по уже установленному соединению, и рукопожатие в её
задержку не входит. Мерить его вместе с поиском — значит записывать стоимость
сети в счёт указателя.

Здесь одно соединение на весь прогон, как у страницы, которая уже открыта.
"""
from __future__ import annotations

import contextlib
import http.client
import json
import random
import statistics
import time
import urllib.parse

ХОСТ = "1lordserials1.online"
КАТАЛОГ = "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json"

with open(КАТАЛОГ, encoding="utf-8") as файл:
    каталог = json.load(файл)
записи = каталог["items"] if isinstance(каталог, dict) else каталог
случай = random.Random(20260907)
имена = [str(з.get("name") or "").strip() for з in записи if з.get("name")]

связь = http.client.HTTPSConnection(ХОСТ, timeout=20)


def замер(путь: str) -> float | None:
    global связь
    начало = time.monotonic()
    try:
        связь.request("GET", путь, headers={"User-Agent": "latency-probe/1.0",
                                            "Connection": "keep-alive"})
        связь.getresponse().read()
    except Exception:
        # Соединение могло быть закрыто сервером — поднимаем заново и не
        # засчитываем этот запрос: иначе в выборку попадёт стоимость обрыва.
        with contextlib.suppress(Exception):
            связь.close()
        связь = http.client.HTTPSConnection(ХОСТ, timeout=20)
        return None
    return (time.monotonic() - начало) * 1000


def префиксы(длина: int, сколько: int) -> list[str]:
    итог = []
    while len(итог) < сколько:
        имя = случай.choice(имена)
        if len(имя) >= длина:
            итог.append(имя[:длина])
    return итог


def прогон(подпись: str, запросы: list[str], шаблон: str, цель: int) -> None:
    замеры = [м for q in запросы
              if (м := замер(f"{шаблон}{urllib.parse.quote(q)}")) is not None]
    if not замеры:
        print(f"  {подпись:28} все запросы отказали")
        return
    замеры.sort()
    p95 = замеры[min(len(замеры) - 1, int(len(замеры) * 0.95))]
    вердикт = "выполнена" if p95 <= цель else "НЕ выполнена"
    print(f"  {подпись:28} n={len(замеры):3} p50={statistics.median(замеры):6.1f} "
          f"p95={p95:6.1f} max={замеры[-1]:6.1f} мс   цель {цель} мс: {вердикт}")


замер("/api/search?q=%D0%BC%D0%B0")  # прогрев соединения и указателя
for длина in (2, 3, 4, 6, 10):
    прогон(f"подсказка, префикс {длина}", префиксы(длина, 120), "/api/search?q=", 250)
прогон("страница, полное название", [случай.choice(имена) for _ in range(120)],
       "/search/?q=", 800)
связь.close()
