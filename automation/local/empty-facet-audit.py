#!/usr/bin/env python3
"""Пустые и нераспознанные фильтры не публикуются как индексируемые 200.

knowledge/SEO_KNOWLEDGE_PACK.md §3 п.3–4: неизвестные ключи и значения
запрещены; пустые категории, теги и фильтры не публикуются как indexable 200.
Замер 12.10: /catalog/?genre=<нет такого> у Zona и Animedia — 200, index, canonical
на себя; /year/1066/ у Lords — 200 «1066 год» без единой карточки.

Для каждой витрины запрашивает набор заведомо пустых и нераспознанных адресов и
считает нарушением ответ 200 без noindex. Ответ 200 с canonical на ДРУГОЙ адрес
считается допустимым, но отмечается («сводится canonical»). Не измерено —
отдельно, с причиной; в успех не идёт.

    python3 automation/local/empty-facet-audit.py [домен …]
"""
from __future__ import annotations

import html
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

СЕТЬ = {
    "lordserial33.biz": "lords", "lordfilm47.space": "lords", "1lordserials1.online": "lords",
    "lordserials22.info": "lords", "zonafilm.space": "zona", "zonafilm12.site": "zona",
    "zonafilm.cc": "zona", "an1mego.site": "animego", "animeg0.site": "animego",
    "an1meg0.site": "animego", "animedia.icu": "animedia", "animedia.space": "animedia",
}
ПУТИ = {
    "lords": ["/genre/zzz-net-takogo/", "/catalog/?genre=zzz-net-takogo", "/catalog/?sort=zzz",
              "/year/1066/", "/catalog/?year=1066", "/country/zzz/"],
    "zona": ["/catalog/?genre=zzz-net-takogo", "/catalog/?sort=zzz", "/year/1066/",
             "/catalog/?year=1066", "/country/zzz/"],
    "animego": ["/catalog/?genre=zzz-net-takogo", "/catalog/?sort=zzz", "/year/1066/",
                "/catalog/?year=1066", "/country/zzz/"],
    "animedia": ["/catalog/?genre=zzz-net-takogo", "/catalog/?sort=zzz",
                 "/catalog/?year=1066", "/catalog/?country=zzz"],
}


class _Без(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *а, **к):
        return None


def запросить(адрес: str):
    оп = urllib.request.build_opener(_Без)
    req = urllib.request.Request(адрес, headers={"User-Agent": "seo-operator-empty-facet/1"})
    try:
        r = оп.open(req, timeout=60)
        return r.status, r.headers, r.read(3_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers, ""


def оценить(хост: str, путь: str) -> tuple[str, str]:
    адрес = f"https://{хост}{путь}"
    try:
        код, заг, тело = запросить(адрес)
    except (urllib.error.URLError, OSError) as exc:
        return "НЕ ИЗМЕРЕНО", f"{type(exc).__name__}: {exc}"
    if код != 200:
        return "ок", f"{код}"
    роботы = " ".join(re.findall(r'<meta name="robots" content="([^"]+)"', тело)) + " " + (заг.get("X-Robots-Tag") or "")
    if "noindex" in роботы:
        return "ок", "200 noindex"
    канон = [html.unescape(к) for к in re.findall(r'<link rel="canonical" href="([^"]+)"', тело)]
    своё = urllib.parse.urlsplit(адрес)
    if канон:
        к = urllib.parse.urlsplit(канон[0])
        if (к.path, к.query) != (своё.path, своё.query):
            return "сводится canonical", f"200 → canonical {канон[0]}"
    h1 = re.sub(r"<[^>]+>", "", (re.findall(r"<h1[^>]*>(.*?)</h1>", тело, re.S) or [""])[0]).strip()
    return "НАРУШЕНИЕ", f"200 index, canonical {канон[:1]}, H1 «{h1[:50]}»"


def main(argv: list[str]) -> int:
    хосты = argv or list(СЕТЬ)
    чужие = [х for х in хосты if х not in СЕТЬ]
    if чужие:
        print(f"домены вне перечня сети: {чужие}")
        return 2
    итог = {"ок": 0, "сводится canonical": 0, "НАРУШЕНИЕ": 0, "НЕ ИЗМЕРЕНО": 0}
    for х in хосты:
        for п in ПУТИ[СЕТЬ[х]]:
            вердикт, подробно = оценить(х, п)
            итог[вердикт] += 1
            print(f"{вердикт:20} {х}{п}  {подробно}", flush=True)
    print("ИТОГ", итог)
    return 1 if итог["НАРУШЕНИЕ"] or итог["НЕ ИЗМЕРЕНО"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
