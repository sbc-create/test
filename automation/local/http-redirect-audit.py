#!/usr/bin/env python3
"""Отдаёт ли `http://домен/` перенаправление на https — по всем доменам сети.

Зачем. Адрес, отвечающий 200 и по http, и по https, — это два адреса одной
страницы: дубль для поиска. Проверяется БЕЗ следования переходам: нужен код
первого ответа и заголовок `Location`, а не конечная страница.

Отдельно проверяется путь ACME (`/.well-known/acme-challenge/`): он обязан
остаться доступным по http, иначе сломается продление сертификата. Поэтому
«перенаправлять всё подряд» — неверное требование, и инструмент это различает.

    python3 automation/local/http-redirect-audit.py
    python3 automation/local/http-redirect-audit.py a.site b.site
"""
from __future__ import annotations

import concurrent.futures
import http.client
import re
import sys

ДОМЕНЫ = (
    "animedia.icu", "animedia.space", "animeg0.site", "an1mego.site",
    "an1meg0.site", "lordfilm47.space", "lordserial33.biz",
    "lordserials22.info", "1lordserials1.online", "zonafilm.cc",
    "zonafilm.space", "zonafilm12.site", "yummyani.site", "yummyani.org",
    "yummyani.biz", "yummyani7.site", "yummyani7.info",
)
ТАЙМАУТ = 15
ПУТЬ_ACME = "/.well-known/acme-challenge/probe-not-a-real-token"


def ответ(домен: str, путь: str, *, тело: bool = False) -> tuple[str, str, str]:
    """Код, Location и (по просьбе) тело первого ответа по http.

    Переходы не следуются намеренно: вопрос именно в том, что отвечает
    ПЕРВЫЙ ответ, а не куда в итоге приводит цепочка.
    """
    try:
        соединение = http.client.HTTPConnection(домен, 80, timeout=ТАЙМАУТ)
        соединение.request("GET", путь, headers={"Host": домен,
                                                 "User-Agent": "redirect-audit"})
        о = соединение.getresponse()
        код = str(о.status)
        куда = о.getheader("Location") or ""
        # Хватает головы документа: canonical и robots стоят в <head>, а
        # качать десятки мегабайт каталога ради двух тегов незачем.
        содержимое = (о.read(40000).decode("utf-8", "replace") if тело
                      else (о.read(1) and ""))
        соединение.close()
        return код, куда, содержимое
    except Exception as сбой:
        return f"нет ответа: {type(сбой).__name__}", "", ""


def проверить(домен: str) -> dict:
    код, куда, страница = ответ(домен, "/", тело=True)
    ведёт_на_https = куда.startswith(f"https://{домен}")
    код_acme, _куда, _т = ответ(домен, ПУТЬ_ACME)
    # Чем закрыта копия по http, если редиректа нет. Различать обязательно:
    # canonical на https — это ВЕСОМОЕ смягчение, и без него отсутствие
    # редиректа значит совсем другое. Измерено 12.10: у всех девяти домена
    # без редиректа canonical уже указывает на https.
    кан = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', страница)
    роб = re.search(r'<meta[^>]+name="robots"[^>]+content="([^"]*)"', страница)
    canonical = кан.group(1) if кан else ""
    return {"домен": домен, "код": код, "location": куда,
            "перенаправляет": код in ("301", "302", "307", "308") and ведёт_на_https,
            "canonical_по_http": canonical,
            "canonical_на_https": canonical.startswith(f"https://{домен}"),
            "robots_по_http": (роб.group(1).strip() if роб else ""),
            # 404 по пути ACME — правильный ответ: токена нет, но путь жив и
            # НЕ перенаправляется. Перенаправление здесь сломало бы продление.
            "acme_жив": код_acme in ("404", "403", "200")}


def главное(аргв: list[str] | None = None) -> int:
    домены = tuple(аргв) if аргв else ДОМЕНЫ
    итоги = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as пул:
        итоги = list(пул.map(проверить, домены))
    print(f"{'домен':24} {'код':>14} {'перенаправляет':>15} {'ACME жив':>9}  Location")
    for и in sorted(итоги, key=lambda и: (и["перенаправляет"], и["домен"])):
        print(f"{и['домен']:24} {и['код']:>14} "
              f"{'да' if и['перенаправляет'] else 'НЕТ':>15} "
              f"{'да' if и['acme_жив'] else 'нет':>9}  {и['location'][:60]}")
    без = [и for и in итоги if not и["перенаправляет"]]
    без_acme = [и for и in итоги if и["перенаправляет"] and not и["acme_жив"]]
    print(f"\nдоменов {len(итоги)}; без перенаправления: {len(без)}")
    if без:
        print("   " + " ".join(и["домен"] for и in без))
        голые = [и for и in без if not и["canonical_на_https"]]
        print(f"   из них БЕЗ canonical на https: {len(голые)}"
              + (" — " + " ".join(и["домен"] for и in голые) if голые else ""))
        print("   это и есть мера серьёзности: при canonical на https копия по "
              "http сама называет правильный адрес, и отсутствие редиректа "
              "остаётся незашифрованным лишним ходом, а не вторым сайтом в "
              "индексе. Без canonical это уже дубль.")
        for и in без:
            if not и["canonical_на_https"]:
                print(f"      {и['домен']:24} canonical "
                      f"{и['canonical_по_http'] or '—'}, "
                      f"robots {и['robots_по_http'] or '—'}")
    if без_acme:
        print(f"ВНИМАНИЕ: перенаправляют и путь ACME: "
              f"{' '.join(и['домен'] for и in без_acme)} — продление "
              "сертификата сломается")
    return 0 if not без and not без_acme else 1


if __name__ == "__main__":
    sys.exit(главное(sys.argv[1:] or None))
