#!/usr/bin/env python3
"""Внутренний поиск не индексируется по ОБОИМ слоям и работает (SEO_KNOWLEDGE_PACK §3 п.2).

Для каждой витрины: /search/?q=<запрос> и /search/ —
* ответ 200 (поиск работает), у ?q= есть карточки;
* ровно один заголовок X-Robots-Tag, с noindex; meta robots с noindex; значения
  не противоречат друг другу (противоречивая пара — дефект D150/D166/D187);
* контроль: /catalog/ остаётся index (правило не накрыло соседнее).
Не измерено — отдельно, не успех.

    python3 automation/local/search-noindex-audit.py [домен …]
"""
from __future__ import annotations

import http.client
import re
import sys
import urllib.parse

СЕТЬ = ("lordserial33.biz", "lordfilm47.space", "1lordserials1.online", "lordserials22.info",
        "zonafilm.space", "zonafilm12.site", "zonafilm.cc", "an1mego.site", "animeg0.site",
        "an1meg0.site", "animedia.icu", "animedia.space")
ЗАПРОС = urllib.parse.quote("наруто")


def снять(хост: str, путь: str) -> dict:
    с = http.client.HTTPSConnection(хост, timeout=60)
    с.request("GET", путь, headers={"User-Agent": "seo-operator-search-audit/1"})
    r = с.getresponse()
    тело = r.read(3_000_000).decode("utf-8", "replace")
    заг = [v for k, v in r.getheaders() if k.lower() == "x-robots-tag"]
    мета = re.findall(r'<meta\s+name="robots"\s+content="([^"]+)"', тело)
    return {"код": r.status, "заг": заг, "мета": мета, "build": r.getheader("x-site-factory-build-id"),
            "карточек": len(set(re.findall(r'href="(?:https://[^"/]+)?/title/([^/"]+)/?"', тело)))}


def main(argv: list[str]) -> int:
    хосты = argv or list(СЕТЬ)
    if any(х not in СЕТЬ for х in хосты):
        print("домены вне перечня")
        return 2
    плохо = 0
    for х in хосты:
        try:
            пробы = {"поиск ?q": снять(х, f"/search/?q={ЗАПРОС}"), "поиск пустой": снять(х, "/search/"),
                     "каталог": снять(х, "/catalog/")}
        except OSError as exc:
            print(f"НЕ ИЗМЕРЕНО {х}: {exc}")
            плохо += 1
            continue
        беды = []
        for имя, с in пробы.items():
            закрыт_заг = [("noindex" in v.lower()) for v in с["заг"]]
            закрыт_мета = [("noindex" in v.lower()) for v in с["мета"]]
            if с["код"] != 200:
                беды.append(f"{имя}: код {с['код']}")
            if len(с["заг"]) != 1:
                беды.append(f"{имя}: X-Robots-Tag {len(с['заг'])} шт: {с['заг']}")
            if len(set(закрыт_заг + закрыт_мета)) > 1:
                беды.append(f"{имя}: слои расходятся: заголовок {с['заг']} / meta {с['мета']}")
            ждём = имя != "каталог"
            if закрыт_заг and закрыт_заг[0] is not ждём:
                беды.append(f"{имя}: {'не закрыт' if ждём else 'закрыт'}: {с['заг']}")
        if пробы["поиск ?q"]["карточек"] == 0:
            беды.append("поиск по запросу не вернул карточек — проверьте, работает ли он")
        плохо += bool(беды)
        print(f"{'ок' if not беды else 'НАРУШЕНИЕ':10} {х:22} build {пробы['поиск ?q']['build']} "
              f"?q: {пробы['поиск ?q']['заг']} карточек {пробы['поиск ?q']['карточек']}", flush=True)
        for б in беды:
            print("    ·", б)
    print("ИТОГ", "чисто" if not плохо else f"витрин с нарушениями: {плохо}")
    return 1 if плохо else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
