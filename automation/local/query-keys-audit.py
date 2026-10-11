#!/usr/bin/env python3
"""Ключи запроса по SEO_KNOWLEDGE_PACK §3 п.2–3 на живых витринах — четыре пробы, все обязательны.

* неизвестный ключ ?nosuchkey=1 — не индексируется;
* повтор ?genre=X&genre=Y — не индексируется;
* метка трафика ?utm_source=proba — 200 без перенаправления, не индексируется,
  canonical на адрес без метки (три условия сразу: сломанный адрес тоже «не
  индексируется», и проба только на noindex приняла бы 404 за норму);
* известный ключ ?genre=X — 200, с карточками и ИНДЕКСИРУЕМЫЙ (защита от
  слишком широкого запрета: регрессия только по запрещённым адресам зелена и
  тогда, когда запрещено всё); у AnimeGo ещё ?yf=2020.

«Индексируется» — нет noindex ни в meta robots, ни в X-Robots-Tag. Не измерено —
отдельно и не успех.

    python3 automation/local/query-keys-audit.py [домен …]
"""
from __future__ import annotations

import html
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

СЕТЬ = {
    "lordserial33.biz": ("/catalog/", "drama", "komediya"), "lordfilm47.space": ("/catalog/", "drama", "komediya"),
    "1lordserials1.online": ("/catalog/", "drama", "komediya"), "lordserials22.info": ("/catalog/", "drama", "komediya"),
    "zonafilm.space": ("/catalog/", "drama", "comedy"), "zonafilm12.site": ("/catalog/", "drama", "comedy"),
    "zonafilm.cc": ("/catalog/", "drama", "comedy"),
    "an1mego.site": ("/catalog/", "боевик", "комедия"), "animeg0.site": ("/catalog/", "боевик", "комедия"),
    "an1meg0.site": ("/catalog/", "боевик", "комедия"),
    "animedia.icu": ("/catalog/", "boevik", "komediya"), "animedia.space": ("/catalog/", "boevik", "komediya"),
}
ANIMEGO = {"an1mego.site", "animeg0.site", "an1meg0.site"}


class _Без(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *а, **к):
        return None


def запросить(адрес: str):
    req = urllib.request.Request(адрес, headers={"User-Agent": "seo-operator-query-keys/1"})
    try:
        r = urllib.request.build_opener(_Без).open(req, timeout=60)
        return r.status, r.headers, r.read(3_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers, ""


def снять(адрес: str) -> dict:
    код, заг, тело = запросить(адрес)
    роботы = " ".join(re.findall(r'<meta\s+name="robots"\s+content="([^"]+)"', тело)) + " " + (заг.get("X-Robots-Tag") or "")
    канон = [html.unescape(к) for к in re.findall(r'<link rel="canonical" href="([^"]+)"', тело)]
    карточек = len(set(re.findall(r'href="(?:https://[^"/]+)?/title/([^/"]+)/?"', тело)))
    return {"код": код, "закрыт": "noindex" in роботы.lower(), "канон": канон[:1], "карточек": карточек,
            "куда": заг.get("Location")}


def main(argv: list[str]) -> int:
    хосты = argv or list(СЕТЬ)
    if any(х not in СЕТЬ for х in хосты):
        print("домены вне перечня сети")
        return 2
    плохо = 0
    for х in хосты:
        путь, ж1, ж2 = СЕТЬ[х]
        база = f"https://{х}{путь}"
        q = urllib.parse.quote
        пробы = [
            ("неизвестный ключ", f"{база}?nosuchkey=1", lambda с: с["код"] != 200 or с["закрыт"]),
            ("повтор ключа", f"{база}?genre={q(ж1)}&genre={q(ж2)}", lambda с: с["код"] != 200 or с["закрыт"]),
            ("метка трафика", f"{база}?utm_source=proba",
             lambda с: с["код"] == 200 and с["закрыт"] and с["канон"] and "utm_" not in с["канон"][0]),
            ("известный ключ", f"{база}?genre={q(ж1)}",
             lambda с: с["код"] == 200 and not с["закрыт"] and с["карточек"] > 0),
        ]
        if х in ANIMEGO:
            пробы.append(("рабочий yf", f"{база}?yf=2020",
                          lambda с: с["код"] == 200 and not с["закрыт"] and с["карточек"] > 0))
        for имя, адрес, годно in пробы:
            try:
                с = снять(адрес)
            except (urllib.error.URLError, OSError) as exc:
                print(f"НЕ ИЗМЕРЕНО {х} {имя}: {exc}")
                плохо += 1
                continue
            ок = bool(годно(с))
            плохо += not ок
            print(f"{'ок' if ок else 'НАРУШЕНИЕ':12} {х:22} {имя:16} {с['код']} закрыт={с['закрыт']} "
                  f"canon={с['канон']} карточек={с['карточек']} {с['куда'] or ''}", flush=True)
    print("ИТОГ", "чисто" if not плохо else f"нарушений/не измерено: {плохо}")
    return 1 if плохо else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
