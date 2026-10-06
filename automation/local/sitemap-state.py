#!/usr/bin/env python3
"""Что домен ГОВОРИТ о карте сайта и какие разделы он действительно отдаёт.

Только чтение, по публичному HTTPS. Нужен перед подключением карты: перечень
разделов в карту заносится ИЗМЕРЕННЫМ, а не по аналогии с соседом — у сайтов
семейства наборы разные, и раздел, попавший в карту по догадке, дал бы
поисковику ошибочный адрес.

Отдельно печатается режим индексации: закрытому домену карта не нужна, и 404
на `/sitemap.xml` у него — правильный ответ, а не дефект.

    python3 automation/local/sitemap-state.py <домен> [<домен> …]
"""
from __future__ import annotations

import re
import subprocess
import sys

#: Разделы, которые встречаются у семейств lords/zona/animego. Проверяются ВСЕ,
#: в карту пойдут только ответившие 200 собственным содержимым.
КАНДИДАТЫ = ("/movies/", "/series/", "/animation/", "/anime/", "/dorama/",
             "/catalog/", "/collections/", "/genres/", "/years/", "/new/",
             "/popular/", "/schedule/", "/random/", "/top/")


def ответ(url: str, таймаут: int = 30) -> tuple[str, str, dict[str, str]]:
    г = subprocess.run(["curl", "-sS", "--max-time", str(таймаут), "-D", "-", url],
                       capture_output=True, text=True)
    всё = г.stdout or ""
    разд = "\r\n\r\n" if "\r\n\r\n" in всё else "\n\n"
    части = всё.split(разд)
    голова = части[0]
    тело = разд.join(части[1:]) if len(части) > 1 else ""
    код = ""
    заг: dict[str, str] = {}
    for с in голова.splitlines():
        if с.lower().startswith("http/"):
            ч = с.split()
            код = ч[1] if len(ч) > 1 else ""
        elif ":" in с:
            к, _, з = с.partition(":")
            заг.setdefault(к.strip().lower(), з.strip())
    return код, тело, заг


def проверить(домен: str) -> dict:
    итог: dict = {"домен": домен}
    код, тело, заг = ответ(f"https://{домен}/")
    итог["главная"] = код
    итог["x-robots-tag"] = заг.get("x-robots-tag", "")
    итог["build"] = заг.get("x-site-factory-build-id", "")
    мета = re.search(r'<meta[^>]+name="robots"[^>]+content="([^"]+)"', тело)
    итог["meta-robots"] = мета.group(1) if мета else ""

    к, т, _ = ответ(f"https://{домен}/robots.txt")
    итог["robots.txt"] = к
    итог["robots-sitemap"] = [с.strip() for с in т.splitlines()
                              if с.lower().startswith("sitemap:")]
    итог["robots-disallow-all"] = bool(re.search(r"(?mi)^Disallow:\s*/\s*$", т))

    к, т, _ = ответ(f"https://{домен}/sitemap.xml")
    итог["sitemap.xml"] = к
    итог["sitemap-loc"] = т.count("<loc>")
    итог["sitemap-index"] = "<sitemapindex" in т

    разделы = {}
    for р in КАНДИДАТЫ:
        к2, т2, _ = ответ(f"https://{домен}{р}")
        карточек = len(set(re.findall(r'href="/(?:title|anime)/[a-z0-9-]+', т2)))
        кан = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', т2)
        свой = bool(кан) and кан.group(1).rstrip("/").endswith(р.rstrip("/"))
        разделы[р] = {"код": к2, "карточек": карточек, "canonical_свой": свой}
    итог["разделы"] = разделы
    return итог


def главная(argv: list[str]) -> int:
    домены = argv[1:]
    if not домены:
        print(__doc__)
        return 2
    for домен in домены:
        о = проверить(домен)
        print(f"\n=== {домен}  build {о['build'] or '—'}")
        print(f"    режим: X-Robots-Tag {о['x-robots-tag'] or '—'} | "
              f"meta {о['meta-robots'] or '—'}")
        print(f"    robots.txt {о['robots.txt']}: Sitemap {о['robots-sitemap'] or '—'}"
              f" | Disallow всего: {о['robots-disallow-all']}")
        print(f"    /sitemap.xml {о['sitemap.xml']}: loc {о['sitemap-loc']}, "
              f"индекс {о['sitemap-index']}")
        годные = [р for р, д in о["разделы"].items()
                  if д["код"] == "200" and д["карточек"] > 0 and д["canonical_свой"]]
        print(f"    разделы 200 + карточки + свой canonical: {' '.join(годные) or '—'}")
        for р, д in о["разделы"].items():
            if д["код"] != "404":
                print(f"       {р:14} код {д['код']:3} карточек {д['карточек']:3} "
                      f"canonical свой {д['canonical_свой']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(главная(sys.argv))
